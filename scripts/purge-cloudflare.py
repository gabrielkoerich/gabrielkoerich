"""Purge the Cloudflare cache for the files that changed since the last deploy, run after the deploy"""

import hashlib
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

SITE = "https://gabrielkoerich.com"
ZONE = "b4f279fbdc18c1d62d60751dcefbc03e"
# URLs per purge request, the limit on the Free plan
BATCH = 30
# Past this many changed URLs one hostname purge is cheaper than the batches
LIMIT = 300


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


def main():
    root, manifest = Path(sys.argv[1]), Path(sys.argv[2])
    if not os.environ.get("CF_API_TOKEN"):
        raise SystemExit("CF_API_TOKEN is not set, the edge cache was not purged")

    new = hashes(root)
    host = {"hosts": [SITE.removeprefix("https://")]}
    if not manifest.exists():
        print("no file list from the last deploy, purging the hostname")
        ok = purge(host)
    else:
        old = json.loads(manifest.read_text())
        changed = sorted({u for p in new.keys() | old.keys() if new.get(p) != old.get(p) for u in urls(p)})
        print(f"{len(changed)} URLs changed")
        for u in changed:
            print(f"  {u}")

        if not changed:
            ok = True
        elif len(changed) > LIMIT:
            ok = purge(host)
        else:
            ok = all(purge({"files": changed[i:i + BATCH]}) for i in range(0, len(changed), BATCH)) or purge(host)

    # Only the zone is left, and it also clears every other subdomain
    if not ok:
        ok = purge({"purge_everything": True})

    if not ok:
        raise SystemExit("Cloudflare cache purge failed")

    manifest.write_text(json.dumps(new))


if __name__ == "__main__":
    main()
