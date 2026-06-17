# CLAUDE.md — Agent Instructions for Auto Content Poster

This file is read automatically by Claude Code and any sub-agent in this repo.
Do not delete it — it is the shared brain for every AI coding session here.

---

## What this project does

Auto Content Poster is a Python CLI + MCP server that:
1. Picks a content niche (fitness, crypto, motivation, tech, food)
2. Calls Claude AI to generate platform-native posts
3. Publishes them to Twitter, Instagram, Facebook, and Telegram
4. Runs on a daily schedule or on-demand via CLI / MCP tool call

---

## Data flow (memorize this)

```
Trigger (scheduler | CLI | MCP)
  → runner.run_posting_cycle()             src/scheduler/runner.py
    → random.choice(NICHES)                config/settings.py
    → generate_all_platforms(niche, ...)   src/content_generator/generator.py
      → NICHE_PROFILES[niche]              src/niches/niche_config.py
      → PLATFORM_CONSTRAINTS[platform]     src/content_generator/generator.py
      → client.messages.create(...)        Anthropic SDK (claude-sonnet-4-6)
    → platform_module.post(post_dict)      src/platforms/*.py
```

---

## Key files — read these before making changes

| File | What lives there |
|---|---|
| `config/settings.py` | All env vars, PLATFORMS dict, NICHES list, POST_TIMES |
| `src/niches/niche_config.py` | NICHE_PROFILES — every niche's topics/tone/hashtags |
| `src/content_generator/generator.py` | `generate_post()` and `generate_all_platforms()` — Claude prompt lives here |
| `src/scheduler/runner.py` | `run_posting_cycle()` and `start_scheduler()` |
| `src/platforms/*.py` | Each file has one `post(post_dict) -> bool` function |
| `mcp_server.py` | MCP server — 6 tools exposed to Claude Desktop |
| `src/cleaner.py` | `clean_logs(days)` — removes old .log files |
| `main.py` | CLI: `start`, `post-now`, `preview`, `clean` |

---

## Conventions — always follow these

- Every platform module exports exactly one function: `post(post_dict: dict) -> bool`
- `post_dict` always has keys: `niche`, `platform`, `topic`, `text`, `hashtags`, `needs_image`, `needs_video`
- Never hardcode API keys — use `config/settings.py` which reads from `.env`
- Python 3.11+ required — use modern type hints freely (`list[str]`, `dict[str, bool]`)
- Use `Rich` for all console output — never bare `print()` in runner or CLI code
- Platform modules must not raise — they catch exceptions and return `False`

---

## How to add a new niche

1. Add entry to `NICHE_PROFILES` in `src/niches/niche_config.py`
2. Add niche name string to `NICHES` list in `config/settings.py`
3. Test: `python main.py preview --niche yourniche --platform twitter`

## How to add a new platform

1. Create `src/platforms/yourplatform.py` — one `post(post_dict) -> bool` function
2. Add to `PLATFORMS` in `config/settings.py` (set `True` to enable)
3. Add to `PLATFORM_MODULES` in `src/scheduler/runner.py`
4. Add to `PLATFORM_LIST` in `mcp_server.py`
5. Add to `PLATFORM_CONSTRAINTS` in `src/content_generator/generator.py`

---

## Testing without posting

```bash
# Preview generates the post but never publishes
python main.py preview --niche fitness --platform twitter

# Disable all platforms in config/settings.py to dry-run the full cycle
PLATFORMS = {"twitter": False, "instagram": False, ...}
python main.py post-now
```

There are no automated tests yet — add them to `tests/`.

---

## MCP server quick reference

Run: `python mcp_server.py`
Transport: stdio
Tools: `generate_post`, `generate_all_platforms`, `list_niches`, `list_platforms`, `post_now`, `clean_logs`

---

## What NOT to do

- Do not change the Claude model in `generator.py` without checking token costs
- Do not add retry loops to platform modules — let callers decide on retry
- Do not import `config.settings` in platform modules — pass credentials in or read env directly
- Do not create new files for one-off scripts — extend `main.py` with a new subparser

---

## Specialized sub-agents

Three agents live in `.claude/agents/`. Use them when the task matches:

- **content-reviewer** — review/score generated post quality, check character limits, tone fit
- **niche-builder** — build a fully fleshed-out new niche profile from a topic idea
- **platform-debugger** — diagnose why a platform module is failing to post
