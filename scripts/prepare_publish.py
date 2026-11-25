#!/usr/bin/env python3
"""Add shared article metrics, then regenerate complete publication sitemaps."""
import re
from update_sitemaps import ROOT, main as update_sitemaps

TAG = '<script defer src="/assets/article-metrics.js?v=20261125"></script>'


def main():
    added = 0
    for path in ROOT.glob('**/story/*/index.html'):
        text = path.read_text()
        if '/assets/article-metrics.js' in text:
            continue
        if '<article' not in text or 'function gtag()' not in text:
            raise ValueError(f'Article or existing Google tag missing: {path}')
        if len(re.findall(r'</body>', text, flags=re.I)) != 1:
            raise ValueError(f'Unexpected article document: {path}')
        path.write_text(re.sub(r'</body>', TAG + '</body>', text, count=1, flags=re.I))
        added += 1
    print(f'Shared article metrics added to {added} pages')
    update_sitemaps()


if __name__ == '__main__':
    main()
