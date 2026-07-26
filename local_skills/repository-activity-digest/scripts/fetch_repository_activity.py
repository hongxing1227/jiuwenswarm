#!/usr/bin/env python3
"""Fetch recent GitHub issues and pull requests as deterministic JSON."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

_USER_AGENT = "jiuwenswarm-repository-activity-digest/1.0"


def _configure_utf8_stdio() -> None:
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            reconfigure(encoding="utf-8", errors="backslashreplace")


def _parse_utc(value: str) -> datetime:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _format_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _read_state(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_state(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        delete=False,
    ) as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
        temp_path = Path(handle.name)
    temp_path.replace(path)


def _request_json(url: str, token: str) -> list[dict[str, Any]]:
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": _USER_AGENT,
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        detail = exc.read(4096).decode("utf-8", errors="replace")
        raise RuntimeError(f"GitHub API returned HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"GitHub API request failed: {exc.reason}") from exc
    if not isinstance(payload, list):
        raise RuntimeError("GitHub API returned an unexpected non-list response")
    return [item for item in payload if isinstance(item, dict)]


def _item_timestamp(item: dict[str, Any], mode: str) -> datetime | None:
    raw = item.get("created_at" if mode == "created" else "updated_at")
    if not isinstance(raw, str) or not raw:
        return None
    try:
        return _parse_utc(raw)
    except ValueError:
        return None


def _compact_item(item: dict[str, Any], mode: str) -> dict[str, Any]:
    labels = item.get("labels")
    label_names = []
    if isinstance(labels, list):
        for label in labels:
            if isinstance(label, dict) and label.get("name"):
                label_names.append(str(label["name"]))
    user = item.get("user")
    author = str(user.get("login") or "") if isinstance(user, dict) else ""
    kind = "pull_request" if isinstance(item.get("pull_request"), dict) else "issue"
    return {
        "kind": kind,
        "number": int(item.get("number") or 0),
        "title": str(item.get("title") or "").strip(),
        "url": str(item.get("html_url") or "").strip(),
        "state": str(item.get("state") or "").strip(),
        "author": author,
        "labels": label_names,
        "created_at": str(item.get("created_at") or ""),
        "updated_at": str(item.get("updated_at") or ""),
        "activity_at": _format_utc(
            _item_timestamp(item, mode) or datetime.now(timezone.utc)
        ),
        "draft": bool(item["draft"]) if "draft" in item else None,
    }


def _fetch(
    *,
    repo: str,
    start: datetime,
    end: datetime,
    mode: str,
    api_base: str,
    token: str,
    max_pages: int,
) -> list[dict[str, Any]]:
    sort_key = "created" if mode == "created" else "updated"
    results: list[dict[str, Any]] = []
    for page in range(1, max_pages + 1):
        query: dict[str, str | int] = {
            "state": "all",
            "sort": sort_key,
            "direction": "desc",
            "per_page": 100,
            "page": page,
        }
        if mode == "updated":
            query["since"] = _format_utc(start)
        encoded_repo = "/".join(
            urllib.parse.quote(part, safe="") for part in repo.split("/")
        )
        url = (
            f"{api_base.rstrip('/')}/repos/{encoded_repo}/issues?"
            f"{urllib.parse.urlencode(query)}"
        )
        page_items = _request_json(url, token)
        if not page_items:
            break

        timestamps: list[datetime] = []
        for item in page_items:
            item_time = _item_timestamp(item, mode)
            if item_time is None:
                continue
            timestamps.append(item_time)
            if start <= item_time <= end:
                results.append(_compact_item(item, mode))
        if timestamps and min(timestamps) < start:
            break
    return results


def _self_test() -> None:
    sample = {
        "number": 42,
        "title": "Add Slack automation",
        "html_url": "https://github.com/example/repo/pull/42",
        "state": "open",
        "user": {"login": "octocat"},
        "labels": [{"name": "enhancement"}],
        "created_at": "2026-07-25T10:00:00Z",
        "updated_at": "2026-07-25T11:00:00Z",
        "pull_request": {"url": "https://api.github.com/pulls/42"},
        "draft": True,
    }
    compact = _compact_item(sample, "created")
    assert compact["kind"] == "pull_request"
    assert compact["number"] == 42
    assert compact["labels"] == ["enhancement"]
    assert compact["activity_at"] == "2026-07-25T10:00:00Z"
    print("self-test: ok")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", help="GitHub repository in owner/name form")
    parser.add_argument("--hours", type=float, default=24.0)
    parser.add_argument("--mode", choices=("created", "updated"), default="created")
    parser.add_argument("--until", help="UTC ISO-8601 end time; defaults to now")
    parser.add_argument("--state-file", type=Path)
    parser.add_argument("--api-base", default="https://api.github.com")
    parser.add_argument("--token-env", default="GITHUB_TOKEN")
    parser.add_argument("--max-pages", type=int, default=10)
    parser.add_argument("--self-test", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if args.self_test:
        _self_test()
        return 0
    if not args.repo or args.repo.count("/") != 1:
        raise SystemExit("--repo must use owner/name format")
    if args.hours <= 0:
        raise SystemExit("--hours must be positive")
    if args.max_pages <= 0:
        raise SystemExit("--max-pages must be positive")

    end = _parse_utc(args.until) if args.until else datetime.now(timezone.utc)
    requested_start = end - timedelta(hours=args.hours)
    state = _read_state(args.state_file)
    last_success_raw = state.get("last_success_utc")
    last_success = None
    if isinstance(last_success_raw, str):
        try:
            last_success = _parse_utc(last_success_raw)
        except ValueError:
            last_success = None
    start = min(requested_start, last_success) if last_success else requested_start
    seen = {str(item) for item in state.get("seen", []) if isinstance(item, (str, int))}

    items = _fetch(
        repo=args.repo,
        start=start,
        end=end,
        mode=args.mode,
        api_base=args.api_base,
        token=os.environ.get(args.token_env, "").strip(),
        max_pages=args.max_pages,
    )
    fresh_items = [
        item
        for item in items
        if f"{item['kind']}:{item['number']}:{args.mode}:{item['activity_at']}"
        not in seen
    ]
    issues = [item for item in fresh_items if item["kind"] == "issue"]
    pull_requests = [item for item in fresh_items if item["kind"] == "pull_request"]
    output = {
        "ok": True,
        "repository": args.repo,
        "mode": args.mode,
        "window": {
            "requested_hours": args.hours,
            "start_utc": _format_utc(start),
            "end_utc": _format_utc(end),
            "catch_up_from_state": bool(
                last_success and last_success < requested_start
            ),
        },
        "counts": {
            "issues": len(issues),
            "pull_requests": len(pull_requests),
            "total": len(fresh_items),
        },
        "issues": issues,
        "pull_requests": pull_requests,
    }
    json.dump(output, sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")

    if args.state_file is not None:
        new_seen = list(seen)
        new_seen.extend(
            f"{item['kind']}:{item['number']}:{args.mode}:{item['activity_at']}"
            for item in fresh_items
        )
        _write_state(
            args.state_file,
            {
                "last_success_utc": _format_utc(end),
                "seen": new_seen[-2000:],
            },
        )
    return 0


if __name__ == "__main__":
    _configure_utf8_stdio()
    try:
        raise SystemExit(main())
    except (RuntimeError, ValueError) as exc:
        json.dump({"ok": False, "error": str(exc)}, sys.stderr, ensure_ascii=False)
        sys.stderr.write("\n")
        raise SystemExit(1) from exc
