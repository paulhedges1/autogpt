"""Small Firecrawl discovery test: one keyword, one query per platform.

Read-only. Public pages only. No logins, no retries, no workarounds.
Makes at most MAX_REQUESTS search calls (each asks Firecrawl to return the page
text so we can see whether the full question is readable).

Usage: FIRECRAWL_API_KEY=... python platform_test.py ["keyword"]
"""
import os
import sys
import time

import requests

API_URL = "https://api.firecrawl.dev/v2/search"
RESULTS_PER_PLATFORM = 3
MAX_REQUESTS = 5
DELAY_SECONDS = 3
MIN_READABLE_CHARS = 300
LOGIN_WALL_MARKERS = (
    "sign in to", "log in to", "join linkedin", "log into facebook",
    "you must log in", "create an account", "captcha", "verify you are human",
)

PLATFORMS = {
    "Quora": "site:quora.com {kw}",
    "Reddit": "site:reddit.com {kw}",
    "LinkedIn": "site:linkedin.com {kw}",
    "Facebook": "site:facebook.com {kw}",
    "General web": "{kw} -site:quora.com -site:reddit.com -site:linkedin.com -site:facebook.com",
}


def extract_results(payload):
    data = payload.get("data", [])
    if isinstance(data, dict):  # v2 shape: {"web": [...]}
        data = data.get("web", [])
    return data or []


def assess(item):
    text = item.get("markdown") or ""
    meta = item.get("metadata") or {}
    lowered = text.lower()
    wall = [m for m in LOGIN_WALL_MARKERS if m in lowered]
    return {
        "url": item.get("url") or meta.get("sourceURL", ""),
        "title": item.get("title") or meta.get("title", ""),
        "chars": len(text),
        "readable": len(text) >= MIN_READABLE_CHARS and not wall,
        "wall": wall,
        "error": meta.get("error"),
        "status": meta.get("statusCode"),
        "snippet": " ".join(text.split())[:160],
    }


def main():
    key = os.environ.get("FIRECRAWL_API_KEY")
    if not key:
        sys.exit("FIRECRAWL_API_KEY is not set. Stopping.")
    keyword = sys.argv[1] if len(sys.argv) > 1 else "CV writer"
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    print(f"Platform test | keyword: {keyword!r} | max {MAX_REQUESTS} requests\n")

    for count, (platform, template) in enumerate(PLATFORMS.items(), start=1):
        if count > MAX_REQUESTS:
            break
        body = {
            "query": template.format(kw=keyword),
            "limit": RESULTS_PER_PLATFORM,
            "scrapeOptions": {"formats": ["markdown"], "onlyMainContent": True},
        }
        print(f"== {platform}: {body['query']}")
        try:
            resp = requests.post(API_URL, headers=headers, json=body, timeout=90)
        except requests.RequestException as exc:
            print(f"   ERROR: request failed ({type(exc).__name__}). Not retrying.\n")
            continue
        if resp.status_code != 200:
            print(f"   BLOCKED/ERROR: HTTP {resp.status_code}: {resp.text[:200]!r}. Not retrying.\n")
            continue
        results = [assess(r) for r in extract_results(resp.json())]
        readable = sum(r["readable"] for r in results)
        print(f"   results returned: {len(results)} | full text readable: {readable}/{len(results)}")
        for r in results:
            flags = []
            if r["wall"]:
                flags.append(f"login-wall markers: {r['wall']}")
            if r["error"]:
                flags.append(f"scrape error: {r['error']}")
            if r["status"] and r["status"] != 200:
                flags.append(f"page status: {r['status']}")
            print(f"   - {r['url']}\n     {r['chars']} chars | readable={r['readable']} {'; '.join(flags)}")
            print(f"     {r['snippet']!r}")
        print()
        time.sleep(DELAY_SECONDS)


if __name__ == "__main__":
    main()
