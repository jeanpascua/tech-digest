#!/usr/bin/env python3
"""Daily tech news digest → Discord webhook."""

import os
import re
import json
import time
import subprocess
import xml.etree.ElementTree as ET
import requests
from requests.adapters import HTTPAdapter, Retry
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

WEBHOOK_URL = os.environ["DISCORD_WEBHOOK_URL"]
HN_TOP_URL = "https://hacker-news.firebaseio.com/v0/topstories.json"
HN_ITEM_URL = "https://hacker-news.firebaseio.com/v0/item/{}.json"
REDDIT_RSS_URL = "https://www.reddit.com/r/{}/top.rss?t=day"
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


def fetch_reddit(sub, n=TOP_N):
    xml_body = None
    for attempt in range(3):
        result = subprocess.run(
            ["curl", "-s", "-L", "-w", "\n__HTTP_STATUS__%{http_code}",
             "-H", f"User-Agent: {HEADERS['User-Agent']}",
             REDDIT_RSS_URL.format(sub)],
            capture_output=True, text=True, timeout=30,
        )
        body, _, http_status = result.stdout.rpartition("\n__HTTP_STATUS__")
        http_status = http_status.strip()
        if result.returncode == 0 and http_status == "200" and "<entry>" in body:
            xml_body = body
            break
        wait = 30 * (2 ** attempt)  # 30s, 60s, 120s
        print(f"  WARN: r/{sub} attempt {attempt+1} failed (HTTP {http_status}), retrying in {wait}s...")
        time.sleep(wait)
    else:
        print(f"  WARN: r/{sub} all retries failed, skipping")
        return []
    root = ET.fromstring(xml_body)
    ns = {"atom": "http://www.w3.org/2005/Atom"}
    entries = root.findall("atom:entry", ns)
    results = []
    for entry in entries[:n]:
        title = entry.findtext("atom:title", "", ns).strip()
        link_el = entry.find("atom:link", ns)
        reddit_link = link_el.get("href", "") if link_el is not None else ""
        if not (title and reddit_link):
            continue
        content = entry.findtext("atom:content", "", ns)
        ext_urls = re.findall(r'href="(https?://(?!www\.reddit\.com)[^"]+)"', content)
        ext_url = ext_urls[0] if ext_urls else ""
        link = ext_url or reddit_link
        desc = ""
        if ext_url:
            page_text = fetch_page_text(ext_url)
        else:
            page_text = ""
        if len(page_text) < 50:
            post_body = re.sub(r'<[^>]+>', ' ', content)
            post_body = re.sub(r'\s+', ' ', post_body).strip()
            page_text = post_body[:800] if len(post_body) > 50 else ""
        if page_text:
            desc = summarize(title, page_text)
        results.append({"title": title, "url": link, "score": None, "comments": reddit_link, "description": desc})
    return results


OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "gemma3:4b"


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
