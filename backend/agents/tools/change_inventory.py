"""Deterministic unified-diff parsing for Coordinator context tools."""

from __future__ import annotations

import re

_DIFF_HEADER = re.compile(r"^diff --git a/(.+) b/(.+)$")
_HUNK_HEADER = re.compile(r"^@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@(.*)$")


def build_change_inventory(pr_diff: str, path: str | None = None) -> dict:
    """Return a bounded, factual inventory of changed files and their hunks."""
    files: list[dict] = []
    current: dict | None = None
    current_hunk: dict | None = None

    def append_file() -> None:
        nonlocal current
        if current is None:
            return
        file_path = current["path"]
        if path is None or path == file_path:
            files.append(current)
        current = None

    for line in pr_diff.splitlines():
        match = _DIFF_HEADER.match(line)
        if match:
            append_file()
            old_path, new_path = match.groups()
            current = {
                "path": new_path,
                "old_path": old_path,
                "status": "modified",
                "additions": 0,
                "deletions": 0,
                "hunks": [],
            }
            current_hunk = None
            continue

        if current is None:
            continue
        if line == "--- /dev/null":
            current["old_path"] = "/dev/null"
            continue
        if line.startswith("--- "):
            current["old_path"] = line[4:].removeprefix("a/")
            continue
        if line.startswith("+++ "):
            if line == "+++ /dev/null":
                current["status"] = "deleted"
                current["path"] = current["old_path"]
            else:
                current["path"] = line[4:].removeprefix("b/")
            continue
        match = _HUNK_HEADER.match(line)
        if match:
            old_start, new_start, header = match.groups()
            current_hunk = {
                "old_start": int(old_start),
                "new_start": int(new_start),
                "header": header.strip(),
                "lines": [line],
            }
            current["hunks"].append(current_hunk)
            continue
        if line.startswith("+") and not line.startswith("+++"):
            current["additions"] += 1
        elif line.startswith("-") and not line.startswith("---"):
            current["deletions"] += 1
        if current_hunk is not None:
            current_hunk["lines"].append(line)

    append_file()
    for item in files:
        if item["old_path"] == "/dev/null":
            item["status"] = "added"
        item["hunks"] = [
            {
                **hunk,
                "patch": "\n".join(hunk.pop("lines")),
            }
            for hunk in item["hunks"]
        ]

    return {
        "changed_file_count": len(files),
        "files": files,
        "total_additions": sum(item["additions"] for item in files),
        "total_deletions": sum(item["deletions"] for item in files),
    }


def compact_inventory(inventory: dict) -> dict:
    """Keep the initial model input small while leaving full hunks in the tool."""
    return {
        "changed_file_count": inventory.get("changed_file_count", 0),
        "total_additions": inventory.get("total_additions", 0),
        "total_deletions": inventory.get("total_deletions", 0),
        "files": [
            {
                "path": item.get("path", ""),
                "status": item.get("status", "modified"),
                "additions": item.get("additions", 0),
                "deletions": item.get("deletions", 0),
                "hunk_headers": [hunk.get("header", "") for hunk in item.get("hunks", [])[:8]],
            }
            for item in inventory.get("files", [])[:200]
        ],
    }
