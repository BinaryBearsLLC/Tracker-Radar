#!/usr/bin/env python3
"""Torrent Tracker Inspector - a dependency-free macOS-friendly tracker tester.

The program validates HTTP(S) and UDP BitTorrent trackers, imports tracker lists
from text/files/URLs, and can query tracker-reported swarm statistics for magnet
links and .torrent files.  It intentionally does not download torrent payloads.
"""

from __future__ import annotations

import argparse
import base64
import concurrent.futures
import csv
import hashlib
import os
import queue
import random
import re
import socket
import ssl
import struct
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable, Optional


APP_NAME = "Tracker Radar"
APP_VERSION = "1.0.0"
USER_AGENT = f"{APP_NAME}/{APP_VERSION} (local tracker diagnostic)"
MAX_HTTP_BODY = 2 * 1024 * 1024
MAX_LIST_BODY = 5 * 1024 * 1024
MAX_TRACKERS = 2_000
SUPPORTED_SCHEMES = {"http", "https", "udp"}
NGOSANG_REPOSITORY = "https://github.com/ngosang/trackerslist"
NGOSANG_SOURCES = {
    "Best (recommended)": "trackers_best.txt",
    "All HTTP + HTTPS + UDP": "trackers_all.txt",
    "UDP only": "trackers_all_udp.txt",
    "HTTP only": "trackers_all_http.txt",
    "HTTPS only": "trackers_all_https.txt",
}


def ngosang_mirrors(filename: str) -> tuple[str, ...]:
    """Return official/mirrored URLs in preferred failover order."""
    return (
        f"https://raw.githubusercontent.com/ngosang/trackerslist/master/{filename}",
        f"https://ngosang.github.io/trackerslist/{filename}",
        f"https://cdn.jsdelivr.net/gh/ngosang/trackerslist@master/{filename}",
    )


class InspectorError(Exception):
    """A user-facing validation or parsing error."""


class BencodeError(InspectorError):
    """Raised for malformed bencoded data."""


class UnknownSwarm(InspectorError):
    """A tracker answered without statistics for the requested hash."""


@dataclass(frozen=True)
class SwarmContext:
    info_hash: bytes
    display_hash: str
    name: str
    trackers: tuple[str, ...]
    source_kind: str
    note: str = ""
    private: bool = False


@dataclass
class TrackerResult:
    url: str
    status: str
    protocol: str
    latency_ms: Optional[int] = None
    seeders: Optional[int] = None
    peers: Optional[int] = None
    completed: Optional[int] = None
    detail: str = ""
    method: str = ""
    checked_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )

    @property
    def exportable(self) -> bool:
        return self.status == "WORKING"


def _text(value: Any) -> str:
    if isinstance(value, bytes):
        return value.decode("utf-8", "replace")
    return str(value)


class BDecoder:
    """Small bounded bencode decoder; can capture the top-level info span."""

    def __init__(self, data: bytes, *, strict: bool = False) -> None:
        self.data = data
        self.strict = strict
        self.nodes = 0
        self.info_span: Optional[tuple[int, int]] = None

    def decode(self) -> Any:
        value, end = self._node(0, 0)
        if end != len(self.data):
            raise BencodeError("Trailing bytes after the bencoded value")
        return value

    def _node(self, pos: int, depth: int) -> tuple[Any, int]:
        if depth > 100:
            raise BencodeError("Bencoded data is nested too deeply")
        self.nodes += 1
        if self.nodes > 500_000:
            raise BencodeError("Bencoded data contains too many values")
        if pos >= len(self.data):
            raise BencodeError("Unexpected end of bencoded data")

        marker = self.data[pos : pos + 1]
        if marker == b"i":
            end = self.data.find(b"e", pos + 1)
            if end < 0:
                raise BencodeError("Unterminated bencoded integer")
            raw = self.data[pos + 1 : end]
            if not raw or raw in (b"-0",) or (raw.startswith(b"0") and raw != b"0"):
                raise BencodeError("Invalid bencoded integer")
            if raw.startswith(b"-") and (len(raw) == 1 or raw[1:2] == b"0"):
                raise BencodeError("Invalid negative bencoded integer")
            try:
                return int(raw), end + 1
            except ValueError as exc:
                raise BencodeError("Invalid bencoded integer") from exc

        if marker == b"l":
            values: list[Any] = []
            pos += 1
            while True:
                if pos >= len(self.data):
                    raise BencodeError("Unterminated bencoded list")
                if self.data[pos : pos + 1] == b"e":
                    return values, pos + 1
                item, pos = self._node(pos, depth + 1)
                values.append(item)

        if marker == b"d":
            result: dict[bytes, Any] = {}
            previous: Optional[bytes] = None
            pos += 1
            while True:
                if pos >= len(self.data):
                    raise BencodeError("Unterminated bencoded dictionary")
                if self.data[pos : pos + 1] == b"e":
                    return result, pos + 1
                key, pos = self._node(pos, depth + 1)
                if not isinstance(key, bytes):
                    raise BencodeError("Bencoded dictionary keys must be byte strings")
                if self.strict and previous is not None and key <= previous:
                    raise BencodeError("Torrent dictionary keys are duplicated or unsorted")
                previous = key
                value_start = pos
                value, pos = self._node(pos, depth + 1)
                if depth == 0 and key == b"info":
                    self.info_span = (value_start, pos)
                result[key] = value

        if b"0" <= marker <= b"9":
            colon = self.data.find(b":", pos)
            if colon < 0:
                raise BencodeError("Invalid bencoded byte string")
            length_raw = self.data[pos:colon]
            if not length_raw or (length_raw.startswith(b"0") and length_raw != b"0"):
                raise BencodeError("Invalid bencoded byte-string length")
            try:
                length = int(length_raw)
            except ValueError as exc:
                raise BencodeError("Invalid bencoded byte-string length") from exc
            if length < 0 or length > 64 * 1024 * 1024:
                raise BencodeError("Bencoded byte string is too large")
            start = colon + 1
            end = start + length
            if end > len(self.data):
                raise BencodeError("Truncated bencoded byte string")
            return self.data[start:end], end

        raise BencodeError(f"Unknown bencode marker at byte {pos}")


