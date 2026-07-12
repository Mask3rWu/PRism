"""Review-scoped, read-only tools for Coordinator ReAct runs."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import PurePosixPath
from typing import Any

from backend.agents.tools.change_inventory import build_change_inventory
from backend.services.github.client import (
    fetch_pr_detail,
    fetch_repository_file,
    search_repository_code,
)

MAX_FILE_LINES = 240
MAX_FILE_CHARS = 24_000
MAX_DIFF_HUNKS_PER_FILE = 20
MAX_DIFF_HUNK_CHARS = 6_000


def _safe_path(path: str) -> str:
    candidate = path.strip().replace("\\", "/")
    pure_path = PurePosixPath(candidate)
    if (
        not candidate
        or pure_path.is_absolute()
        or ".." in pure_path.parts
        or any(character in candidate for character in ("?", "#", ":"))
    ):
        raise ValueError("path must be a repository-relative path")
    return candidate


@dataclass
class ReviewContextTools:
    owner: str
    repo: str
    pr_number: int
    project_description: str
    pr_diff: str
    _metadata: dict[str, Any] | None = None
    _calls: list[dict[str, str | int | bool]] = field(default_factory=list)

    def _record(self, name: str, result: object, success: bool = True) -> None:
        size = len(str(result)) if result is not None else 0
        self._calls.append({"tool": name, "success": success, "result_chars": size})

    @property
    def tool_summary(self) -> list[dict[str, str | int | bool]]:
        return list(self._calls)

    async def _get_metadata(self) -> dict[str, Any] | None:
        if self._metadata is None:
            self._metadata = await fetch_pr_detail(self.owner, self.repo, self.pr_number)
        return self._metadata

    async def get_pr_metadata(self) -> dict:
        """Return PR description and immutable base/head commit SHAs."""
        metadata = await self._get_metadata()
        if not metadata:
            result = {"available": False}
            self._record("get_pr_metadata", result, False)
            return result
        result = {
            "available": True,
            "number": self.pr_number,
            "title": metadata.get("title", ""),
            "body": str(metadata.get("body") or "")[:6000],
            "labels": [label.get("name", "") for label in metadata.get("labels", []) if isinstance(label, dict)],
            "base_sha": ((metadata.get("base") or {}).get("sha") or ""),
            "head_sha": ((metadata.get("head") or {}).get("sha") or ""),
        }
        self._record("get_pr_metadata", result)
        return result

    async def get_change_inventory(self, path: str = "") -> dict:
        """Return changed files and full unified-diff hunks, optionally for one changed path."""
        safe_path = _safe_path(path) if path else None
        result = build_change_inventory(self.pr_diff, safe_path)
        for file_item in result["files"]:
            hunks = file_item.get("hunks", [])
            file_item["hunks"] = [
                {**hunk, "patch": str(hunk.get("patch", ""))[:MAX_DIFF_HUNK_CHARS]}
                for hunk in hunks[:MAX_DIFF_HUNKS_PER_FILE]
            ]
            file_item["hunks_truncated"] = len(hunks) > MAX_DIFF_HUNKS_PER_FILE
        self._record("get_change_inventory", result)
        return result

    async def read_repository_file(
        self,
        path: str,
        ref: str = "head",
        start_line: int = 1,
        end_line: int = MAX_FILE_LINES,
    ) -> dict:
        """Read a bounded line range from the PR base or head revision."""
        safe_path = _safe_path(path)
        if ref not in {"base", "head"}:
            raise ValueError("ref must be base or head")
        start = max(1, start_line)
        end = min(max(start, end_line), start + MAX_FILE_LINES - 1)
        metadata = await self._get_metadata()
        sha = ((metadata or {}).get(ref) or {}).get("sha")
        if not sha:
            result = {"available": False, "path": safe_path, "ref": ref}
            self._record("read_repository_file", result, False)
            return result
        content = await fetch_repository_file(self.owner, self.repo, safe_path, str(sha))
        if content is None:
            result = {"available": False, "path": safe_path, "ref": ref}
            self._record("read_repository_file", result, False)
            return result
        lines = content.splitlines()
        selected = "\n".join(lines[start - 1:end])[:MAX_FILE_CHARS]
        result = {
            "available": True,
            "path": safe_path,
            "ref": ref,
            "sha": sha,
            "start_line": start,
            "end_line": min(end, len(lines)),
            "truncated": end < len(lines) or len(selected) >= MAX_FILE_CHARS,
            "content": selected,
        }
        self._record("read_repository_file", result)
        return result

    async def search_repository(self, query: str, path_glob: str = "", max_results: int = 10) -> dict:
        """Search one repository for a short text query and return candidate file paths."""
        if len(query.strip()) > 200:
            raise ValueError("query must be at most 200 characters")
        restricted_qualifiers = ("repo:", "org:", "user:", "fork:")
        if any(qualifier in query.lower() for qualifier in restricted_qualifiers):
            raise ValueError("repository scope qualifiers are not allowed")
        if any(character in path_glob for character in ("?", "#", ":")):
            raise ValueError("path_glob contains unsupported characters")
        results = await search_repository_code(
            self.owner,
            self.repo,
            query,
            path_glob=path_glob.strip(),
            max_results=max(1, min(max_results, 20)),
        )
        result = {"available": results is not None, "results": results or []}
        self._record("search_repository", result, results is not None)
        return result

    async def get_related_tests(self, changed_path: str) -> dict:
        """Find candidate test files related to one changed source path."""
        safe_path = _safe_path(changed_path)
        filename = PurePosixPath(safe_path).stem
        results = await search_repository_code(self.owner, self.repo, filename, path_glob="test", max_results=20)
        candidates = [item["path"] for item in results or [] if "test" in item["path"].lower()]
        result = {"available": results is not None, "changed_path": safe_path, "test_paths": candidates[:20]}
        self._record("get_related_tests", result, results is not None)
        return result

    async def get_project_context(self) -> dict:
        """Return the user-maintained project description available to this review."""
        result = {"project_description": self.project_description}
        self._record("get_project_context", result)
        return result

    def as_langchain_tools(self) -> list[object]:
        """Build tool-call schemas lazily so non-ReAct imports stay lightweight."""
        from langchain_core.tools import tool

        owner = self

        @tool
        async def get_pr_metadata() -> dict:
            """Get PR title, body, labels, and fixed base/head SHAs."""
            return await owner.get_pr_metadata()

        @tool
        async def get_change_inventory(path: str = "") -> dict:
            """Get changed files and unified diff hunks; set path only for a changed file."""
            return await owner.get_change_inventory(path)

        @tool
        async def read_repository_file(path: str, ref: str = "head", start_line: int = 1, end_line: int = 240) -> dict:
            """Read a bounded file range at the PR base or head revision."""
            return await owner.read_repository_file(path, ref, start_line, end_line)

        @tool
        async def search_repository(query: str, path_glob: str = "", max_results: int = 10) -> dict:
            """Search code in this PR repository and return matching file paths."""
            return await owner.search_repository(query, path_glob, max_results)

        @tool
        async def get_related_tests(changed_path: str) -> dict:
            """Find likely test files for a changed file."""
            return await owner.get_related_tests(changed_path)

        @tool
        async def get_project_context() -> dict:
            """Get the project description configured in PRism."""
            return await owner.get_project_context()

        return [
            get_pr_metadata,
            get_change_inventory,
            read_repository_file,
            search_repository,
            get_related_tests,
            get_project_context,
        ]
