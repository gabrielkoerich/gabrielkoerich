"""Purge the Cloudflare cache for the files that changed since the last deploy, then warm them, run after the deploy"""

import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

SITE = "https://gabrielkoerich.com"
ZONE = "b4f279fbdc18c1d62d60751dcefbc03e"
# URLs per purge request, the limit on the Free plan
BATCH = 30
# Past this many changed URLs one hostname purge is cheaper than the batches
LIMIT = 300
# Requests after a purge, so a hostname purge does not turn into thousands of fetches
WARM_LIMIT = 500


def hashes(root):
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(root.rglob("*")) if p.is_file()}


def urls(path):
    if path == "index.html":
        return [f"{SITE}/"]

    # Cloudflare caches the form without the slash on its own, a redirect or a 404 from before the page existed
    if path.endswith("/index.html"):
        page = f"{SITE}/{path.removesuffix('/index.html')}"
        return [page, f"{page}/"]

    return [f"{SITE}/{path}"]


def purge(body):
    print(f"purging {json.dumps(body)}")
    request = urllib.request.Request(
        f"https://api.cloudflare.com/client/v4/zones/{ZONE}/purge_cache",
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {os.environ['CF_API_TOKEN']}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            result = response.read().decode()
    except urllib.error.HTTPError as error:
        result = error.read().decode()

    print(result)
    return '"success":true' in result


def warm_targets(root, paths):
    # A page in its slash form only, the form without the slash is a redirect
    pages = sorted({urls(p)[-1] for p in paths if p.endswith("index.html")})
    files = sorted({urls(p)[-1] for p in paths if not p.endswith("index.html")})
    # The stylesheets every page loads, linked with a cachebust query that is part of the cache key
    home = (root / "index.html").read_text(errors="ignore")
    styles = sorted({u for u in re.findall(r'href="?([^" >]+\.css[^" >]*)', home) if u.startswith(SITE)})
    # Pages first, so the cap never drops a page for an image
    return list(dict.fromkeys(pages + styles + files))[:WARM_LIMIT]


def fetch(url):
    # Cloudflare answers 403 to urllib's default user agent
    request = urllib.request.Request(url, headers={"User-Agent": "gabrielkoerich.com cache warm"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return response.status
    except urllib.error.HTTPError as error:
        return error.code
    except (urllib.error.URLError, TimeoutError):
        return 0


def warm(targets):
    with ThreadPoolExecutor(max_workers=8) as pool:
        codes = list(pool.map(fetch, targets))
    print(f"warmed {len(targets)} URLs: " + ", ".join(f"{codes.count(c)} x {c}" for c in sorted(set(codes))))


def main():
    root, manifest = Path(sys.argv[1]), Path(sys.argv[2])
    if not os.environ.get("CF_API_TOKEN"):
        raise SystemExit("CF_API_TOKEN is not set, the edge cache was not purged")

    new = hashes(root)
    host = {"hosts": [SITE.removeprefix("https://")]}
    # What the purge emptied that still exists, a deleted URL would only cache a 404
    to_warm = set(new)
    if not manifest.exists():
        print("no file list from the last deploy, purging the hostname")
        ok = purge(host)
    else:
        old = json.loads(manifest.read_text())
        changed_paths = {p for p in new.keys() | old.keys() if new.get(p) != old.get(p)}
        changed = sorted({u for p in changed_paths for u in urls(p)})
        print(f"{len(changed)} URLs changed")
        for u in changed:
            print(f"  {u}")

        if not changed:
            ok = True
            to_warm = set()
        elif len(changed) > LIMIT:
            ok = purge(host)
        else:
            to_warm = changed_paths & new.keys()
            ok = all(purge({"files": changed[i:i + BATCH]}) for i in range(0, len(changed), BATCH))
            if not ok:
                ok = purge(host)
                to_warm = set(new)

    # Only the zone is left, and it also clears every other subdomain
    if not ok:
        ok = purge({"purge_everything": True})
        to_warm = set(new)

    if not ok:
        raise SystemExit("Cloudflare cache purge failed")

    manifest.write_text(json.dumps(new))
    if to_warm:
        warm(warm_targets(root, to_warm))


if __name__ == "__main__":
    main()
