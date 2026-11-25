#!/usr/bin/env python3
"""Build complete language sitemaps from canonical, indexable article files.

The homepage's 20-story limit must never limit sitemap coverage.
Run after publishing: python3 scripts/update_sitemaps.py
"""
import argparse
import json
from datetime import date, datetime, timedelta
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin
from zoneinfo import ZoneInfo
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
ORIGIN = "https://thecurtain.online"
SM = "http://www.sitemaps.org/schemas/sitemap/0.9"
NEWS = "http://www.google.com/schemas/sitemap-news/0.9"
ET.register_namespace("", SM)
ET.register_namespace("news", NEWS)


class Page(HTMLParser):
    def __init__(self, path):
        super().__init__(convert_charrefs=True)
        self.canonical = None
        self.robots = ""
        self.schemas = []
        self.story_links = []
        self.json_buffer = None
        self.feed(path.read_text())

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "link" and attrs.get("rel") == "canonical":
            self.canonical = attrs.get("href")
        if tag == "meta" and attrs.get("name", "").lower() == "robots":
            self.robots = attrs.get("content", "").lower()
        if tag == "a" and {"card", "hero"}.intersection((attrs.get("class") or "").split()):
            href = attrs.get("href") or ""
            if "/story/" in href:
                self.story_links.append(urljoin(ORIGIN, href))
        if tag == "script" and attrs.get("type") == "application/ld+json":
            self.json_buffer = ""

    def handle_data(self, text):
        if self.json_buffer is not None:
            self.json_buffer += text

    def handle_endtag(self, tag):
        if tag == "script" and self.json_buffer is not None:
            value = json.loads(self.json_buffer)
            self.schemas.extend(value if isinstance(value, list) else [value])
            self.json_buffer = None


def url_for(path):
    relative = path.parent.relative_to(ROOT).as_posix()
    return ORIGIN + ("/" if relative == "." else "/" + relative + "/")


def url_path(url):
    if not url.startswith(ORIGIN + "/"):
        raise ValueError(f"Unexpected sitemap origin: {url}")
    return ROOT / url[len(ORIGIN):].strip("/") / "index.html"


def emit(path, tree, check, stale):
    ET.indent(tree, space="  ")
    document = ET.tostring(tree, encoding="UTF-8", xml_declaration=True) + b"\n"
    if check:
        actual = ET.parse(path)
        ET.indent(actual, space="  ")
        if ET.tostring(actual.getroot(), encoding="UTF-8", xml_declaration=True) + b"\n" != document:
            stale.append(path.name)
        return
    path.write_bytes(document)


def verify_navigation(prefix):
    home = ROOT / prefix / "index.html"
    archive = ROOT / prefix / "archive/index.html"
    for path in (home, archive):
        links = Page(path).story_links
        if len(links) != len(set(links)):
            raise ValueError(f"Repeated story cards: {path.relative_to(ROOT)}")
        if path == home and len(links) != 20:
            raise ValueError(f"Expected 20 story cards: {path.relative_to(ROOT)}")
        for url in links:
            if not url_path(url).is_file():
                raise ValueError(f"Story card points to a retired or missing page: {url}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", type=date.fromisoformat,
                        default=datetime.now(ZoneInfo("Europe/London")).date())
    parser.add_argument("--check", action="store_true", help="verify existing sitemaps without writing")
    args = parser.parse_args()
    articles = []
    summary = {}
    stale = []
    for language in ("en", "tr", "de", "es"):
        prefix = "" if language == "en" else language
        verify_navigation(prefix)
        sitemap_path = ROOT / ("sitemap-0.xml" if language == "en" else f"sitemap-{language}.xml")
        old = ET.parse(sitemap_path).getroot()
        previous = {item.findtext(f"{{{SM}}}loc"): item.findtext(f"{{{SM}}}lastmod") for item in old}
        # Preserve the established non-article URL scope; app policies are separate.
        urls = {url for url in previous if "/story/" not in url}
        # Include the publisher's public identity and AI disclosure pages when
        # present; keep unrelated app policies outside the news sitemap scope.
        for relative in ("author/sezgin-baktiaya/index.html", "ai-transparency/index.html"):
            institutional = ROOT / prefix / relative
            if institutional.is_file():
                urls.add(url_for(institutional))
        metadata = {}
        for path in sorted((ROOT / prefix / "story").glob("*/index.html")):
            page = Page(path)
            if "noindex" in page.robots:
                continue
            url = url_for(path)
            if page.canonical != url:
                raise ValueError(f"Article canonical mismatch: {path}")
            urls.add(url)
            metadata[url] = page
            for schema in page.schemas:
                if schema.get("@type") == "NewsArticle":
                    articles.append((language, url, schema))
        document = ET.Element(f"{{{SM}}}urlset")
        for url in sorted(urls):
            path = url_path(url)
            page = metadata.get(url) or Page(path)
            if page.canonical != url or "noindex" in page.robots:
                raise ValueError(f"Non-indexable sitemap URL: {url}")
            element = ET.SubElement(document, f"{{{SM}}}url")
            ET.SubElement(element, f"{{{SM}}}loc").text = url
            modified = next((s.get("dateModified") for s in page.schemas if s.get("dateModified")), None)
            modified = modified or previous.get(url)
            if modified:
                ET.SubElement(element, f"{{{SM}}}lastmod").text = modified
        emit(sitemap_path, document, args.check, stale)
        summary[language] = {"urls": len(urls), "articles": len(metadata),
                             "added_articles": len(set(metadata) - set(previous))}

    news_path = ROOT / "sitemap-news.xml"
    old_news = ET.parse(news_path).getroot()
    publication_name = old_news.findtext(f".//{{{NEWS}}}name") or "The Curtain"
    document = ET.Element(f"{{{SM}}}urlset")
    count = 0
    for language, url, schema in sorted(articles, key=lambda row: row[1]):
        published = schema.get("datePublished", "")
        published_day = date.fromisoformat(published[:10])
        # With date-only source dates, include today and yesterday, never older news.
        if not args.date - timedelta(days=1) <= published_day <= args.date:
            continue
        element = ET.SubElement(document, f"{{{SM}}}url")
        ET.SubElement(element, f"{{{SM}}}loc").text = url
        news = ET.SubElement(element, f"{{{NEWS}}}news")
        publication = ET.SubElement(news, f"{{{NEWS}}}publication")
        ET.SubElement(publication, f"{{{NEWS}}}name").text = publication_name
        ET.SubElement(publication, f"{{{NEWS}}}language").text = language
        ET.SubElement(news, f"{{{NEWS}}}publication_date").text = published
        ET.SubElement(news, f"{{{NEWS}}}title").text = schema["headline"]
        count += 1
    if count > 1000:
        raise ValueError("News sitemap must be split before exceeding 1000 URLs")
    emit(news_path, document, args.check, stale)
    summary["news"] = {"urls": count, "date": args.date.isoformat()}
    if stale:
        raise SystemExit("Regenerate stale sitemaps with scripts/prepare_publish.py: " + ", ".join(stale))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
