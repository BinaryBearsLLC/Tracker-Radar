"""Validate the static page's local assets, anchors and public download contract."""
from html.parser import HTMLParser
from pathlib import Path
import sys
from urllib.parse import urlsplit
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from tracker_core import APP_VERSION
root = Path(__file__).resolve().parents[1] / 'site'
class Page(HTMLParser):
    def __init__(self):
        super().__init__(); self.ids = set(); self.refs = []; self.downloads = []; self.themes = []
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if 'id' in a:
            assert a['id'] not in self.ids, 'Duplicate HTML id'
            self.ids.add(a['id'])
        for attr in ('href', 'src'):
            if attr in a: self.refs.append(a[attr])
        if tag == 'html': assert a.get('lang') == 'en'
        if tag == 'img': assert 'alt' in a
        if tag == 'option': self.themes.append(a['value'])
page = Page(); page.feed((root / 'index.html').read_text())
for ref in page.refs:
    if ref.startswith('#'):
        assert ref[1:] in page.ids, ref
    elif not urlsplit(ref).scheme:
        assert (root / ref).is_file(), ref
    if '/releases/download/' in ref:
        assert f'/v{APP_VERSION}/' in ref, ref
        page.downloads.append(ref)
assert len(page.downloads) == 4
assert set(page.themes) == {'auto', 'dark', 'light'}
assert (root / '.nojekyll').is_file()
print('Site checked: English, local assets, anchors, theme options and three downloads plus checksums')
