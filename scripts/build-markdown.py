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


def main():
    base = tomllib.loads((ROOT / "config.toml").read_text())["base_url"].rstrip("/")
    today = date.today()
    count = 0

    for path in sorted((ROOT / "content" / "posts").glob("*.md")):
        if path.name.startswith("_") or path.name.endswith(".pt.md"):
            continue

        meta = tomllib.loads(path.read_text().split("+++", 2)[1])
        # Scheduled posts stay out until the daily deploy on their date, like the sitemap
        if meta.get("draft") or not meta.get("date") or meta["date"] > today:
            continue

        s = slug(path.name)
        write(path, f"{base}/posts/{s}/", PUBLIC / "posts" / f"{s}.md", base)
        count += 1

    for name in PAGES:
        path = ROOT / "content" / name
        if path.exists():
            stem = Path(name).stem
            write(path, f"{base}/{stem}/", PUBLIC / f"{stem}.md", base)
            count += 1

    print(f"wrote {count} markdown copies into {PUBLIC}")


if __name__ == "__main__":
    main()
