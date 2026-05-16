#!/usr/bin/env python3
"""Daily tech news digest → Discord webhook."""

import os
import json
import requests
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

WEBHOOK_URL = os.environ["DISCORD_WEBHOOK_URL"]
HN_TOP_URL = "https://hacker-news.firebaseio.com/v0/topstories.json"
HN_ITEM_URL = "https://hacker-news.firebaseio.com/v0/item/{}.json"
REDDIT_URL = "https://www.reddit.com/r/{}/top.json?limit=10&t=day"
TOP_N = 5

HEADERS = {"User-Agent": "tech-digest-bot/1.0"}


def fetch_hn(n=TOP_N):
    ids = requests.get(HN_TOP_URL, timeout=10).json()[:n * 3]
    stories = []
    for id_ in ids:
        if len(stories) >= n:
            break
        item = requests.get(HN_ITEM_URL.format(id_), timeout=10).json()
        if item.get("type") == "story" and item.get("url"):
            stories.append({
                "title": item["title"],
                "url": item["url"],
                "score": item.get("score", 0),
                "comments": f"https://news.ycombinator.com/item?id={item['id']}",
            })
    return stories


def fetch_reddit(sub, n=TOP_N):
    resp = requests.get(REDDIT_URL.format(sub), headers=HEADERS, timeout=10)
    posts = resp.json()["data"]["children"]
    results = []
    for p in posts[:n]:
        d = p["data"]
        if d.get("is_self"):
            url = f"https://reddit.com{d['permalink']}"
        else:
            url = d.get("url", f"https://reddit.com{d['permalink']}")
        results.append({
            "title": d["title"],
            "url": url,
            "score": d["score"],
            "comments": f"https://reddit.com{d['permalink']}",
        })
    return results


def format_stories(stories, show_comments=True):
    lines = []
    for i, s in enumerate(stories, 1):
        line = f"{i}. [{s['title']}]({s['url']}) ↑{s['score']}"
        if show_comments and s.get("comments") and s["comments"] != s["url"]:
            line += f" · [comments]({s['comments']})"
        lines.append(line)
    return "\n".join(lines)


def build_payload(hn, programming, devops):
    date_str = datetime.now(timezone.utc).strftime("%A, %b %d %Y")
    embeds = [
        {
            "title": f"Tech Digest — {date_str}",
            "color": 0xFF6600,
            "fields": [
                {
                    "name": "🔶 Hacker News",
                    "value": format_stories(hn),
                    "inline": False,
                },
                {
                    "name": "💻 r/programming",
                    "value": format_stories(programming),
                    "inline": False,
                },
                {
                    "name": "⚙️ r/devops",
                    "value": format_stories(devops),
                    "inline": False,
                },
            ],
            "footer": {"text": "HN + Reddit · daily at 8am"},
        }
    ]
    return {"embeds": embeds}


def main():
    print("Fetching HN...")
    hn = fetch_hn()
    print("Fetching r/programming...")
    programming = fetch_reddit("programming")
    print("Fetching r/devops...")
    devops = fetch_reddit("devops")

    payload = build_payload(hn, programming, devops)
    resp = requests.post(WEBHOOK_URL, json=payload, timeout=10)
    resp.raise_for_status()
    print(f"Posted. Status: {resp.status_code}")


if __name__ == "__main__":
    main()
