#!/usr/bin/env python3
"""Generate personalized static share-preview pages in /i/ for each guest name.

Reads the guest list straight out of index.html's ALLOWED_DEAR_NAMES array (so
there is one source of truth), slugifies each name with the same rules as the
site's client-side slugifyGuestName(), and writes /i/<slug>.html — a page whose
og:/twitter: meta tags read "Dəvətli: <Name>" for link-preview crawlers, and
redirects a real visitor into the main experience via ?dear=<Name> — via a JS
location.replace() only, deliberately NOT a <meta http-equiv="refresh"> (many
crawlers, including Facebook's, follow an instant 0-second meta-refresh like a
real redirect and read the *target* page's tags instead of this page's own).

Also renders a personalized 1200x630 og:image per guest (via ImageMagick),
reusing the same background/couple-illustration style as the site's generic
og-image.jpg but with the guest's own name as the headline, instead of every
guest page sharing that one generic banner.

Run manually after editing the guest list in index.html:
    python3 scripts/generate_guest_pages.py

Requires ImageMagick (`magick`) and the Noto Serif / Montserrat fonts used
elsewhere in this repo's og-image generation to be installed locally.
"""
import re
import pathlib
import html
import subprocess
import urllib.parse

ROOT = pathlib.Path(__file__).resolve().parent.parent
INDEX = ROOT / "index.html"
OUT_DIR = ROOT / "i"
OG_IMAGE_DIR = OUT_DIR / "og"
COUPLE_ASSET = ROOT / "assets" / "couple-illustration.png"

SITE_URL = "https://aser-turkan.love"

SERIF_FONT = "/usr/share/fonts/google-noto-vf/NotoSerif[wght].ttf"
SANS_FONT = "/usr/share/fonts/julietaula-montserrat-fonts/Montserrat-Regular.otf"
SANS_SB_FONT = "/usr/share/fonts/julietaula-montserrat-fonts/Montserrat-SemiBold.otf"

# must mirror GUEST_SLUG_OVERRIDES / GUEST_SLUG_MAP in index.html's <script>
SLUG_OVERRIDES = {"თიკა": "tika"}
SLUG_MAP = {"ə": "e", "ı": "i", "ö": "o", "ü": "u", "ş": "s", "ç": "c", "ğ": "g"}


def slugify(name: str) -> str:
    if name in SLUG_OVERRIDES:
        return SLUG_OVERRIDES[name]
    # plain .lower() turns 'İ' into 'i' + a combining dot-above (U+0307)
    # rather than the Turkish/Azerbaijani locale's plain 'i' — but that
    # stray combining mark isn't a-z0-9, so the final strip below removes
    # it anyway, landing on the same result as JS's toLocaleLowerCase('az')
    lowered = name.lower()
    slug = "".join(SLUG_MAP.get(ch, ch) for ch in lowered)
    return re.sub(r"[^a-z0-9]", "", slug)


def extract_names() -> list[str]:
    text = INDEX.read_text(encoding="utf-8")
    m = re.search(r"const ALLOWED_DEAR_NAMES\s*=\s*\[(.*?)\]", text, re.S)
    if not m:
        raise SystemExit("could not find ALLOWED_DEAR_NAMES in index.html")
    return re.findall(r"'([^']+)'", m.group(1))