def bdecode(data: bytes, *, strict: bool = False) -> Any:
    return BDecoder(data, strict=strict).decode()


def _dict_get(mapping: dict[bytes, Any], *names: bytes) -> Any:
    for name in names:
        if name in mapping:
            return mapping[name]
    return None


def _decode_url(raw: Any) -> Optional[str]:
    if not isinstance(raw, bytes):
        return None
    value = raw.decode("utf-8", "replace").strip()
    return value or None


def parse_torrent_bytes(data: bytes, *, source_name: str = "torrent") -> SwarmContext:
    if len(data) > 64 * 1024 * 1024:
        raise InspectorError("The .torrent file is unexpectedly large")
    decoder = BDecoder(data, strict=True)
    metainfo = decoder.decode()
    if not isinstance(metainfo, dict) or decoder.info_span is None:
        raise InspectorError("This is not a valid .torrent metainfo file (missing info)")
    info = metainfo.get(b"info")
    if not isinstance(info, dict):
        raise InspectorError("The torrent info value is not a dictionary")

    start, end = decoder.info_span
    raw_info = data[start:end]
    meta_version = info.get(b"meta version")
    has_v1 = isinstance(info.get(b"pieces"), bytes)
    if not has_v1 and meta_version != 2:
        raise InspectorError("Torrent has neither v1 pieces nor v2 metadata")
    if meta_version == 2 and not has_v1:
        full = hashlib.sha256(raw_info).digest()
        tracker_hash = full[:20]
        display_hash = full.hex()
        kind = "BitTorrent v2"
        note = "Trackers are queried with the 20-byte truncated SHA-256 info-hash."
    else:
        full = hashlib.sha1(raw_info).digest()
        tracker_hash = full
        display_hash = full.hex()
        kind = "Hybrid v1/v2" if meta_version == 2 else "BitTorrent v1"
        note = "Hybrid torrents are queried through their v1 SHA-1 swarm."

    name = _decode_url(info.get(b"name.utf-8")) or _decode_url(info.get(b"name"))
    trackers: list[str] = []
    announce = _decode_url(metainfo.get(b"announce"))
    if announce:
        trackers.append(announce)
    tiers = metainfo.get(b"announce-list")
    if isinstance(tiers, list):
        for tier in tiers:
            candidates = tier if isinstance(tier, list) else [tier]
            for candidate in candidates:
                decoded = _decode_url(candidate)
                if decoded:
                    trackers.append(decoded)
    return SwarmContext(
        tracker_hash,
        display_hash,
        name or Path(source_name).name,
        tuple(dedupe_trackers(trackers)),
        kind,
        note,
        info.get(b"private") == 1,
    )


def parse_torrent_file(path: str | os.PathLike[str]) -> SwarmContext:
    torrent_path = Path(path)
    try:
        data = torrent_path.read_bytes()
    except OSError as exc:
        raise InspectorError(f"Could not read the torrent file: {exc}") from exc
    return parse_torrent_bytes(data, source_name=torrent_path.name)


