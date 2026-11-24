"""Fill the project and post lists in README.md, the GitHub profile page, run after fetch-github.py"""

import json
import re
import subprocess
import tomllib
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"
POSTS = 5
# A repo counts as current while it had a push in this many days
CURRENT_DAYS = 360
SKIP = {"gabrielkoerich", "gabrielkoerich.github.io", "homebrew-tap"}


def read(path):
    _, front, body = path.read_text().split("+++", 2)
    return tomllib.loads(front)


def posts(base):
    today = date.today()
    # Untracked posts are local drafts that never reach the site
    tracked = subprocess.run(["git", "ls-files", "content/posts"], cwd=ROOT, capture_output=True, text=True, check=True)
    found = []
    for name in tracked.stdout.split():
        path = ROOT / name
        if path.suffix != ".md" or path.name.startswith("_") or path.name.endswith(".pt.md"):
            continue

        front = read(path)
        day = front.get("date")
        # Scheduled posts stay out until the daily deploy on their date, like the sitemap
        if front.get("draft") or not day or day > today:
            continue

        slug = front.get("slug") or re.sub(r"^\d{4}-\d{2}-\d{2}[-_]", "", path.stem)
        found.append((day, front["title"], f"{base}/posts/{slug}/"))

    found.sort(reverse=True)
    return [f"- [{title}]({url})" for day, title, url in found[:POSTS]]


def projects():
    repos = json.loads((ROOT / "data" / "github-repos.json").read_text())
    lines = []
    repos.sort(key=lambda r: r.get("last_commit_at") or r.get("pushed_at") or "", reverse=True)
    for repo in repos:
        if repo["fork"] or repo["archived"] or repo["name"] in SKIP or not repo.get("description"):
            continue

        # Without a token there is no commit date, so fall back to the last push
        age = repo.get("days_since_commit")
        if (repo.get("days_since_push", 9999) if age is None else age) > CURRENT_DAYS:
            continue

        line = f"- **[{repo['name']}]({repo['html_url']})** - {repo['description'].strip()}"
        home = (repo.get("homepage") or "").strip().rstrip("/")
        if home:
            home = re.sub(r"^(https?://)?", "https://", home)
            line += f" [{home.removeprefix('https://')}]({home})"

        lines.append(line)

    return lines


def fill(text, name, lines):
    pattern = re.compile(rf"(<!-- {name}:start -->\n).*?(<!-- {name}:end -->)", re.S)
    if not pattern.search(text):
        raise SystemExit(f"README.md has no {name} markers")

    return pattern.sub(lambda m: m.group(1) + "\n".join(lines) + "\n" + m.group(2), text)


def main():
    base = tomllib.loads((ROOT / "config.toml").read_text())["base_url"].rstrip("/")
    text = fill(README.read_text(), "projects", projects())
    text = fill(text, "posts", posts(base))
    README.write_text(text)
    print("wrote README.md")


if __name__ == "__main__":
    main()
