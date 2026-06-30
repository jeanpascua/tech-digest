# tech-digest

Pulls the top 10 Hacker News stories every morning, summarizes each with a local Ollama model, and posts them as a Discord embed. Runs on my homelab server via systemd timer at 8am daily. I built it because I wanted passive tech news without opening HN myself.

## What gets posted

One Discord embed:

- **Hacker News** — top 10 stories of the day (Firebase API), with AI-generated summary, score, and comments link

## Setup

```bash
git clone git@github.com:jeanpascua/tech-digest.git
cd tech-digest

python3 -m venv venv
venv/bin/pip install -r requirements.txt

cp .env.example .env
# add your Discord webhook URL to .env
```

Test it manually:

```bash
venv/bin/python digest.py
```

## Deploy (systemd)

```bash
sudo cp tech-digest.service tech-digest.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now tech-digest.timer
```

Check it's scheduled:

```bash
systemctl list-timers tech-digest.timer
journalctl -u tech-digest.service
```

Timer fires at `08:00:00` local time daily.

## Config

| Variable | Description |
|----------|-------------|
| `DISCORD_WEBHOOK_URL` | Discord incoming webhook URL |

`.env` file, not committed. See `.env.example` for the format.

## Stack

- Python + `requests` + `python-dotenv`
- Ollama (`qwen2.5:7b`) — local LLM for per-story summarization
- Discord webhook (no bot token)
- Systemd timer (no cron, no Docker)