def parse_magnet(uri: str) -> SwarmContext:
    uri = uri.strip()
    if not uri.lower().startswith("magnet:?"):
        raise InspectorError("The swarm field does not contain a magnet link")
    parsed = urllib.parse.urlsplit(uri)
    params = urllib.parse.parse_qs(parsed.query, keep_blank_values=True)
    xt_values = params.get("xt", [])
    btih: Optional[bytes] = None
    btmh: Optional[bytes] = None
    for xt in xt_values:
        lowered = xt.lower()
        if lowered.startswith("urn:btih:"):
            encoded = xt[9:]
            try:
                if len(encoded) == 40 and re.fullmatch(r"[0-9a-fA-F]{40}", encoded):
                    btih = bytes.fromhex(encoded)
                elif len(encoded) == 32 and re.fullmatch(r"[A-Za-z2-7]{32}", encoded):
                    btih = base64.b32decode(encoded.upper())
            except (ValueError, base64.binascii.Error):
                pass
        elif lowered.startswith("urn:btmh:"):
            encoded = xt[9:]
            # BEP 9/BEP 52 magnets commonly use hex multihash 0x12 0x20 + SHA-256.
            if re.fullmatch(r"1220[0-9a-fA-F]{64}", encoded):
                btmh = bytes.fromhex(encoded[4:])
    if btih is not None:
        info_hash = btih
        display = btih.hex()
        kind = "Magnet v1" if btmh is None else "Hybrid magnet"
        note = "Hybrid magnets are queried through their v1 SHA-1 swarm." if btmh else ""
    elif btmh is not None:
        info_hash = btmh[:20]
        display = btmh.hex()
        kind = "Magnet v2"
        note = "Trackers are queried with the 20-byte truncated SHA-256 info-hash."
    else:
        raise InspectorError(
            "The magnet has no supported info-hash (btih hex/base32 or btmh SHA-256)"
        )
    name = params.get("dn", ["Unnamed magnet"])[0] or "Unnamed magnet"
    trackers = dedupe_trackers(params.get("tr", []))
    return SwarmContext(info_hash, display, name, tuple(trackers), kind, note)


TRACKER_RE = re.compile(r"(?i)\b(?:https?|udp|wss?)://[^\s<>\"']+")


def parse_tracker_text(text: str) -> list[str]:
    text = text.lstrip("\ufeff")
    found: list[str] = []
    for match in TRACKER_RE.finditer(text):
        value = match.group(0).strip().rstrip(",;)]}")
        if value:
            found.append(value)
    return dedupe_trackers(found)


def _canonical_tracker(url: str) -> str:
    try:
        parsed = urllib.parse.urlsplit(url.strip())
        host = (parsed.hostname or "").lower()
        if ":" in host:
            host = f"[{host}]"
        port = f":{parsed.port}" if parsed.port is not None else ""
        user = ""
        if parsed.username:
            user = parsed.username
            if parsed.password:
                user += f":{parsed.password}"
            user += "@"
        netloc = f"{user}{host}{port}"
        return urllib.parse.urlunsplit(
            (parsed.scheme.lower(), netloc, parsed.path, parsed.query, parsed.fragment)
        )
    except (ValueError, UnicodeError):
        return url.strip()


