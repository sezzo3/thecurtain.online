#!/usr/bin/env python3
"""Add shared article metrics, then regenerate complete publication sitemaps."""
import re
from update_sitemaps import ROOT, main as update_sitemaps

TAG = '<script defer src="/assets/article-metrics.js?v=20261125"></script>'
STYLE = '<link rel="stylesheet" href="/assets/article-experience.css?v=20261125">'


def main():
    added = 0
    for path in ROOT.glob('**/story/*/index.html'):
        text = path.read_text()
        if '<article' not in text or 'function gtag()' not in text:
            raise ValueError(f'Article or existing Google tag missing: {path}')
        if len(re.findall(r'</body>', text, flags=re.I)) != 1:
            raise ValueError(f'Unexpected article document: {path}')
        updated = text
        if '/assets/article-metrics.js' not in updated:
            updated = re.sub(r'</body>', TAG + '</body>', updated, count=1, flags=re.I)
        if '/assets/article-experience.css' not in updated:
            updated = re.sub(r'</head>', STYLE + '</head>', updated, count=1, flags=re.I)
        if updated != text:
            path.write_text(updated)
            added += 1
    print(f'Shared article metrics and mobile styles prepared on {added} pages')
    update_sitemaps()


if __name__ == '__main__':
    main()
