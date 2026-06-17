# Auto Content Poster

> AI-powered multi-platform social media content generator and auto-scheduler.
> Powered by Claude AI — generates platform-native posts and publishes them on a daily schedule.

---

## How It Works

```
┌─────────────────────────────────────────────────────────────┐
│                      TRIGGER                                │
│        scheduler (cron) | CLI | MCP (Claude Desktop)        │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│                  NICHE SELECTION                            │
│   fitness · crypto · motivation · tech · food               │
│           (random or specified by caller)                   │
└───────────────────────┬─────────────────────────────────────┘
                        │
                        ▼
┌─────────────────────────────────────────────────────────────┐
│              CLAUDE AI CONTENT GENERATOR                    │
│   niche_config.py → prompt → claude-sonnet-4-6 → post text │
│   (per-platform: char limit · tone · hashtags · format)     │
└───────────┬───────┬───────┬───────┬───────────────────────┘
            │       │       │       │
            ▼       ▼       ▼       ▼
        Twitter Instagram Facebook Telegram
```

---

## Features

- AI content generation via Claude (tone, length, hashtags tuned per platform)
- 5 content niches — fitness, crypto, motivation, tech, food
- 4 live platforms — Twitter, Instagram, Facebook, Telegram
- MCP server — drive everything from Claude Desktop
- Auto-clean — remove stale log files on a schedule or via CLI

---

## Requirements

- **Python 3.11+** — required (uses modern type hints)
- API keys for the platforms you want to post to

---

## Quick Start

```bash
# 1. Clone
git clone <repo-url> && cd auto-content-poster

# 2. Virtual env
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

# 3. Install
pip install -r requirements.txt

# 4. Configure
cp .env.example .env
# Fill in your keys (see Environment Variables below)

# 5. Run
python main.py start
```

---

## CLI

```bash
# Start the daily scheduler (posts at 08:00, 12:00, 17:00, 20:00)
python main.py start

# Post right now (random niche)
python main.py post-now

# Post right now for a specific niche
python main.py post-now --niche fitness

# Preview a post (no publishing)
python main.py preview --niche crypto --platform twitter

# Remove log files older than 7 days (default)
python main.py clean

# Remove log files older than 30 days
python main.py clean --days 30
```

---

## MCP Server — Claude Desktop Integration

The MCP server exposes all poster tools so you can drive the entire system from a Claude Desktop conversation.

### Start

```bash
python mcp_server.py
```

### Wire up Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "auto-content-poster": {
      "command": "python",
      "args": ["/absolute/path/to/auto-content-poster/mcp_server.py"],
      "env": {
        "ANTHROPIC_API_KEY": "sk-ant-..."
      }
    }
  }
}
```

Restart Claude Desktop — the poster tools appear in the tool drawer.

### Available MCP tools

| Tool | What it does |
|---|---|
| `generate_post` | Generate one post — niche + platform |
| `generate_all_platforms` | Generate posts for every active platform |
| `list_niches` | Show niches with topics, tone, hashtags |
| `list_platforms` | Show platform on/off status |
| `post_now` | Fire an immediate posting cycle |
| `clean_logs` | Delete logs older than N days |

---

## Configuration

### Environment variables

| Variable | Platform | Required |
|---|---|---|
| `ANTHROPIC_API_KEY` | Claude AI | Yes |
| `TWITTER_API_KEY` | Twitter | If enabled |
| `TWITTER_API_SECRET` | Twitter | If enabled |
| `TWITTER_ACCESS_TOKEN` | Twitter | If enabled |
| `TWITTER_ACCESS_SECRET` | Twitter | If enabled |
| `INSTAGRAM_USERNAME` | Instagram | If enabled |
| `INSTAGRAM_PASSWORD` | Instagram | If enabled |
| `FACEBOOK_PAGE_ID` | Facebook | If enabled |
| `FACEBOOK_ACCESS_TOKEN` | Facebook | If enabled |
| `TELEGRAM_BOT_TOKEN` | Telegram | If enabled |
| `TELEGRAM_CHANNEL_ID` | Telegram | If enabled |
| `TIKTOK_SESSION_ID` | TikTok | If enabled |

### Toggle platforms — `config/settings.py`

```python
PLATFORMS = {
    "twitter":   True,
    "instagram": True,
    "facebook":  True,
    "telegram":  True,
    "tiktok":    False,  # stub — not wired up yet
    "youtube":   False,  # stub — not wired up yet
}
```

### Change post times — `config/settings.py`

```python
POST_TIMES = ["08:00", "12:00", "17:00", "20:00"]  # 24-hour local time
```

### Add a niche — `src/niches/niche_config.py`

```python
NICHE_PROFILES["travel"] = {
    "topics": ["budget travel tips", "hidden gems in Europe", "solo travel safety"],
    "tone": "adventurous and inspiring",
    "hashtags": ["#TravelLife", "#Wanderlust", "#TravelTips"],
    "emoji": True,
    "post_format": "tip",   # tip | insight | quote | news
}
```

Then add `"travel"` to the `NICHES` list in `config/settings.py`.

### Add a platform — `src/platforms/`

1. Create `src/platforms/yourplatform.py` with a `post(post_dict) -> bool` function
2. Add it to `PLATFORMS` in `config/settings.py`
3. Import and register it in `src/scheduler/runner.py` under `PLATFORM_MODULES`

---

## Project Structure

```
auto-content-poster/
├── main.py                          CLI entry point
├── mcp_server.py                    MCP server (stdio transport)
├── requirements.txt
├── .env.example
├── CLAUDE.md                        Agent instructions for Claude Code
├── .claude/agents/                  Specialized sub-agents
│   ├── content-reviewer.md
│   ├── niche-builder.md
│   └── platform-debugger.md
├── config/
│   └── settings.py                  API keys · schedule · platform toggles
├── src/
│   ├── cleaner.py                   Log cleanup utility
│   ├── content_generator/
│   │   └── generator.py             Claude-powered post generation
│   ├── niches/
│   │   └── niche_config.py          Niche profiles (topics · tone · hashtags)
│   ├── platforms/
│   │   ├── twitter.py
│   │   ├── instagram.py
│   │   ├── facebook.py
│   │   └── telegram.py
│   └── scheduler/
│       └── runner.py                APScheduler-based posting loop
├── logs/                            Auto-cleaned log output
└── tests/
```

---

## Auto-Clean

Logs accumulate in `logs/`. The cleaner removes `.log` files older than a threshold.

```bash
# CLI
python main.py clean --days 14

# Weekly cron (every Sunday 3 AM)
0 3 * * 0 cd /path/to/auto-content-poster && python main.py clean --days 7
```

Or ask Claude via MCP: *"Clean up log files older than 14 days"*

---

## License

MIT
