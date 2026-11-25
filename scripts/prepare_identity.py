#!/usr/bin/env python3
"""Keep real author attribution, publisher identity and feed discovery consistent.

Uses the standard library so the existing publication command also prepares new
articles. Article text, citations, canonical URLs and source dates are retained.
"""
import html
import json
import re
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote, urljoin
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
ORIGIN = "https://thecurtain.online"
AUTHOR_ID = ORIGIN + "/author/sezgin-baktiaya/#person"
PUBLISHER_ID = ORIGIN + "/#publisher"
ARTICLE_TYPES = {"NewsArticle", "Article", "BlogPosting"}
STYLE = '<link rel="stylesheet" href="/assets/publisher-transparency.css?v=20261125">'
JSON_TAG = re.compile(r'<script\b[^>]*type=[\'"]application/ld\+json[\'"][^>]*>(.*?)</script>', re.S | re.I)
META = re.compile(r'(<div\b[^>]*class="meta"[^>]*>)(.*?)(</div>)', re.S)
LABELS = {
    "en": {"author": "About the author", "editorial": "Editorial standards", "correction": "Report an error", "ai": "AI transparency", "updated": "Updated", "rss": "RSS feed", "language": "English", "subject": "Correction request", "article": "Article", "concern": "Concern", "source": "Supporting source"},
    "tr": {"author": "Yazar hakkında", "editorial": "Yayın ilkeleri", "correction": "Hata bildir", "ai": "Yapay zekâ şeffaflığı", "updated": "Güncelleme", "rss": "RSS akışı", "language": "Türkçe", "subject": "Düzeltme talebi", "article": "Haber", "concern": "Bildirim", "source": "Destekleyici kaynak"},
    "de": {"author": "Über den Autor", "editorial": "Redaktionelle Standards", "correction": "Fehler melden", "ai": "KI-Transparenz", "updated": "Aktualisiert", "rss": "RSS-Feed", "language": "Deutsch", "subject": "Korrekturanfrage", "article": "Artikel", "concern": "Hinweis", "source": "Beleg"},
    "es": {"author": "Sobre el autor", "editorial": "Normas editoriales", "correction": "Informar de un error", "ai": "Transparencia sobre IA", "updated": "Actualizado", "rss": "Canal RSS", "language": "Español", "subject": "Solicitud de corrección", "article": "Artículo", "concern": "Observación", "source": "Fuente de respaldo"},
}
SUPPORT_LEGACY = {
    "The Curtain is run by a single independent journalist — no newsroom, no sponsors, no salary. If this story was worth your time, please consider supporting the work that makes it possible.",
    "The Curtain, tek bir bağımsız gazeteci tarafından yürütülüyor — ne bir haber odası, ne sponsorlar, ne de bir maaş var. Bu haber vaktinize değdiyse, bu işi mümkün kılan çalışmayı desteklemeyi düşünün.",
    "The Curtain wird von einem einzelnen unabhängigen Journalisten betrieben — ohne Redaktion, ohne Sponsoren, ohne Gehalt. Wenn diese Geschichte Ihre Zeit wert war, unterstützen Sie bitte die Arbeit, die sie möglich macht.",
    "The Curtain lo lleva un solo periodista independiente: sin redacción, sin patrocinadores y sin salario. Si esta historia valió su tiempo, considere apoyar el trabajo que la hace posible.",
}
SUPPORT = {
    "en": "The Curtain is independently owned and edited by Sezgin Baktiaya. If you value this reporting, you can support the publication.",
    "tr": "The Curtain, Sezgin Baktiaya’nın sahibi ve editörü olduğu bağımsız bir yayındır. Bu haberciliğe değer veriyorsanız yayını destekleyebilirsiniz.",
    "de": "The Curtain ist eine unabhängige Publikation im Eigentum und unter der redaktionellen Leitung von Sezgin Baktiaya. Wenn Sie diese Berichterstattung schätzen, können Sie die Publikation unterstützen.",
    "es": "The Curtain es una publicación independiente propiedad de Sezgin Baktiaya, quien también es su editor. Si valoras este periodismo, puedes apoyar la publicación.",
}


def language_for(path):
    first = path.relative_to(ROOT).parts[0]
    return first if first in {"tr", "de", "es"} else "en"


