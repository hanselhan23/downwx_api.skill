---
name: down-mptext-wechat-key-refresh
description: Check, refresh, and persist the WeChat public-account article crawler API key from down.mptext.top. Use when Codex needs to validate WECHAT_PUBLIC_API_KEY or another env var used for down.mptext.top, handle invalid-session/auth-key failures, open the website for WeChat scan-login, or update the current project's .env with a refreshed公众号文章抓取 API key.
---

# down.mptext WeChat Key Refresh

## Purpose

Use this skill in any project that reads WeChat public-account articles through `down.mptext.top`. It maintains an API key such as `WECHAT_PUBLIC_API_KEY`.

The key belongs to down.mptext.top, is refreshed after website login succeeds, and expires with that website session. This skill never stores WeChat credentials; it only supports browser scan-login and writes the refreshed key into the current project's `.env`.

## Quick Commands

Run commands from the project that owns the `.env`.

Check the current project's key:

```bash
python ~/.codex/skills/down-mptext-wechat-key-refresh/scripts/refresh_down_mptext_key.py --check
```

Open down.mptext.top with a persistent browser profile, extract a refreshed key, validate it, and update `.env`:

```bash
python ~/.codex/skills/down-mptext-wechat-key-refresh/scripts/refresh_down_mptext_key.py --refresh
```

Check for expiry in a scheduled reminder. Add `--notify` on macOS to show a desktop notification when the key is invalid:

```bash
python ~/.codex/skills/down-mptext-wechat-key-refresh/scripts/refresh_down_mptext_key.py --remind --notify
```

Use a different env var, env file, or base URL:

```bash
python ~/.codex/skills/down-mptext-wechat-key-refresh/scripts/refresh_down_mptext_key.py --refresh --key-env MP_TEXT_AUTH_KEY --env-file .env.local --base-url https://down.mptext.top
```

## Workflow

1. Run `--check` before touching login state.
2. If the key is expired or invalid, run `--refresh`.
3. If `--refresh` opens a browser and the persistent profile is already logged in, let the script reuse that login state without scanning.
4. If the browser is not logged in, ask the user to scan the website login QR code.
5. Let the script poll browser cookies, storage, and the auth-key API until it finds a valid key.
6. Confirm that `.env` was updated, then rerun the caller project's WeChat crawler.

## Notes

- Default env file: `./.env` in the current working directory.
- Default env var: `WECHAT_PUBLIC_API_KEY`.
- Default persistent browser profile: `~/.codex/down-mptext-chrome-profile`; override with `--user-data-dir` or `DOWN_MPTEXT_USER_DATA_DIR`.
- Default validation endpoint: `GET https://down.mptext.top/api/public/v1/authkey`.
- API auth may be supplied through `X-Auth-Key` or an `auth-key` cookie.
- A valid response has `code: 0` or `base_resp.ret: 0`; expired auth usually has `code: -1`.
- Each successful website login can refresh the API key, so do not open the login flow when `--check` says the current key is valid.
- Read `references/down-mptext-api.md` only when endpoint behavior or response handling needs clarification.
