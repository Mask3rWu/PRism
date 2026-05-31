import json
import subprocess

from mcp.server.fastmcp import FastMCP

from backend.mcp.client import PrismClient, PrismError

mcp = FastMCP("PRism")

_client: PrismClient | None = None


def _get_client() -> PrismClient:
    global _client
    if _client is None:
        _client = PrismClient()
    return _client


def _get_git_remote_url() -> str | None:
    """获取 git remote origin 的 URL 字符串。"""
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True, text=True, timeout=5,
        )
        if result.returncode != 0:
            return None
        return result.stdout.strip()
    except Exception:
        return None


async def _detect_project_id(client: PrismClient) -> int | None:
    """通过 git remote URL 调用 lookup API 匹配 PRism 项目。"""
    url = _get_git_remote_url()
    if not url:
        return None
    try:
        data = await client.get("/api/projects/lookup", params={"url": url})
        return data["id"]
    except PrismError:
        return None


@mcp.tool()
async def get_current_project() -> str:
    """通过当前仓库的 git remote origin 自动识别 PRism 中的项目。

    无需参数，自动解析 git remote URL 并匹配项目。
    """
    client = _get_client()
    url = _get_git_remote_url()
    if not url:
        return "无法解析 git remote origin，请确保当前目录是 GitHub 仓库。"
    project_id = await _detect_project_id(client)
    if project_id is None:
        return f"未在 PRism 中找到匹配项目。git remote: {url}"
    try:
        data = await client.get(f"/api/projects/{project_id}")
        return json.dumps(data, ensure_ascii=False, indent=2)
    except PrismError as e:
        return str(e)


@mcp.tool()
async def list_projects(
    search: str = "",
    tag: list[str] | None = None,
    favorite: bool = False,
    page: int = 1,
    per_page: int = 12,
) -> str:
    """列出所有项目，支持按名称搜索、标签和收藏筛选。

    Args:
        search: 按项目名称或仓库名搜索
        tag: 按标签筛选（可多个）
        favorite: 仅显示收藏的项目
        page: 页码（从 1 开始）
        per_page: 每页数量（1-100）
    """
    client = _get_client()
    params: dict = {"search": search, "favorite": str(favorite).lower(), "page": page, "per_page": per_page}
    if tag:
        params["tag"] = tag
    try:
        data = await client.get("/api/projects", params=params)
        return json.dumps(data, ensure_ascii=False, indent=2)
    except PrismError as e:
        return str(e)


@mcp.tool()
async def get_project(project_id: int | None = None) -> str:
    """获取单个项目的详细信息。不传 project_id 时自动从 git remote 检测当前项目。

    Args:
        project_id: 项目 ID（可选，不传则自动检测）
    """
    client = _get_client()
    if project_id is None:
        project_id = await _detect_project_id(client)
        if project_id is None:
            return "未指定项目 ID 且无法从 git remote 自动检测项目。"
    try:
        data = await client.get(f"/api/projects/{project_id}")
        return json.dumps(data, ensure_ascii=False, indent=2)
    except PrismError as e:
        return str(e)


@mcp.tool()
async def list_pull_requests(
    project_id: int | None = None,
    page: int = 1,
    per_page: int = 30,
    state: str = "open",
    search: str = "",
    author: str = "",
) -> str:
    """列出项目的 Pull Request。不传 project_id 时自动从 git remote 检测当前项目。

    返回结果中每个 PR 包含 review_id 字段，可传给 get_review_detail 获取审核结果。

    Args:
        project_id: 项目 ID（可选，不传则自动检测）
        page: 页码（从 1 开始）
        per_page: 每页数量（1-100）
        state: PR 状态（open/closed/all）
        search: 按标题搜索
        author: 按作者筛选
    """
    client = _get_client()
    if project_id is None:
        project_id = await _detect_project_id(client)
        if project_id is None:
            return "未指定项目 ID 且无法从 git remote 自动检测项目。"
    params: dict = {"page": page, "per_page": per_page, "state": state, "search": search, "author": author}
    try:
        data = await client.get(f"/api/projects/{project_id}/pulls", params=params)
        return json.dumps(data, ensure_ascii=False, indent=2)
    except PrismError as e:
        return str(e)


@mcp.tool()
async def get_review_detail(review_id: int) -> str:
    """获取 review 的完整结果，包括总结、风险分析、问题检测和测试建议。

    Args:
        review_id: Review ID（可从 PR 列表的 review_id 字段获取）
    """
    client = _get_client()
    try:
        data = await client.get(f"/api/reviews/{review_id}")
        return json.dumps(data, ensure_ascii=False, indent=2)
    except PrismError as e:
        return str(e)


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
