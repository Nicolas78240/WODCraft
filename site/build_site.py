"""Builds public/: / in English and /fr/ in French, from index.html (French) and en.json.

Each language gets static HTML (crawlers see the text without running JavaScript), its own title,
description, canonical and hreflang links, Open Graph and JSON-LD; plus sitemap.xml, robots.txt, 404.
Needs beautifulsoup4 at build time only:  python build_site.py
"""

import datetime
import html
import json
import re
import shutil
from pathlib import Path

from bs4 import BeautifulSoup

HERE = Path(__file__).parent
OUT = HERE / "public"
SITE = "https://wodcraft.dev"
REPO = "https://github.com/Nicolas78240/WODCraft"
ASSETS = ["styles.css", "main.js", "data.js", "i18n.js", "favicon.svg", "og-en.png", "og-fr.png", "py"]

META = {
    "en": {
        "path": "/",
        "title": "WODCraft — a language to write and check WODs",
        "description": "Write a WOD the way it goes on the whiteboard. The WODCraft compiler checks movements, "
        "units and plausibility, and turns it into JSON for timers, apps and AI agents. Open source.",
        "og_title": "WODCraft — write the WOD like on the whiteboard",
        "og_locale": "en_US",
        "keywords": "WOD, CrossFit, functional fitness, workout language, DSL, compiler, AMRAP, EMOM, For time, workout JSON",
    },
    "fr": {
        "path": "/fr/",
        "title": "WODCraft — le langage pour écrire et vérifier vos WODs",
        "description": "Écrivez un WOD comme au tableau blanc. Le compilateur WODCraft vérifie mouvements, unités "
        "et plausibilité, et le transforme en JSON pour les chronos, les applications et les agents IA. Open source.",
        "og_title": "WODCraft — le WOD s'écrit comme au tableau",
        "og_locale": "fr_FR",
        "keywords": "WOD, CrossFit, fitness fonctionnel, langage d'entraînement, DSL, compilateur, AMRAP, EMOM, For time, JSON",
    },
}

# First visit to / with a French browser (and no remembered choice): go to /fr/. Crawlers stay on /.
REDIRECT = """<script>(function(){try{var q=new URLSearchParams(location.search).get("lang"),s=null;
try{s=localStorage.getItem("wodcraft-lang")}catch(e){}
var l=q||s||((navigator.languages&&navigator.languages[0])||navigator.language||"");
if(/^fr\\b/i.test(l))location.replace("/fr/"+location.hash)}catch(e){}})();</script>"""


t_credit = {
    "en": "A collaboration: Nicolas Caussin set the course and had the idea, orchestrated, corrected and approved; most of the writing was done by Claude (Anthropic) with Claude Code.",
    "fr": "Une collaboration : Nicolas Caussin a donné le cap et l'idée, orchestré, corrigé et validé ; l'essentiel de l'écriture a été réalisé par Claude (Anthropic) avec Claude Code.",
}


def head(lang: str) -> str:
    m = META[lang]
    url = SITE + m["path"]
    e = lambda s: html.escape(s, quote=True)
    ld = {
        "@context": "https://schema.org",
        "@graph": [
            {
                "@type": "SoftwareApplication",
                "name": "WODCraft",
                "url": url,
                "description": m["description"],
                "applicationCategory": "DeveloperApplication",
                "operatingSystem": "macOS, Linux, Windows, iOS",
                "softwareVersion": "1.1",
                "license": "https://www.apache.org/licenses/LICENSE-2.0",
                "offers": {"@type": "Offer", "price": "0", "priceCurrency": "EUR"},
                "author": {"@type": "Person", "name": "Nicolas Caussin"},
                "creditText": t_credit[lang],
                "sameAs": [REPO],
                "inLanguage": lang,
            },
            {"@type": "WebSite", "name": "WODCraft", "url": SITE + "/", "inLanguage": ["en", "fr"]},
        ],
    }
    lines = [
        f"<title>{e(m['title'])}</title>",
        f'<meta name="description" content="{e(m["description"])}">',
        f'<meta name="keywords" content="{e(m["keywords"])}">',
        '<meta name="theme-color" content="#0e0e0c">',
        '<meta name="robots" content="index, follow, max-image-preview:large">',
        f'<link rel="canonical" href="{url}">',
        f'<link rel="alternate" hreflang="en" href="{SITE}/">',
        f'<link rel="alternate" hreflang="fr" href="{SITE}/fr/">',
        f'<link rel="alternate" hreflang="x-default" href="{SITE}/">',
        '<meta property="og:type" content="website">',
        '<meta property="og:site_name" content="WODCraft">',
        f'<meta property="og:url" content="{url}">',
        f'<meta property="og:title" content="{e(m["og_title"])}">',
        f'<meta property="og:description" content="{e(m["description"])}">',
        f'<meta property="og:image" content="{SITE}/og-{lang}.png">',
        '<meta property="og:image:width" content="1200">',
        '<meta property="og:image:height" content="630">',
        f'<meta property="og:locale" content="{m["og_locale"]}">',
        f'<meta property="og:locale:alternate" content="{META["fr" if lang == "en" else "en"]["og_locale"]}">',
        '<meta name="twitter:card" content="summary_large_image">',
        f'<meta name="twitter:title" content="{e(m["og_title"])}">',
        f'<meta name="twitter:description" content="{e(m["description"])}">',
        f'<meta name="twitter:image" content="{SITE}/og-{lang}.png">',
        '<link rel="apple-touch-icon" href="/favicon.svg">',
        f'<script type="application/ld+json">{json.dumps(ld, ensure_ascii=False)}</script>',
    ]
    if lang == "en":
        lines.insert(0, REDIRECT)
    return "\n".join(lines)


