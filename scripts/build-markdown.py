"""Write a markdown copy of every published post and page next to its HTML, run after `zola build`"""

import re
import sys
import tomllib
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PUBLIC = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "public"
PAGES = ["about.md", "cv.md", "cv-summary.md"]


def slug(path):
    return re.sub(r"^\d{4}-\d{2}-\d{2}[-_]", "", Path(path).stem)


def tweet(m):
    args = dict(re.findall(r'(\w+)="([^"]*)"', m.group(1)))
    body = "\n".join("> " + line if line.strip() else ">" for line in m.group(2).strip().splitlines())
    return f"{body}\n>\n> {args.get('author', '')}, [{args.get('date', 'link')}]({args.get('url', '')})"


def internal(m, base):
    target, fragment = m.group(1), m.group(2) or ""
    name = Path(target).name
    if target.startswith("posts/"):
        # A fragment points into the HTML page, the markdown copy has no anchors
        return f"({base}/posts/{slug(name)}/{fragment})" if fragment else f"({base}/posts/{slug(name)}.md)"

    return f"({base}/{Path(name).stem}/{fragment})"


def convert(body, base):
    body = re.sub(r"\{%\s*tweet\((.*?)\)\s*%\}(.*?)\{%\s*end\s*%\}", tweet, body, flags=re.S)
    body = re.sub(r'\{\{\s*asset\(path="([^"]+)"\)\s*\}\}', lambda m: f"{base}/{m.group(1).lstrip('/')}", body)
    body = re.sub(r"\(@/([^)#]+\.md)(#[^)]*)?\)", lambda m: internal(m, base), body)
    # Site-relative links become absolute, so the copy works outside the site
    return re.sub(r"\]\(/(?!/)", f"]({base}/", body)


def add_to_sitemap(sitemap, entries):
    """Append (url, lastmod) entries, zola wrote the sitemap before these files existed"""
    rows = "".join(f"<url><loc>{url}</loc>" + (f"<lastmod>{day}</lastmod>" if day else "") + "</url>" for url, day in entries)
    sitemap.write_text(sitemap.read_text().replace("</urlset>", rows + "</urlset>"))


def write(source, url, out, base):
    _, front, body = source.read_text().split("+++", 2)
    meta = tomllib.loads(front)
    lines = [f"# {meta.get('title') or 'CV'}", ""]
    info = [str(meta["date"])] if meta.get("date") else []
    info.append(url)
    tags = meta.get("taxonomies", {}).get("tags", [])
    if tags:
        info.append("tags: " + ", ".join(tags))

    lines += [" · ".join(info), ""]
    if meta.get("description"):
        lines += [f"> {meta['description']}", ""]

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(lines) + "\n" + convert(body, base).strip() + "\n")
    return meta.get("updated") or meta.get("date")


def main():
    base = tomllib.loads((ROOT / "config.toml").read_text())["base_url"].rstrip("/")
    today = date.today()
    entries = []

    for path in sorted((ROOT / "content" / "posts").glob("*.md")):
        if path.name.startswith("_") or path.name.endswith(".pt.md"):
            continue

        meta = tomllib.loads(path.read_text().split("+++", 2)[1])
        # Scheduled posts stay out until the daily deploy on their date, like the sitemap
        if meta.get("draft") or not meta.get("date") or meta["date"] > today:
            continue

        s = slug(path.name)
        day = write(path, f"{base}/posts/{s}/", PUBLIC / "posts" / f"{s}.md", base)
        entries.append((f"{base}/posts/{s}.md", day))

    for name in PAGES:
        path = ROOT / "content" / name
        if path.exists():
            stem = Path(name).stem
            day = write(path, f"{base}/{stem}/", PUBLIC / f"{stem}.md", base)
            entries.append((f"{base}/{stem}.md", day))

    add_to_sitemap(PUBLIC / "sitemap.xml", entries)
    print(f"wrote {len(entries)} markdown copies into {PUBLIC} and its sitemap")


if __name__ == "__main__":
    main()