def dedupe_trackers(trackers: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for tracker in trackers:
        value = tracker.strip()
        if not value:
            continue
        key = _canonical_tracker(value)
        if key not in seen:
            seen.add(key)
            result.append(value)
        if len(result) >= MAX_TRACKERS:
            break
    return result


def validate_tracker_url(url: str) -> tuple[bool, str, Optional[urllib.parse.SplitResult]]:
    if not url or any(char.isspace() for char in url):
        return False, "URL is empty or contains whitespace", None
    try:
        parsed = urllib.parse.urlsplit(url)
        scheme = parsed.scheme.lower()
        if scheme not in SUPPORTED_SCHEMES:
            return False, "Only HTTP, HTTPS and UDP trackers are supported", parsed
        if not parsed.hostname:
            return False, "Tracker URL has no hostname", parsed
        parsed.hostname.encode("idna")
        port = parsed.port
        if port == 0:
            return False, "Tracker port must be between 1 and 65535", parsed
        if scheme == "udp" and port is None:
            return False, "UDP trackers need an explicit port", parsed
        if parsed.fragment:
            return False, "Tracker URLs cannot contain a fragment", parsed
        return True, "", parsed
    except (ValueError, UnicodeError) as exc:
        return False, f"Invalid tracker URL: {exc}", None


def trackers_for_query(trackers: Iterable[str], swarm: Optional[SwarmContext]) -> list[str]:
    """Never disclose a private torrent's hash to added public trackers."""
    return dedupe_trackers(swarm.trackers if swarm and swarm.private else trackers)


def clean_trackers(trackers, results, *, zero_seeders=False, zero_peers=False,
                   include_unknown=False, swarm_query=False):
    """Select without mutating the input. Unknown counters never equal zero."""
    kept = []
    for url in dedupe_trackers(trackers):
        result = results.get(url)
        if result is None or result.status not in ("WORKING", "REVIEW"):
            continue
        if result.status != "WORKING" and not include_unknown:
            continue
        if swarm_query:
            if zero_seeders and (result.seeders == 0 or (result.seeders is None and not include_unknown)):
                continue
            if zero_peers and (result.peers == 0 or (result.peers is None and not include_unknown)):
                continue
        kept.append(url)
    return kept


def load_tracker_url(url: str, timeout: float = 12.0) -> str:
    parsed = urllib.parse.urlsplit(url.strip())
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise InspectorError("Tracker-list links must use HTTP or HTTPS")
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=ssl.create_default_context()) as reply:
            body = reply.read(MAX_LIST_BODY + 1)
            if len(body) > MAX_LIST_BODY:
                raise InspectorError("The remote tracker list is larger than 5 MB")
            charset = reply.headers.get_content_charset() or "utf-8"
    except (urllib.error.URLError, OSError) as exc:
        raise InspectorError(f"Could not fetch the tracker list: {exc}") from exc
    return body.decode(charset, "replace")


def load_tracker_sources(
    candidates: Iterable[str], timeout: float = 12.0
) -> tuple[list[str], str]:
    """Load the first usable tracker list, trying candidates in order."""
    urls = [url.strip() for url in candidates if url.strip()]
    if not urls:
        raise InspectorError("No tracker-list URL was provided")
    errors: list[str] = []
    for url in urls:
        try:
            trackers = parse_tracker_text(load_tracker_url(url, timeout=timeout))
            if not trackers:
                raise InspectorError("The downloaded file contains no tracker URLs")
            return trackers, url
        except Exception as exc:
            host = urllib.parse.urlsplit(url).hostname or url
            errors.append(f"{host}: {exc}")
    raise InspectorError(
        "Could not load the tracker list from any available source:\n\n"
        + "\n".join(errors)
    )


def _replace_announce_with_scrape(url: str) -> Optional[str]:
    parsed = urllib.parse.urlsplit(url)
    lower_path = parsed.path.lower()
    index = lower_path.rfind("announce")
    if index < 0:
        return None
    path = parsed.path[:index] + "scrape" + parsed.path[index + len("announce") :]
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, path, parsed.query, ""))


def _append_query(url: str, pairs: Iterable[tuple[str, str | bytes | int]]) -> str:
    parsed = urllib.parse.urlsplit(url)
    encoded: list[str] = []
    for key, value in pairs:
        key_part = urllib.parse.quote(key, safe="")
        if isinstance(value, bytes):
            value_part = urllib.parse.quote_from_bytes(value, safe="")
        else:
            value_part = urllib.parse.quote(str(value), safe="")
        encoded.append(f"{key_part}={value_part}")
    query = "&".join(part for part in (parsed.query, "&".join(encoded)) if part)
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, query, ""))