def prefill(soup: BeautifulSoup, lang: str, data: dict) -> None:
    """Static text in the code and board panes, so the page reads without JavaScript."""
    fill = {
        "#heroCode": data["sources"]["fran"],
        "#heroBoard": data["boards"]["fran"],
        "#fmtCode": data["sources"]["fran"],
        "#fmtBoard": data["boards"]["fran"],
        "#profileBoard": data["fran"][f"men-rx-kg-{lang}"],
        "#diagCode": data["sources"]["bad" if lang == "fr" else "tuesday"],
        "#playSrc": data["sources"]["fran"],
    }
    for sel, text in fill.items():
        el = soup.select_one(sel)
        el.clear()
        el.append(text)


def translate(soup: BeautifulSoup, en: dict) -> None:
    for key, val in en.items():
        if key == "title" or key.startswith("meta"):
            continue
        sel, _, attr = key.partition("@")
        els = soup.select(sel)
        assert els, f"en.json: nothing matches {sel!r}"
        for el in els:
            if attr:
                el[attr] = val
            else:
                el.clear()
                el.append(BeautifulSoup(val, "html.parser"))
    label = soup.select_one(".play-bar label")
    label.contents[0].replace_with("Example\n          ")
    soup.html["lang"] = "en"


def page(lang: str, template: str, en: dict, data: dict) -> str:
    soup = BeautifulSoup(template.replace("<!--HEAD-->", head(lang)), "html.parser")
    if lang == "en":
        translate(soup, en)
    prefill(soup, lang, data)
    return str(soup)


def sitemap() -> str:
    today = datetime.date.today().isoformat()
    alt = "".join(
        f'\n    <xhtml:link rel="alternate" hreflang="{h}" href="{SITE}{p}"/>'
        for h, p in [("en", "/"), ("fr", "/fr/"), ("x-default", "/")]
    )
    urls = "".join(f"\n  <url>\n    <loc>{SITE}{p}</loc>{alt}\n    <lastmod>{today}</lastmod>\n  </url>" for p in ["/", "/fr/"])
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">'
        f"{urls}\n</urlset>\n"
    )


NOT_FOUND = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>404 — WODCraft</title><meta name="robots" content="noindex"><link rel="icon" href="/favicon.svg">
<link href="https://fonts.googleapis.com/css2?family=Big+Shoulders+Display:wght@900&family=Instrument+Sans:wght@400;600&display=swap" rel="stylesheet">
<style>body{margin:0;min-height:100vh;display:grid;place-items:center;background:#0e0e0c;color:#f2efe6;font:16px/1.6 "Instrument Sans",sans-serif;text-align:center;padding:16px}
h1{font:900 clamp(64px,16vw,160px)/.9 "Big Shoulders Display",Impact,sans-serif;margin:0;color:#e5383b}a{color:#f2efe6}</style></head>
<body><main><h1>No rep.</h1><p>This page does not exist. · Cette page n'existe pas.</p>
<p><a href="/">wodcraft.dev</a> · <a href="/fr/">Version française</a></p></main></body></html>
"""


def main() -> None:
    template = (HERE / "index.html").read_text()
    en = json.loads((HERE / "en.json").read_text())
    data = json.loads((HERE / "data.js").read_text()[len("window.WOD = ") : -2])
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "fr").mkdir(parents=True)
    for a in ASSETS:
        src = HERE / a
        (shutil.copytree if src.is_dir() else shutil.copy)(src, OUT / a)
    (OUT / "index.html").write_text(page("en", template, en, data))
    (OUT / "fr" / "index.html").write_text(page("fr", template, en, data))
    (OUT / "sitemap.xml").write_text(sitemap())
    (OUT / "robots.txt").write_text(f"User-agent: *\nAllow: /\n\nSitemap: {SITE}/sitemap.xml\n")
    (OUT / "404.html").write_text(NOT_FOUND)
    print("public/:", ", ".join(sorted(str(p.relative_to(OUT)) for p in OUT.rglob("*") if p.is_file() and "py" not in p.parts)))


if __name__ == "__main__":
    main()
