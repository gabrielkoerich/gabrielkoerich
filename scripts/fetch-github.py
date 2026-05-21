#!/usr/bin/env python3
"""
Fetch GitHub profile data including pinned repositories.
Scrapes the public GitHub profile page to get pinned repos dynamically.
"""

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
import urllib.request
import urllib.error

USERNAME = "gabrielkoerich"
OUTPUT_DIR = Path("data")


def fetch_url(url, headers=None):
    """Fetch URL content"""
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req) as response:
            return response.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        print(f"Error fetching {url}: {e}", file=sys.stderr)
        return None


def fetch_profile(token=None):
    """Fetch user profile from GitHub API"""
    headers = {}
    if token:
        headers["Authorization"] = f"token {token}"

    url = f"https://api.github.com/users/{USERNAME}"
    html = fetch_url(url, headers)
    if html:
        return json.loads(html)
    return {}


def fetch_repo(owner, repo, token=None):
    """Fetch repository details from GitHub API"""
    headers = {}
    if token:
        headers["Authorization"] = f"token {token}"

    url = f"https://api.github.com/repos/{owner}/{repo}"
    html = fetch_url(url, headers)
    if html:
        return json.loads(html)
    return None


def fetch_pinned_repos(token=None):
    """
    Fetch pinned repositories by scraping GitHub profile.
    Looks for repository links in the profile page.
    """
    print("Scraping GitHub profile for pinned repositories...")

    # Scrape the profile page
    url = f"https://github.com/{USERNAME}"
    html = fetch_url(url)

    if not html:
        print("Failed to fetch profile page", file=sys.stderr)
        return []

    # Find all repository links
    # Pattern matches: href="/owner/repo"
    # We want paths with exactly 2 components (owner/repo)
    pattern = r'href="/([^/"]+/[^/"]+)"'
    matches = re.findall(pattern, html)

    # Filter and deduplicate
    repos = []
    seen = set()

    # Common GitHub paths to skip
    skip_patterns = [
        "achievements",
        "forks",
        "stargazers",
        "issues",
        "pulls",
        "actions",
        "projects",
        "wiki",
        "security",
        "pulse",
        "graphs",
        "settings",
        "report-abuse",
        "contact",
        "notifications",
        "explore",
        "marketplace",
        "pricing",
        "topics",
        "collections",
        "trending",
        "readme",
        "license",
        "code-of-conduct",
        "pull",
        "issues",
        "commits",
        "branches",
        "releases",
        "packages",
        "labels",
        "milestones",
    ]

    for match in matches:
        # Skip if contains query params or anchors
        if "?" in match or "&" in match or "#" in match:
            continue

        # Skip GitHub system paths
        if any(skip in match.lower() for skip in skip_patterns):
            continue

        # Must have exactly one slash (owner/repo format)
        parts = match.split("/")
        if len(parts) != 2:
            continue

        owner, repo = parts

        # Skip profile repo (owner/repo where owner == repo == username)
        if owner == USERNAME and repo == USERNAME:
            continue

        if match not in seen:
            seen.add(match)
            repos.append(match)

    # GitHub shows max 6 pinned repos
    repos = repos[:6]

    print(f"Found {len(repos)} potential pinned repositories")

    # Fetch details for each repo
    pinned = []
    for repo_path in repos:
        try:
            owner, repo = repo_path.split("/", 1)
            print(f"  Fetching {owner}/{repo}...", end=" ")

            data = fetch_repo(owner, repo, token)

            if data and "name" in data:
                pinned.append(
                    {
                        "name": data.get("name", repo),
                        "description": data.get("description") or "",
                        "html_url": data.get(
                            "html_url", f"https://github.com/{repo_path}"
                        ),
                        "language": {"name": data.get("language") or ""},
                        "stargazers": {"totalCount": data.get("stargazers_count", 0)},
                        "owner": {"login": data.get("owner", {}).get("login", owner)},
                    }
                )
                print(f"✓ ({data.get('stargazers_count', 0)} ⭐)")
            else:
                print("✗ (not found)")
        except Exception as e:
            print(f"✗ ({e})")

    return pinned