def local(language, suffix=""):
    return ("/" if language == "en" else "/" + language + "/") + suffix


def person(language):
    return {"@type": "Person", "@id": AUTHOR_ID, "name": "Sezgin Baktiaya",
            "url": ORIGIN + local(language, "author/sezgin-baktiaya/"),
            "image": ORIGIN + "/assets/sezgin-baktiaya.jpg",
            "jobTitle": "Founder and Editor", "worksFor": {"@id": PUBLISHER_ID}}


def publisher(language):
    return {"@type": "NewsMediaOrganization", "@id": PUBLISHER_ID,
            "name": "The Curtain", "url": ORIGIN + "/",
            "logo": {"@type": "ImageObject", "url": ORIGIN + "/favicon.svg"},
            "foundingDate": "2026-10-10",
            "foundingLocation": {"@type": "Place", "name": "London, United Kingdom"},
            "founder": {"@id": AUTHOR_ID},
            "publishingPrinciples": ORIGIN + local(language, "editorial/"),
            "ethicsPolicy": ORIGIN + local(language, "editorial/"),
            "correctionsPolicy": ORIGIN + local(language, "blog/how-we-handle-corrections/"),
            "ownershipFundingInfo": ORIGIN + local(language, "about/")}


def json_script(value):
    return '<script type="application/ld+json">' + json.dumps(value, ensure_ascii=False).replace("</", "<\\/") + '</script>'


class Metadata(HTMLParser):
    def __init__(self, text):
        super().__init__(convert_charrefs=True)
        self.canonical = None
        self.description = None
        self.robots = ""
        self.heading = ""
        self.in_heading = False
        self.cover = None
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "link" and attrs.get("rel") == "canonical":
            self.canonical = attrs.get("href")
        if tag == "meta" and attrs.get("name") == "description":
            self.description = attrs.get("content")
        if tag == "meta" and attrs.get("name") == "robots":
            self.robots = attrs.get("content", "")
        if tag == "h1":
            self.in_heading = True
        if tag == "img" and "/covers/" in attrs.get("src", "") and not self.cover:
            self.cover = urljoin(ORIGIN, attrs["src"])

    def handle_endtag(self, tag):
        if tag == "h1":
            self.in_heading = False

    def handle_data(self, value):
        if self.in_heading:
            self.heading += value


def normalize_schema(value, language, page):
    if isinstance(value, list):
        return [normalize_schema(v, language, page) for v in value]
    if not isinstance(value, dict):
        return value
    if value.get("@type") in ARTICLE_TYPES:
        # Dates are deliberately not generated or refreshed by this migration.
        value.update(author=person(language), publisher=publisher(language), inLanguage=language)
        if page.heading.strip():
            value["headline"] = " ".join(page.heading.split())
        if page.description:
            value["description"] = page.description
        if not value.get("image") and page.cover:
            value["image"] = [page.cover]
    elif value.get("@type") == "NewsMediaOrganization" and value.get("name") == "The Curtain":
        value.update(publisher(language))
    elif value.get("@type") == "Person" and value.get("name") == "Sezgin Baktiaya":
        value.update(person(language))
    if "@graph" in value:
        value["@graph"] = normalize_schema(value["@graph"], language, page)
    return value


def article_schema(text):
    for match in JSON_TAG.finditer(text):
        value = json.loads(match[1])
        if isinstance(value, dict) and value.get("@type") in ARTICLE_TYPES:
            return value
    return None


def editorial_links(language, canonical):
    d = LABELS[language]
    body = d["article"] + ": " + canonical + "\n\n" + d["concern"] + ":\n\n" + d["source"] + ":\n"
    mail = "mailto:hello@thecurtain.online?subject=" + quote(d["subject"]) + "&body=" + quote(body)
    links = [(local(language, "author/sezgin-baktiaya/"), d["author"]),
             (local(language, "editorial/"), d["editorial"]),
             (mail, d["correction"]), (local(language, "ai-transparency/"), d["ai"])]
    return '<nav class="curtain-editorial-links" aria-label="' + html.escape(d["editorial"], quote=True) + '">' + "".join('<a href="' + html.escape(href, quote=True) + '">' + html.escape(label) + '</a>' for href, label in links) + '</nav>'


