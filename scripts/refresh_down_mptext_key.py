#!/usr/bin/env python3
"""Check and refresh a down.mptext.top API key for the current project."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import requests


PROJECT_ROOT = Path.cwd()
DEFAULT_ENV_FILE = PROJECT_ROOT / ".env"
DEFAULT_ENV_EXAMPLE = PROJECT_ROOT / ".env.example"
DEFAULT_KEY_ENV = "WECHAT_PUBLIC_API_KEY"
DEFAULT_BASE_URL = "https://down.mptext.top"
DEFAULT_USER_DATA_DIR = Path("~/.codex/down-mptext-chrome-profile").expanduser()


@dataclass
class AuthCheck:
    valid: bool
    code: int | None
    message: str
    payload: dict[str, Any]


def _strip_inline_comment(value: str) -> str:
    quote = ""
    escaped = False
    for index, char in enumerate(value):
        if escaped:
            escaped = False
            continue
        if char == "\\":
            escaped = True
            continue
        if quote:
            if char == quote:
                quote = ""
            continue
        if char in {"'", '"'}:
            quote = char
            continue
        if char == "#" and (index == 0 or value[index - 1].isspace()):
            return value[:index].rstrip()
    return value.strip()


def _unquote_env(value: str) -> str:
    value = _strip_inline_comment(value).strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        value = value[1:-1]
    return value.replace(r"\"", '"').replace(r"\\", "\\")


def load_env_value(path: Path, name: str) -> str:
    if not path.exists():
        return os.environ.get(name, "").strip()
    pattern = re.compile(rf"^\s*(?:export\s+)?{re.escape(name)}\s*=\s*(.*)$")
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        match = pattern.match(raw_line.lstrip("\ufeff"))
        if match:
            return _unquote_env(match.group(1)).strip()
    return os.environ.get(name, "").strip()


def quote_env_value(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', r"\"")
    return f'"{escaped}"'


def update_env_value(path: Path, name: str, value: str, *, backup: bool = True) -> None:
    if not path.exists():
        if DEFAULT_ENV_EXAMPLE.exists():
            shutil.copyfile(DEFAULT_ENV_EXAMPLE, path)
        else:
            path.write_text("", encoding="utf-8")

    if backup:
        shutil.copyfile(path, path.with_suffix(path.suffix + ".bak"))

    lines = path.read_text(encoding="utf-8").splitlines()
    pattern = re.compile(rf"^(\s*#\s*)?(export\s+)?{re.escape(name)}\s*=.*$")
    replacement = f"{name}={quote_env_value(value)}"
    changed = False
    updated: list[str] = []
    for line in lines:
        if not changed and pattern.match(line.lstrip("\ufeff")):
            prefix = "\ufeff" if line.startswith("\ufeff") else ""
            updated.append(prefix + replacement)
            changed = True
        else:
            updated.append(line)
    if not changed:
        if updated and updated[-1].strip():
            updated.append("")
        updated.append(replacement)
    path.write_text("\n".join(updated) + "\n", encoding="utf-8")


def authkey_url(base_url: str) -> str:
    return urljoin(base_url.rstrip("/") + "/", "api/public/v1/authkey")


def _response_code(payload: dict[str, Any]) -> int | None:
    code = payload.get("code")
    if isinstance(code, int):
        return code
    base_resp = payload.get("base_resp")
    if isinstance(base_resp, dict) and isinstance(base_resp.get("ret"), int):
        return base_resp["ret"]
    return None


def _response_message(payload: dict[str, Any]) -> str:
    for key in ("message", "msg", "err_msg"):
        value = payload.get(key)
        if value:
            return str(value)
    base_resp = payload.get("base_resp")
    if isinstance(base_resp, dict):
        return str(base_resp.get("err_msg") or base_resp.get("errmsg") or "")
    return ""


def validate_key(base_url: str, key: str, *, timeout: int = 15) -> AuthCheck:
    if not key:
        return AuthCheck(False, None, "empty key", {})
    try:
        response = requests.get(
            authkey_url(base_url),
            headers={"X-Auth-Key": key},
            cookies={"auth-key": key},
            timeout=timeout,
        )
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        return AuthCheck(False, None, str(exc), {})
    if not isinstance(payload, dict):
        return AuthCheck(False, None, "non-object JSON response", {})
    code = _response_code(payload)
    return AuthCheck(code == 0, code, _response_message(payload), payload)


def query_key_with_cookies(base_url: str, cookies: dict[str, str], *, timeout: int = 15) -> tuple[str, AuthCheck]:
    try:
        response = requests.get(authkey_url(base_url), cookies=cookies, timeout=timeout)
        response.raise_for_status()
        payload = response.json()
    except Exception as exc:
        return "", AuthCheck(False, None, str(exc), {})
    if not isinstance(payload, dict):
        return "", AuthCheck(False, None, "non-object JSON response", {})
    key = first_key_candidate(payload)
    code = _response_code(payload)
    return key, AuthCheck(code == 0, code, _response_message(payload), payload)


def first_key_candidate(obj: Any) -> str:
    preferred_names = {
        "authkey",
        "auth_key",
        "auth-key",
        "apikey",
        "api_key",
        "key",
        "token",
        "value",
    }
    if isinstance(obj, dict):
        for key, value in obj.items():
            normalized = str(key).replace("-", "_").lower()
            if normalized in {name.replace("-", "_") for name in preferred_names}:
                candidate = str(value or "").strip()
                if plausible_key(candidate):
                    return candidate
        for value in obj.values():
            candidate = first_key_candidate(value)
            if candidate:
                return candidate
    if isinstance(obj, list):
        for value in obj:
            candidate = first_key_candidate(value)
            if candidate:
                return candidate
    return ""


def plausible_key(value: str) -> bool:
    if not value or len(value) < 16 or len(value) > 512:
        return False
    return bool(re.fullmatch(r"[A-Za-z0-9._~+/=-]+", value))


def start_driver(browser: str, user_data_dir: str = ""):
    from selenium import webdriver

    browser = browser.lower().strip()
    profile_dir = Path(user_data_dir).expanduser() if user_data_dir else None
    if profile_dir:
        profile_dir.mkdir(parents=True, exist_ok=True)
    if browser == "edge":
        from selenium.webdriver.edge.options import Options

        options = Options()
        if profile_dir:
            options.add_argument(f"--user-data-dir={profile_dir}")
        return webdriver.Edge(options=options)
    if browser == "safari":
        if profile_dir:
            print("Warning: Safari does not support --user-data-dir; persistent login state is browser-managed.")
        return webdriver.Safari()
    if browser == "firefox":
        if profile_dir:
            return webdriver.Firefox(firefox_profile=str(profile_dir))
        return webdriver.Firefox()

    from selenium.webdriver.chrome.options import Options

    options = Options()
    if profile_dir:
        options.add_argument(f"--user-data-dir={profile_dir}")
    return webdriver.Chrome(options=options)


def browser_cookies(driver, base_url: str) -> dict[str, str]:
    host = urlparse(base_url).hostname or ""
    cookies: dict[str, str] = {}
    for cookie in driver.get_cookies():
        name = str(cookie.get("name") or "")
        value = str(cookie.get("value") or "")
        domain = str(cookie.get("domain") or "")
        if not name or not value:
            continue
        if host and domain and host not in domain.lstrip(".") and domain.lstrip(".") not in host:
            continue
        cookies[name] = value
    return cookies


def browser_storage_candidates(driver) -> list[str]:
    script = """
    const out = {};
    for (const storeName of ["localStorage", "sessionStorage"]) {
      const store = window[storeName];
      out[storeName] = {};
      for (let i = 0; i < store.length; i++) {
        const key = store.key(i);
        out[storeName][key] = store.getItem(key);
      }
    }
    return out;
    """
    try:
        stores = driver.execute_script(script)
    except Exception:
        return []
    candidates: list[str] = []
    if not isinstance(stores, dict):
        return candidates
    for store in stores.values():
        if not isinstance(store, dict):
            continue
        for key, value in store.items():
            name = str(key).lower()
            text = str(value or "").strip()
            if any(part in name for part in ("auth", "api", "key", "token")) and plausible_key(text):
                candidates.append(text)
            else:
                candidate = first_key_candidate(_maybe_json(text))
                if candidate:
                    candidates.append(candidate)
    return candidates


def _maybe_json(text: str) -> Any:
    try:
        return json.loads(text)
    except Exception:
        return text


def refresh_with_browser(args) -> str:
    driver = start_driver(args.browser, args.user_data_dir)
    try:
        driver.get(args.login_url or args.base_url)
        if args.user_data_dir:
            print(f"Opened browser with persistent profile: {Path(args.user_data_dir).expanduser()}")
        print("Scan-login to down.mptext.top if the browser is not already logged in, then keep this terminal running.")
        deadline = time.time() + args.wait_seconds
        seen: set[str] = set()
        while time.time() < deadline:
            cookies = browser_cookies(driver, args.base_url)
            candidates: list[str] = []
            cookie_key = cookies.get("auth-key") or cookies.get("auth_key")
            if cookie_key:
                candidates.append(cookie_key)

            endpoint_key, cookie_check = query_key_with_cookies(args.base_url, cookies, timeout=args.timeout)
            if endpoint_key:
                candidates.append(endpoint_key)
            if cookie_check.valid and cookie_key:
                candidates.append(cookie_key)

            candidates.extend(browser_storage_candidates(driver))
            for candidate in candidates:
                if candidate in seen:
                    continue
                seen.add(candidate)
                check = validate_key(args.base_url, candidate, timeout=args.timeout)
                if check.valid:
                    return candidate
            time.sleep(args.poll_seconds)
    finally:
        if not args.keep_browser_open:
            driver.quit()
    raise RuntimeError(f"Timed out after {args.wait_seconds}s without finding a valid auth key.")


def notify(title: str, message: str) -> None:
    if sys.platform == "darwin":
        script = f'display notification {json.dumps(message)} with title {json.dumps(title)}'
        try:
            subprocess.run(["osascript", "-e", script], check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass
        return
    print(f"{title}: {message}")


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="Validate the current env key only.")
    mode.add_argument("--remind", action="store_true", help="Validate the key for scheduled expiry reminders.")
    mode.add_argument("--refresh", action="store_true", help="Open browser login and update .env with a valid key.")
    parser.add_argument("--env-file", default=str(DEFAULT_ENV_FILE), help="Env file to read and update.")
    parser.add_argument("--key-env", default=DEFAULT_KEY_ENV, help="Environment variable name for the API key.")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="down.mptext.top base URL.")
    parser.add_argument("--login-url", default="", help="URL to open for browser login. Defaults to base URL.")
    parser.add_argument("--browser", default=os.environ.get("DOWN_MPTEXT_BROWSER", os.environ.get("WANYOU_SELENIUM_BROWSER", "chrome")), help="chrome, edge, safari, or firefox.")
    parser.add_argument(
        "--user-data-dir",
        default=os.environ.get("DOWN_MPTEXT_USER_DATA_DIR", str(DEFAULT_USER_DATA_DIR)),
        help="Persistent browser profile directory for retaining down.mptext.top login state. Use empty string to disable.",
    )
    parser.add_argument("--timeout", type=int, default=15, help="HTTP timeout in seconds.")
    parser.add_argument("--wait-seconds", type=int, default=600, help="Maximum time to wait for scan-login.")
    parser.add_argument("--poll-seconds", type=int, default=3, help="Browser polling interval.")
    parser.add_argument("--notify", action="store_true", help="Show a desktop notification when --remind finds an invalid key.")
    parser.add_argument("--no-backup", action="store_true", help="Do not create .env.bak before updating.")
    parser.add_argument("--keep-browser-open", action="store_true", help="Leave browser open after refresh.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv or sys.argv[1:])
    env_file = Path(args.env_file).expanduser()
    if not env_file.is_absolute():
        env_file = PROJECT_ROOT / env_file
    current_key = load_env_value(env_file, args.key_env)

    if args.check or args.remind:
        check = validate_key(args.base_url, current_key, timeout=args.timeout)
        if check.valid:
            print(f"{args.key_env} is valid.")
            return 0
        message = f"{args.key_env} is invalid: code={check.code} message={check.message}"
        print(message)
        if args.remind and args.notify:
            notify("down.mptext API key expired", f"{args.key_env} needs refresh in {env_file}")
        return 1

    if current_key:
        check = validate_key(args.base_url, current_key, timeout=args.timeout)
        if check.valid:
            print(f"{args.key_env} is already valid; no update needed.")
            return 0
        print(f"Current {args.key_env} is invalid: code={check.code} message={check.message}")

    new_key = refresh_with_browser(args)
    update_env_value(env_file, args.key_env, new_key, backup=not args.no_backup)
    print(f"Updated {args.key_env} in {env_file}")
    final_check = validate_key(args.base_url, new_key, timeout=args.timeout)
    if not final_check.valid:
        print(f"Warning: saved key did not validate after update: code={final_check.code} message={final_check.message}")
        return 2
    print(f"{args.key_env} is valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
