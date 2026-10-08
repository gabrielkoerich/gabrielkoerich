"""Write llms.txt (https://llmstxt.org) from the site content, run after `zola build`"""

import json
import re
import sys
import tomllib
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "public" / "llms.txt"
PAGES = ["about.md", "consulting.md", "cv.md"]
# Posts before this year are old Portuguese posts, listed under Optional
OPTIONAL_BEFORE = 2020


def read(path):
    text = path.read_text()
    _, front, body = text.split("+++", 2)
    return tomllib.loads(front), body


def summary(body):
    """First prose paragraph, plain text, cut at a sentence end near 200 characters"""
    for block in body.split("\n\n"):
        block = block.strip()
        if not block or block[0] in "#{<|`-*>!":
            continue
        text = re.sub(r"!?\[([^\]]*)\]\([^)]*\)", r"\1", block)
        text = re.sub(r"[*_`]", "", " ".join(text.split()))
        if len(text) <= 200:
            return text
        cut = text[:200].rfind(". ")
        return text[: cut + 1] if cut > 0 else text[:197] + "..."
    return ""


def main():
    config = tomllib.loads((ROOT / "config.toml").read_text())
    base = config["base_url"].rstrip("/")
    today = date.today()

    posts = []
    for path in (ROOT / "content" / "posts").glob("*.md"):
        if path.name.startswith("_") or path.name.endswith(".pt.md"):
            continue

        front, body = read(path)
        day = front.get("date")
        # Scheduled posts stay out until the daily deploy on their date, like the sitemap
        if front.get("draft") or not day or day > today:
            continue

        slug = re.sub(r"^\d{4}-\d{2}-\d{2}[-_]", "", path.stem)
        posts.append((day, front["title"], f"{base}/posts/{slug}/", front.get("description") or summary(body)))

    posts.sort(reverse=True)

    _, about_body = read(ROOT / "content" / "about.md")
    lines = [f"# {config['title']}", "", f"> {config['description']}", "", summary(about_body), "", "## Pages", ""]

    for name in PAGES:
        front, _ = read(ROOT / "content" / name)
        title = front.get("title") or "CV"
        lines.append(f"- [{title}]({base}/{Path(name).stem}/): {front.get('description', '')}".rstrip(": "))

    lines += ["", "## Posts", ""]
    lines += [f"- [{t}]({u}): {d}" for day, t, u, d in posts if day.year >= OPTIONAL_BEFORE]

    repos_file = ROOT / "data" / "github-repos.json"
    if repos_file.exists():
        projects = []
        for repo in json.loads(repos_file.read_text()):
            home = (repo.get("homepage") or "").replace("http://", "https://").rstrip("/")
            if "gabrielkoerich.com" in home and home != base:
                projects.append(f"- [{repo['name']}]({home}/): {repo.get('description') or ''}".rstrip(": "))

        if projects:
            lines += ["", "## Projects", ""] + sorted(projects)

    old = [f"- [{t}]({u}): {d}" for day, t, u, d in posts if day.year < OPTIONAL_BEFORE]
    if old:
        lines += ["", "## Optional", ""] + old

    OUT.write_text("\n".join(lines) + "\n")
    print(f"wrote {OUT} with {len(posts)} posts")


if __name__ == "__main__":
    main()