def prepare_page(path):
    text = original = path.read_text()
    if path.name != "index.html":
        return False
    language = language_for(path)
    page = Metadata(text)
    if not page.canonical or "noindex" in page.robots:
        return False
    # Keep the owner's advertising, but never put a sponsored click target over
    # a source box. Move those hidden overlays into an explicitly labelled slot.
    overlays = []
    def move_overlay(match):
        if 'position:absolute' in re.sub(r'\s+', '', match[0]):
            overlays.append(True)
            return ""
        return match[0]
    text = re.sub(r'<a\b[^>]*href="https?://(?:www\.)?asiafilm\.org/[^\"]*"[^>]*>.*?</a>', move_overlay, text, flags=re.S)
    def clean_source_box(match):
        def unlink_heading(ad):
            overlays.append(True)
            return ad[1]
        return re.sub(r'<a\b[^>]*href="https?://(?:www\.)?asiafilm\.org/[^\"]*"[^>]*>(.*?)</a>', unlink_heading, match[0], flags=re.S)
    text = re.sub(r'<section\b[^>]*class="sourcebox"[^>]*>.*?</section>', clean_source_box, text, flags=re.S)
    if overlays and 'class="curtain-sponsored-link"' not in text:
        ad_label = {"en": "Advertisement", "tr": "Reklam", "de": "Werbung", "es": "Publicidad"}[language]
        link_label = {"en": "Sponsored link", "tr": "Sponsorlu bağlantı", "de": "Gesponserter Link", "es": "Enlace patrocinado"}[language]
        placement = '<aside class="curtain-sponsored-link" aria-label="' + ad_label + '"><span>' + ad_label + '</span><a href="https://asiafilm.org/4/945308c7374985c3a8b500ba9668eebe" rel="sponsored nofollow noopener noreferrer" target="_blank">' + link_label + '</a></aside>'
        text = text.replace('</article>', placement + '</article>', 1)
    text = JSON_TAG.sub(lambda m: json_script(normalize_schema(json.loads(m[1]), language, page)), text)
    schema = article_schema(text)
    if schema:
        author = '<a class="curtain-author" rel="author" href="' + local(language, "author/sezgin-baktiaya/") + '">Sezgin Baktiaya</a>'

        def byline(match):
            content = match[2]
            if "The Curtain Editorial" in content:
                content = content.replace("The Curtain Editorial", author)
            elif 'class="curtain-author"' not in content:
                content = author + " · " + content
            published = schema.get("datePublished", "")
            if published and '<time' not in content:
                content = content.replace(published[:10], '<time datetime="' + html.escape(published, quote=True) + '">' + published[:10] + '</time>', 1)
            modified = schema.get("dateModified", "")
            if modified and modified[:10] != published[:10] and modified[:10] not in re.sub('<[^>]+>', '', content):
                content += ' · <span class="curtain-updated">' + LABELS[language]["updated"] + ': <time datetime="' + html.escape(modified, quote=True) + '">' + modified[:10] + '</time></span>'
            return match[1] + content + match[3]

        text, count = META.subn(byline, text, count=1)
        if count != 1:
            raise ValueError(f"Cannot identify article byline: {path}")
        if 'class="curtain-editorial-links"' not in text:
            text = text.replace('</article>', editorial_links(language, page.canonical) + '</article>', 1)
    elif '"@type": "NewsMediaOrganization"' not in text:
        identity = {"@context": "https://schema.org", "@graph": [publisher(language), person(language),
                    {"@type": "WebSite", "@id": ORIGIN + "/#website", "url": ORIGIN + "/", "name": "The Curtain", "publisher": {"@id": PUBLISHER_ID}}]}
        text = text.replace('</head>', json_script(identity) + '</head>')

    # Cards already link to the article, so their byline stays plain text.
    text = text.replace("The Curtain Editorial", "Sezgin Baktiaya")
    for old_support in SUPPORT_LEGACY:
        text = text.replace(old_support, SUPPORT[language])

    # Keep one Twitter card declaration; the repeated copies were identical.
    seen_card = False

    def deduplicate_card(match):
        nonlocal seen_card
        if seen_card:
            return ""
        seen_card = True
        return match[0]

    text = re.sub(r'<meta\b[^>]*name="twitter:card"[^>]*>', deduplicate_card, text)
    if '/assets/publisher-transparency.css' not in text:
        text = text.replace('</head>', STYLE + '</head>')
    if 'type="application/rss+xml"' not in text:
        text = text.replace('</head>', '<link rel="alternate" type="application/rss+xml" title="The Curtain — ' + LABELS[language]["language"] + '" href="' + ORIGIN + local(language, "rss.xml") + '"></head>')

    # Add identity and RSS destinations inside the existing Site footer column.
    footer = re.search(r'<footer\b.*?</footer>', text, re.S)
    if footer:
        fragment = footer[0]
        about = re.search(r'<a\b[^>]*href="' + re.escape(local(language, "about/")) + r'"[^>]*>.*?</a>', fragment, re.S)
        if about:
            additions = ""
            for suffix, label in [("author/sezgin-baktiaya/", "Sezgin Baktiaya"), ("ai-transparency/", LABELS[language]["ai"]), ("rss.xml", LABELS[language]["rss"])]:
                if 'href="' + local(language, suffix) + '"' not in fragment:
                    # Reuse the real footer's scoped attributes for existing layout.
                    attrs = " ".join(re.findall(r'data-astro-cid-[\w-]+(?:="[^"]*")?', about[0].split('>')[0]))
                    additions += '<a href="' + local(language, suffix) + '" ' + attrs + '>' + html.escape(label) + '</a>'
            fragment = fragment[:about.end()] + additions + fragment[about.end():]
            text = text[:footer.start()] + fragment + text[footer.end():]
    if text != original:
        path.write_text(text)
        return True
    return False