PAGE_TEMPLATE = """<!doctype html>
<html lang="az">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Asər &amp; Türkan — Dəvətli: {name_html}</title>
<meta name="description" content="Dəvətli: {name_html}. Toy tarixi, məkan və bütün detallarla tanış olun.">
<meta property="og:site_name" content="Asər & Türkan">
<meta property="og:title" content="Asər &amp; Türkan — Dəvətli: {name_html}">
<meta property="og:description" content="Dəvətli: {name_html}. Toy tarixi, məkan və bütün detallarla tanış olun.">
<meta property="og:type" content="website">
<meta property="og:url" content="{page_url}">
<meta property="og:image" content="{og_image}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="Asər &amp; Türkan — Dəvətli: {name_html}">
<meta name="twitter:description" content="Dəvətli: {name_html}. Toy tarixi, məkan və bütün detallarla tanış olun.">
<link rel="icon" type="image/png" sizes="32x32" href="/favicon-32x32.png">
<link rel="icon" type="image/png" sizes="16x16" href="/favicon-16x16.png">
<link rel="shortcut icon" href="/favicon.ico">
<style>
  :root{{ color-scheme:dark; }}
  body{{
    margin:0; min-height:100vh; display:flex; align-items:center; justify-content:center;
    background:linear-gradient(180deg, #241a34 0%, #1c1428 55%, #150e20 100%);
    color:#f3e7d8; font-family:Georgia, 'Times New Roman', serif; text-align:center;
    padding:2rem; box-sizing:border-box;
  }}
  .eyebrow{{ font-size:0.7rem; letter-spacing:0.3em; text-transform:uppercase; color:#d9c9b4; margin:0 0 0.6rem; }}
  h1{{ font-size:1.8rem; font-style:italic; font-weight:500; color:#f2d38f; margin:0 0 0.8rem; }}
  p{{ margin:0.3rem 0; color:#d9c9b4; }}
  a{{ display:inline-block; margin-top:1.5rem; padding:0.6rem 1.3rem; border:1px solid rgba(211,164,87,0.4); border-radius:999px; color:#f3e7d8; text-decoration:none; font-size:0.85rem; }}
</style>
</head>
<body>
  <main>
    <p class="eyebrow">Dəvətli</p>
    <h1>{name_html}</h1>
    <p>Asər &amp; Türkan</p>
    <p>29 Avqust · 18:00 · Bolnisi, Dzveli Kveshi</p>
    <a href="{redirect_url}">Dəvətnaməni açın →</a>
  </main>
  <script>location.replace({redirect_url_js});</script>
</body>
</html>
"""


def build_page(name: str, slug: str, og_image_url: str) -> str:
    name_html = html.escape(name)
    page_url = f"{SITE_URL}/i/{slug}.html"
    redirect_url = f"/?dear={urllib.parse.quote(name)}"
    return PAGE_TEMPLATE.format(
        name_html=name_html,
        page_url=page_url,
        og_image=og_image_url,
        redirect_url=redirect_url,
        redirect_url_js=repr(redirect_url).replace("'", '"'),
    )


def render_guest_image(name: str, out_path: pathlib.Path):
    """Render a personalized 1200x630 og:image, matching og-image.jpg's
    background/couple-illustration style but with the guest's own name."""
    couple = out_path.parent / f".couple-{out_path.stem}.png"
    subprocess.run(
        ["magick", str(COUPLE_ASSET), "-resize", "x480", str(couple)],
        check=True,
    )
    try:
        subprocess.run(
            [
                "magick", "-size", "1200x630", "radial-gradient:#4a3564-#1c1428",
                str(couple), "-gravity", "East", "-geometry", "+70+60", "-compose", "over", "-composite",
                "-font", SANS_SB_FONT, "-pointsize", "28", "-fill", "#d3a457",
                "-gravity", "NorthWest", "-annotate", "+72+90", "DƏVƏTLİ",
                "-font", SERIF_FONT, "-pointsize", "100", "-fill", "#f2d38f",
                "-gravity", "NorthWest", "-annotate", "+68+140", name,
                "-font", SANS_FONT, "-pointsize", "30", "-fill", "#f3e7d8",
                "-gravity", "NorthWest", "-annotate", "+72+300", "Asər & Türkan-ın toy dəvətnaməsi",
                "-font", SANS_FONT, "-pointsize", "24", "-fill", "#d3a457",
                "-gravity", "NorthWest", "-annotate", "+72+345", "aser-turkan.love",
                "-strip", "-quality", "85", str(out_path),
            ],
            check=True,
        )
    finally:
        couple.unlink(missing_ok=True)


def main():
    names = extract_names()
    OUT_DIR.mkdir(exist_ok=True)
    OG_IMAGE_DIR.mkdir(exist_ok=True)

    seen = {}
    for name in names:
        slug = slugify(name)
        if not slug:
            print(f"WARNING: '{name}' slugified to empty string, skipping")
            continue
        seen.setdefault(slug, []).append(name)

    for slug, group in seen.items():
        # names that collide to the same slug (e.g. Latin "Tika" and
        # Georgian "თიკა") share one generated page, using the first
        # name in the guest list as the canonical display form
        canonical = group[0]
        image_path = OG_IMAGE_DIR / f"{slug}.jpg"
        render_guest_image(canonical, image_path)
        og_image_url = f"{SITE_URL}/i/og/{slug}.jpg"
        (OUT_DIR / f"{slug}.html").write_text(build_page(canonical, slug, og_image_url), encoding="utf-8")
        note = f" (also matches: {', '.join(group[1:])})" if len(group) > 1 else ""
        print(f"wrote i/{slug}.html + i/og/{slug}.jpg for '{canonical}'{note}")

    print(f"\n{len(seen)} pages generated for {len(names)} guest name(s)")


if __name__ == "__main__":
    main()
