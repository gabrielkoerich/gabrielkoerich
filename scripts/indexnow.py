"""Tell IndexNow (Bing and others) about the sitemap URLs changed today, run after the deploy"""

import json
import re
import urllib.request
from datetime import date
from pathlib import Path

SITE = "https://gabrielkoerich.com"


def key():
    # The key is public by design: Bing checks it at https://<site>/<key>.txt
    for path in Path("static").glob("*.txt"):
        if re.fullmatch(r"[0-9a-f]{32}", path.stem) and path.read_text().strip() == path.stem:
            return path.stem

    raise SystemExit("no IndexNow key file in static/")


def changed_today():
    # Cloudflare answers 403 to urllib's default user agent
    request = urllib.request.Request(f"{SITE}/sitemap.xml", headers={"User-Agent": "gabrielkoerich.com indexnow"})
    sitemap = urllib.request.urlopen(request, timeout=30).read().decode()
    today = date.today().isoformat()
    return [loc for loc, mod in re.findall(r"<loc>(.*?)</loc>\s*<lastmod>(.*?)</lastmod>", sitemap) if mod.startswith(today)]


def main():
    urls = changed_today()
    if not urls:
        print("no URLs changed today, nothing to submit")
        return

    k = key()
    body = json.dumps({"host": SITE.removeprefix("https://"), "key": k, "keyLocation": f"{SITE}/{k}.txt", "urlList": urls}).encode()
    request = urllib.request.Request("https://api.indexnow.org/indexnow", data=body, headers={"Content-Type": "application/json; charset=utf-8"})
    with urllib.request.urlopen(request, timeout=30) as response:
        print(f"submitted {len(urls)} URLs, HTTP {response.status}")
        for url in urls:
            print(f"  {url}")


if __name__ == "__main__":
    main()
