# tech-digest

Daily Discord digest of top stories from Hacker News, r/programming, and r/devops. Posts every morning at 8am via systemd timer.

## What it does

Fetches the top 5 stories from each source and sends a single Discord embed with all three sections.

## Setup

```bash
git clone git@github.com:jeanpascua/tech-digest.git
cd tech-digest

python3 -m venv venv
venv/bin/pip install -r requirements.txt

cp .env.example .env
# paste your Discord webhook URL into .env
```

Test it:

```bash
venv/bin/python digest.py
```

## Deploy (systemd)

```bash
sudo cp tech-digest.service tech-digest.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now tech-digest.timer
```

Check logs:

```bash
journalctl -u tech-digest.service
systemctl list-timers tech-digest.timer
```

## Config

| Variable | Description |
|----------|-------------|
| `DISCORD_WEBHOOK_URL` | Discord incoming webhook URL |

Timer fires at 8:00am local time daily (`OnCalendar=*-*-* 08:00:00`).