def build_feeds():
    from update_sitemaps import Page, url_path
    atom = "http://www.w3.org/2005/Atom"
    dc = "http://purl.org/dc/elements/1.1/"
    ET.register_namespace("atom", atom)
    ET.register_namespace("dc", dc)
    for language in LABELS:
        prefix = ROOT / ("" if language == "en" else language)
        rss = ET.Element("rss", {"version": "2.0"})
        channel = ET.SubElement(rss, "channel")
        ET.SubElement(channel, "title").text = "The Curtain — " + LABELS[language]["language"]
        ET.SubElement(channel, "link").text = ORIGIN + local(language)
        ET.SubElement(channel, "description").text = "The Curtain — " + LABELS[language]["language"]
        ET.SubElement(channel, "language").text = "en-gb" if language == "en" else language
        ET.SubElement(channel, "managingEditor").text = "hello@thecurtain.online (Sezgin Baktiaya)"
        ET.SubElement(channel, "ttl").text = "60"
        ET.SubElement(channel, f"{{{atom}}}link", {"href": ORIGIN + local(language, "rss.xml"), "rel": "self", "type": "application/rss+xml"})
        for url in Page(prefix / "index.html").story_links:
            article = article_schema(url_path(url).read_text())
            if not article:
                raise ValueError(f"No article metadata for feed: {url}")
            item = ET.SubElement(channel, "item")
            ET.SubElement(item, "title").text = html.unescape(article["headline"])
            ET.SubElement(item, "link").text = url
            ET.SubElement(item, "guid", {"isPermaLink": "true"}).text = url
            ET.SubElement(item, "description").text = html.unescape(article.get("description", ""))
            ET.SubElement(item, f"{{{dc}}}creator").text = "Sezgin Baktiaya"
            # RSS pubDate requires an exact RFC 822 timestamp. Source articles
            # often have only a calendar date; retain it without inventing time.
            if article.get("datePublished"):
                ET.SubElement(item, f"{{{dc}}}date").text = article["datePublished"]
        ET.indent(rss, space="  ")
        (prefix / "rss.xml").write_bytes(ET.tostring(rss, encoding="UTF-8", xml_declaration=True) + b"\n")


def main():
    changed = sum(prepare_page(path) for path in sorted(ROOT.rglob('*.html')))
    build_feeds()
    print(f"Author identity, publisher metadata and RSS discovery prepared on {changed} pages")


if __name__ == "__main__":
    main()