class TrackerRedirectHandler(urllib.request.HTTPRedirectHandler):
    """Keep tracker hashes and passkeys on the requested origin."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        def origin(url):
            parsed = urllib.parse.urlsplit(url)
            return (parsed.scheme.lower(), parsed.hostname,
                    parsed.port or (443 if parsed.scheme == "https" else 80))
        if origin(req.full_url) != origin(newurl):
            raise InspectorError("Cross-origin tracker redirect blocked; use the intended tracker URL explicitly")
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _http_get(url: str, timeout: float) -> tuple[int, bytes, str, int]:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "application/x-bittorrent,*/*;q=0.2"},
    )
    started = time.monotonic()
    try:
        opener = urllib.request.build_opener(
            urllib.request.HTTPSHandler(context=ssl.create_default_context()),
            TrackerRedirectHandler(),
        )
        with opener.open(request, timeout=timeout) as reply:
            body = reply.read(MAX_HTTP_BODY + 1)
            status = getattr(reply, "status", 200)
            final_url = reply.geturl()
    except urllib.error.HTTPError as exc:
        body = exc.read(MAX_HTTP_BODY + 1)
        status = exc.code
        final_url = exc.geturl()
    latency = round((time.monotonic() - started) * 1000)
    if len(body) > MAX_HTTP_BODY:
        raise InspectorError("Tracker response exceeded 2 MB")
    return status, body, final_url, latency


def _parse_tracker_dict(body: bytes) -> Optional[dict[bytes, Any]]:
    if not body:
        return None
    try:
        value = bdecode(body, strict=False)
    except BencodeError:
        return None
    return value if isinstance(value, dict) else None


AUTH_WORDS = ("passkey", "authentication", "unauthorized", "not authorized", "forbidden")
MISSING_SWARM_WORDS = (
    "unregistered torrent",
    "torrent not found",
    "unknown torrent",
    "not registered",
    "invalid info_hash",
    "invalid info hash",
)
UNSUPPORTED_SCRAPE_WORDS = ("scrape not supported", "scraping is not", "unsupported scrape")


def _failure_reason(mapping: dict[bytes, Any]) -> str:
    reason = _dict_get(mapping, b"failure reason", b"failure_reason")
    return _text(reason).strip() if reason is not None else ""


def _counts_from_scrape(mapping: dict[bytes, Any], info_hash: bytes) -> tuple[int, int, int]:
    files = mapping.get(b"files")
    if not isinstance(files, dict):
        raise InspectorError("Scrape response has no files dictionary")
    stats: Any = files.get(info_hash)
    if stats is None:
        raise UnknownSwarm("Tracker answered; this hash has no reported statistics")
    if not isinstance(stats, dict):
        raise InspectorError("Scrape response has malformed swarm statistics")
    complete = stats.get(b"complete")
    incomplete = stats.get(b"incomplete")
    downloaded = stats.get(b"downloaded", 0)
    if not all(isinstance(item, int) and item >= 0 for item in (complete, incomplete, downloaded)):
        raise InspectorError("Scrape response contains invalid counters")
    return complete, incomplete, downloaded


def _counts_from_announce(mapping: dict[bytes, Any]) -> tuple[Optional[int], Optional[int], Optional[int]]:
    seeders = mapping.get(b"complete")
    peers = mapping.get(b"incomplete")
    completed = mapping.get(b"downloaded")
    return (
        seeders if isinstance(seeders, int) and seeders >= 0 else None,
        peers if isinstance(peers, int) and peers >= 0 else None,
        completed if isinstance(completed, int) and completed >= 0 else None,
    )


def _failure_status(reason: str, *, swarm_query: bool) -> tuple[str, str]:
    lowered = reason.lower()
    if any(word in lowered for word in AUTH_WORDS):
        return "REVIEW", "Authentication/private-tracker response"
    if swarm_query and any(word in lowered for word in MISSING_SWARM_WORDS):
        return "REVIEW", "Tracker works, but this swarm is not registered"
    if not swarm_query and any(word in lowered for word in ("info_hash", "info hash", "peer_id", "peer id")):
        return "WORKING", "Tracker rejected the incomplete availability probe"
    return "REVIEW", "Tracker returned a BitTorrent error"


def _http_announce_url(url: str, info_hash: bytes) -> str:
    peer_id = b"-TTI100-" + os.urandom(12)
    return _append_query(
        url,
        (
            ("info_hash", info_hash),
            ("peer_id", peer_id),
            ("port", 6881),
            ("uploaded", 0),
            ("downloaded", 0),
            ("left", 0),
            ("compact", 1),
            ("numwant", 0),
            ("event", "stopped"),
            ("key", f"{random.getrandbits(32):08x}"),
        ),
    )


def _http_announce_probe(
    url: str, info_hash: Optional[bytes], timeout: float
) -> TrackerResult:
    target = _http_announce_url(url, info_hash) if info_hash else url
    code, body, _final_url, latency = _http_get(target, timeout)
    mapping = _parse_tracker_dict(body)
    if mapping is not None:
        reason = _failure_reason(mapping)
        if reason:
            status, prefix = _failure_status(reason, swarm_query=info_hash is not None)
            return TrackerResult(
                url,
                status,
                urllib.parse.urlsplit(url).scheme.upper(),
                latency,
                detail=f"{prefix}: {reason}",
                method="announce probe" if info_hash is None else "stopped announce",
            )
        seeders, peers, completed = _counts_from_announce(mapping)
        interval = mapping.get(b"interval")
        peer_list = mapping.get(b"peers")
        valid_interval = isinstance(interval, int) and interval >= 0
        valid_peer_list = ((isinstance(peer_list, bytes) and len(peer_list) % 6 == 0)
                           or (isinstance(peer_list, list) and all(isinstance(p, dict) for p in peer_list)))
        if valid_interval or valid_peer_list or seeders is not None or peers is not None:
            return TrackerResult(
                url,
                "WORKING",
                urllib.parse.urlsplit(url).scheme.upper(),
                latency,
                seeders if info_hash else None,
                peers if info_hash else None,
                completed if info_hash else None,
                "Valid BitTorrent announce response",
                "announce probe" if info_hash is None else "stopped announce",
            )
    text = body[:800].decode("utf-8", "replace").strip()
    tracker_like = any(
        token in text.lower()
        for token in ("info_hash", "info hash", "peer_id", "peer id", "announce")
    )
    if tracker_like and code in {200, 400, 422}:
        return TrackerResult(
            url,
            "REVIEW",
            urllib.parse.urlsplit(url).scheme.upper(),
            latency,
            detail=f"HTTP {code}; tracker-like text, but no valid BitTorrent response",
            method="announce probe",
        )
    if code in {401, 403}:
        return TrackerResult(
            url,
            "REVIEW",
            urllib.parse.urlsplit(url).scheme.upper(),
            latency,
            detail=f"HTTP {code}; private or access-controlled tracker",
            method="announce probe",
        )
    return TrackerResult(
        url,
        "FAILED",
        urllib.parse.urlsplit(url).scheme.upper(),
        latency,
        detail=f"HTTP {code}; response is not a valid BitTorrent tracker reply",
        method="announce probe",
    )


def probe_http_tracker(
    url: str,
    info_hash: Optional[bytes],
    timeout: float,
    announce_fallback: bool,
) -> TrackerResult:
    scrape = _replace_announce_with_scrape(url)
    if scrape is not None:
        target = _append_query(scrape, (("info_hash", info_hash or (b"\x00" * 20)),))
        try:
            code, body, _final_url, latency = _http_get(target, timeout)
        except (urllib.error.URLError, OSError, ssl.SSLError, InspectorError) as exc:
            # A network failure on scrape normally applies to announce too.
            return TrackerResult(
                url,
                "FAILED",
                urllib.parse.urlsplit(url).scheme.upper(),
                detail=f"Network error: {exc}",
                method="scrape",
            )
        mapping = _parse_tracker_dict(body)
        if mapping is not None:
            reason = _failure_reason(mapping)
            if reason:
                lowered = reason.lower()
                if any(word in lowered for word in UNSUPPORTED_SCRAPE_WORDS):
                    if announce_fallback or info_hash is None:
                        return _http_announce_probe(url, info_hash, timeout)
                    return TrackerResult(
                        url,
                        "REVIEW",
                        urllib.parse.urlsplit(url).scheme.upper(),
                        latency,
                        detail=f"Tracker works but scrape is unsupported: {reason}",
                        method="scrape",
                    )
                status, prefix = _failure_status(reason, swarm_query=info_hash is not None)
                return TrackerResult(
                    url,
                    status,
                    urllib.parse.urlsplit(url).scheme.upper(),
                    latency,
                    detail=f"{prefix}: {reason}",
                    method="scrape",
                )
            if b"files" in mapping:
                try:
                    seeders, peers, completed = _counts_from_scrape(
                        mapping, info_hash or (b"\x00" * 20)
                    )
                except UnknownSwarm as exc:
                    return TrackerResult(
                        url, "REVIEW" if info_hash else "WORKING",
                        urllib.parse.urlsplit(url).scheme.upper(), latency,
                        detail=str(exc), method="scrape",
                    )
                except InspectorError as exc:
                    return TrackerResult(
                        url,
                        "FAILED",
                        urllib.parse.urlsplit(url).scheme.upper(),
                        latency,
                        detail=str(exc),
                        method="scrape",
                    )
                return TrackerResult(
                    url,
                    "WORKING",
                    urllib.parse.urlsplit(url).scheme.upper(),
                    latency,
                    seeders if info_hash else None,
                    peers if info_hash else None,
                    completed if info_hash else None,
                    "Valid tracker scrape response",
                    "scrape",
                )
        if code in {401, 403}:
            return TrackerResult(
                url,
                "REVIEW",
                urllib.parse.urlsplit(url).scheme.upper(),
                latency,
                detail=f"HTTP {code}; private or access-controlled tracker",
                method="scrape",
            )
        # 404/405/HTML scrape endpoints are common; verify the announce endpoint.
        if announce_fallback or info_hash is None:
            return _http_announce_probe(url, info_hash, timeout)
        return TrackerResult(
            url,
            "REVIEW",
            urllib.parse.urlsplit(url).scheme.upper(),
            latency,
            detail=f"HTTP {code}; scrape unavailable and announce fallback is disabled",
            method="scrape",
        )
    # Non-standard paths can still be valid announce endpoints.
    if info_hash is None or announce_fallback:
        return _http_announce_probe(url, info_hash, timeout)
    return TrackerResult(
        url,
        "REVIEW",
        urllib.parse.urlsplit(url).scheme.upper(),
        detail="Cannot derive a scrape endpoint and announce fallback is disabled",
        method="syntax",
    )


def _udp_roundtrip(
    sock: socket.socket,
    address: tuple[Any, ...],
    payload: bytes,
    transaction: int,
    expected_action: int,
    timeout: float,
) -> tuple[bytes, int]:
    per_attempt = max(0.25, timeout / 2)
    last_error: Optional[Exception] = None
    for _ in range(2):
        started = time.monotonic()
        try:
            deadline = started + per_attempt
            sock.sendto(payload, address)
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise socket.timeout()
                sock.settimeout(remaining)
                data, sender = sock.recvfrom(65535)
                if sender[:2] != address[:2]:
                    continue
                if len(data) < 8:
                    continue
                action, received_transaction = struct.unpack("!II", data[:8])
                if received_transaction != transaction:
                    continue
                latency = round((time.monotonic() - started) * 1000)
                if action == 3:
                    message = data[8:].decode("utf-8", "replace") or "Unknown UDP tracker error"
                    raise InspectorError(message)
                if action != expected_action:
                    raise InspectorError(f"Unexpected UDP action {action}")
                return data, latency
        except socket.timeout as exc:
            last_error = exc
    raise TimeoutError(f"UDP tracker timed out after {timeout:.1f}s") from last_error


def _udp_connect(url: str, timeout: float) -> tuple[socket.socket, tuple[Any, ...], int, int]:
    parsed = urllib.parse.urlsplit(url)
    assert parsed.hostname is not None and parsed.port is not None
    started = time.monotonic()
    try:
        addresses = socket.getaddrinfo(parsed.hostname, parsed.port, 0, socket.SOCK_DGRAM)
    except socket.gaierror as exc:
        raise InspectorError(f"DNS lookup failed: {exc}") from exc
    last_error: Optional[Exception] = None
    for family, socktype, proto, _canonname, address in addresses:
        sock = socket.socket(family, socktype, proto)
        transaction = random.getrandbits(32)
        payload = struct.pack("!QII", 0x41727101980, 0, transaction)
        try:
            data, _ = _udp_roundtrip(sock, address, payload, transaction, 0, timeout)
            if len(data) < 16:
                raise InspectorError("Truncated UDP connect response")
            connection_id = struct.unpack("!Q", data[8:16])[0]
            latency = round((time.monotonic() - started) * 1000)
            return sock, address, connection_id, latency
        except (OSError, InspectorError, TimeoutError) as exc:
            last_error = exc
            sock.close()
    raise InspectorError(str(last_error or "Could not contact UDP tracker"))


def probe_udp_tracker(
    url: str,
    info_hash: Optional[bytes],
    timeout: float,
    announce_fallback: bool,
) -> TrackerResult:
    try:
        sock, address, connection_id, connect_latency = _udp_connect(url, timeout)
    except (OSError, InspectorError, TimeoutError) as exc:
        return TrackerResult(url, "FAILED", "UDP", detail=str(exc), method="connect")
    try:
        if info_hash is None:
            return TrackerResult(
                url,
                "WORKING",
                "UDP",
                connect_latency,
                detail="Valid BEP 15 UDP connect response",
                method="connect",
            )
        transaction = random.getrandbits(32)
        payload = struct.pack("!QII20s", connection_id, 2, transaction, info_hash)
        try:
            data, scrape_latency = _udp_roundtrip(
                sock, address, payload, transaction, 2, timeout
            )
            if len(data) < 20:
                raise InspectorError("Truncated UDP scrape response")
            seeders, completed, peers = struct.unpack("!III", data[8:20])
            return TrackerResult(
                url,
                "WORKING",
                "UDP",
                connect_latency + scrape_latency,
                seeders,
                peers,
                completed,
                "Valid BEP 15 UDP scrape response",
                "scrape",
            )
        except (InspectorError, TimeoutError, OSError) as scrape_error:
            if not announce_fallback:
                return TrackerResult(
                    url,
                    "REVIEW",
                    "UDP",
                    connect_latency,
                    detail=f"UDP tracker connected; scrape failed: {scrape_error}",
                    method="scrape",
                )
            transaction = random.getrandbits(32)
            peer_id = b"-TTI100-" + os.urandom(12)
            announce = struct.pack(
                "!QII20s20sQQQIIIiH",
                connection_id,
                1,
                transaction,
                info_hash,
                peer_id,
                0,
                0,
                0,
                3,  # stopped: do not join/register as an active peer
                0,
                random.getrandbits(32),
                0,  # request no peer addresses
                6881,
            )
            try:
                data, announce_latency = _udp_roundtrip(
                    sock, address, announce, transaction, 1, timeout
                )
                if len(data) < 20:
                    raise InspectorError("Truncated UDP announce response")
                _interval, peers, seeders = struct.unpack("!III", data[8:20])
                return TrackerResult(
                    url,
                    "WORKING",
                    "UDP",
                    connect_latency + announce_latency,
                    seeders,
                    peers,
                    None,
                    "Valid UDP stopped-announce response (scrape unavailable)",
                    "stopped announce",
                )
            except (InspectorError, TimeoutError, OSError) as announce_error:
                detail = f"UDP connected; scrape failed ({scrape_error}); announce failed ({announce_error})"
                lowered = str(announce_error).lower()
                status = "REVIEW" if any(word in lowered for word in MISSING_SWARM_WORDS) else "FAILED"
                return TrackerResult(
                    url,
                    status,
                    "UDP",
                    connect_latency,
                    detail=detail,
                    method="stopped announce",
                )
    finally:
        sock.close()


def probe_tracker(
    url: str,
    info_hash: Optional[bytes],
    timeout: float,
    announce_fallback: bool,
) -> TrackerResult:
    valid, reason, parsed = validate_tracker_url(url)
    if not valid or parsed is None:
        return TrackerResult(
            url,
            "INVALID",
            (parsed.scheme.upper() if parsed and parsed.scheme else "—"),
            detail=reason,
            method="syntax",
        )
    try:
        if parsed.scheme.lower() == "udp":
            return probe_udp_tracker(url, info_hash, timeout, announce_fallback)
        return probe_http_tracker(url, info_hash, timeout, announce_fallback)
    except (urllib.error.URLError, OSError, ssl.SSLError, InspectorError) as exc:
        return TrackerResult(
            url,
            "FAILED",
            parsed.scheme.upper(),
            detail=f"Network/protocol error: {exc}",
            method="probe",
        )
    except Exception as exc:  # A broken tracker must never crash the GUI batch.
        return TrackerResult(
            url,
            "FAILED",
            parsed.scheme.upper(),
            detail=f"Unexpected tracker response: {exc}",
            method="probe",
        )


def test_trackers(
    trackers: Iterable[str],
    *,
    info_hash: Optional[bytes] = None,
    timeout: float = 6.0,
    workers: int = 24,
    announce_fallback: bool = True,
    retry_failures: bool = True,
    cancel_event: Optional[threading.Event] = None,
    on_result: Optional[Callable[[TrackerResult], None]] = None,
) -> list[TrackerResult]:
    urls = dedupe_trackers(trackers)
    if not urls:
        return []
    cancel = cancel_event or threading.Event()
    results: list[TrackerResult] = []

    def run_probe(url: str) -> TrackerResult:
        first = probe_tracker(url, info_hash, timeout, announce_fallback)
        if not retry_failures or first.status != "FAILED" or cancel.is_set():
            return first
        second = probe_tracker(url, info_hash, timeout, announce_fallback)
        second.method = f"{second.method} · retry" if second.method else "retry"
        if second.status == "WORKING":
            second.detail = f"Recovered on automatic retry. {second.detail}"
        elif second.status == "FAILED":
            second.detail = f"Failed twice. {second.detail}"
        return second

    with concurrent.futures.ThreadPoolExecutor(
        max_workers=max(1, min(workers, 64)), thread_name_prefix="tracker"
    ) as pool:
        futures = {
            pool.submit(run_probe, url): url
            for url in urls
            if not cancel.is_set()
        }
        for future in concurrent.futures.as_completed(futures):
            if cancel.is_set():
                for pending in futures:
                    pending.cancel()
                break
            url = futures[future]
            try:
                result = future.result()
            except Exception as exc:
                result = TrackerResult(url, "FAILED", "—", detail=str(exc), method="batch")
            results.append(result)
            if on_result:
                on_result(result)
    return results