def fetch_events(token=None):
    """Fetch recent public events"""
    headers = {}
    if token:
        headers["Authorization"] = f"token {token}"

    url = f"https://api.github.com/users/{USERNAME}/events/public?per_page=100"
    html = fetch_url(url, headers)
    if html:
        return json.loads(html)
    return []


def humanize_delta(iso_ts):
    """Convert an ISO timestamp to a relative human string."""
    if not iso_ts:
        return ""
    try:
        ts = datetime.fromisoformat(iso_ts.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return ""
    delta = datetime.now(timezone.utc) - ts
    days = delta.days
    if days < 0:
        return "in the future"
    if days == 0:
        hours = delta.seconds // 3600
        if hours == 0:
            return "just now"
        return f"{hours}h ago"
    if days == 1:
        return "yesterday"
    if days < 7:
        return f"{days} days ago"
    if days < 14:
        return "last week"
    if days < 30:
        return f"{days // 7} weeks ago"
    if days < 60:
        return "last month"
    if days < 365:
        return f"{days // 30} months ago"
    years = days // 365
    return f"{years} year{'s' if years > 1 else ''} ago"


def fetch_repos(token=None):
    """Fetch user repositories"""
    headers = {}
    if token:
        headers["Authorization"] = f"token {token}"

    url = f"https://api.github.com/users/{USERNAME}/repos?sort=pushed&per_page=100"
    html = fetch_url(url, headers)
    if not html:
        return []
    repos = json.loads(html)

    # Enrich with relative-time strings and a days_since_push integer for filtering
    now = datetime.now(timezone.utc)
    for r in repos:
        pushed = r.get("pushed_at")
        if pushed:
            try:
                ts = datetime.fromisoformat(pushed.replace("Z", "+00:00"))
                r["days_since_push"] = (now - ts).days
                r["pushed_relative"] = humanize_delta(pushed)
            except (ValueError, AttributeError):
                r["days_since_push"] = 9999
                r["pushed_relative"] = ""
        else:
            r["days_since_push"] = 9999
            r["pushed_relative"] = ""
    return repos


def main():
    # Get token from environment or args
    token = None
    if len(sys.argv) > 1:
        token = sys.argv[1]
    else:
        token = None  # Will use env var if needed

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Fetching GitHub data for {USERNAME}...")
    if token:
        print("Using authenticated requests")
    else:
        print("Using public API (unauthenticated)")

    # Fetch all data
    print("\nFetching profile...")
    profile = fetch_profile(token)

    print("\nFetching repositories...")
    repos = fetch_repos(token)

    print("\nFetching pinned repositories...")
    pinned = fetch_pinned_repos(token)

    print("\nFetching contribution events...")
    events = fetch_events(token)

    # Save all data
    (OUTPUT_DIR / "github-profile.json").write_text(
        json.dumps(profile, indent=2), encoding="utf-8"
    )

    (OUTPUT_DIR / "github-repos.json").write_text(
        json.dumps(repos, indent=2), encoding="utf-8"
    )

    (OUTPUT_DIR / "github-pinned.json").write_text(
        json.dumps(pinned, indent=2), encoding="utf-8"
    )

    (OUTPUT_DIR / "github-events.json").write_text(
        json.dumps(events, indent=2), encoding="utf-8"
    )

    print(f"\n{'=' * 50}")
    print("GitHub data fetched successfully!")
    print(f"{'=' * 50}")
    print(f"\nFiles created:")
    print(f"  - {OUTPUT_DIR}/github-profile.json")
    print(f"  - {OUTPUT_DIR}/github-repos.json")
    print(f"  - {OUTPUT_DIR}/github-pinned.json")
    print(f"  - {OUTPUT_DIR}/github-events.json")

    if pinned:
        print(f"\nPinned repositories ({len(pinned)}):")
        for repo in pinned:
            owner = repo["owner"]["login"]
            name = repo["name"]
            stars = repo["stargazers"]["totalCount"]
            lang = repo["language"]["name"]
            if owner != USERNAME:
                print(f"  - {owner}/{name} (★{stars}) [{lang}] ← contributed")
            else:
                print(f"  - {name} (★{stars}) [{lang}]")
    else:
        print("\nNo pinned repositories found.")
        print("  Note: If you change pinned repos on GitHub, run this script again.")


if __name__ == "__main__":
    main()
