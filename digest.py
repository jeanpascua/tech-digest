#!/usr/bin/env python3
"""Daily tech news digest → Discord webhook."""

import os
import re
import json
import time
import subprocess
import requests
from requests.adapters import HTTPAdapter, Retry
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

WEBHOOK_URL = os.environ["DISCORD_WEBHOOK_URL"]
HN_TOP_URL = "https://hacker-news.firebaseio.com/v0/topstories.json"
HN_ITEM_URL = "https://hacker-news.firebaseio.com/v0/item/{}.json"
TOP_N = 10

HEADERS = {"User-Agent": "linux:tech-digest-bot:v1.0 (by /u/jean-homelab)"}

session = requests.Session()
retries = Retry(total=3, backoff_factor=2, status_forcelist=[429, 500, 502, 503])
session.mount("https://", HTTPAdapter(max_retries=retries))


def fetch_hn(n=TOP_N):
    ids = session.get(HN_TOP_URL, timeout=10).json()[:n * 3]
    stories = []
    for id_ in ids:
        if len(stories) >= n:
            break
        item = session.get(HN_ITEM_URL.format(id_), timeout=10).json()
        if item.get("type") == "story" and item.get("url"):
            page_text = fetch_page_text(item["url"])
            desc = summarize(item["title"], page_text)
            stories.append({
                "title": item["title"],
                "url": item["url"],
                "score": item.get("score", 0),
                "comments": f"https://news.ycombinator.com/item?id={item['id']}",
                "description": desc,
            })
    return stories



OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "qwen2.5:7b"


def fetch_page_text(url, max_chars=3000):
    try:
        resp = session.get(url, headers=HEADERS, timeout=10)
        text = resp.text[:max_chars]
        text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL)
        text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL)
        text = re.sub(r'<[^>]+>', ' ', text)
        text = re.sub(r'\s+', ' ', text).strip()
        return text[:1500]
    except Exception:
        return ""


def summarize(title, page_text):
    if not page_text:
        return ""
    prompt = f"Summarize in under 12 words. Output only the summary.\n\nTitle: {title}\nContent: {page_text[:800]}"
    try:
        resp = session.post(OLLAMA_URL, json={
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.3, "num_predict": 40},
        }, timeout=30)
        return resp.json().get("response", "").strip()
    except Exception:
        return ""


def format_stories(stories, show_comments=True):
    lines = []
    for i, s in enumerate(stories, 1):
        score = f" ↑{s['score']}" if s.get("score") is not None else ""
        line = f"{i}. [{s['title']}]({s['url']}){score}"
        if show_comments and s.get("comments") and s["comments"] != s["url"]:
            line += f" · [comments]({s['comments']})"
        desc = s.get("description", "")
        if desc:
            line += f"\n> {desc}"
        lines.append(line)
    result = "\n".join(lines)
    while len(result) > 4000 and lines:
        last = lines[-1]
        if "\n> " in last:
            lines[-1] = last[:last.index("\n> ")]
        else:
            lines.pop()
        result = "\n".join(lines)
    return result


def build_payload(hn):
    date_str = datetime.now(timezone.utc).strftime("%A, %b %d %Y")
    embeds = [
        {
            "title": f"Tech Digest — {date_str}",
            "color": 0xFF6600,
            "description": f"**🔶 Hacker News**\n{format_stories(hn)}",
            "footer": {"text": "Hacker News · daily at 8am"},
        },
    ]
    return {"embeds": embeds}


def main():
    print("Fetching HN...")
    hn = fetch_hn()

    payload = build_payload(hn)
    resp = session.post(WEBHOOK_URL, json=payload, timeout=10)
    resp.raise_for_status()
    print(f"Posted. Status: {resp.status_code}")


if __name__ == "__main__":
    main()
