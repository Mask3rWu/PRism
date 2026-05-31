import os
import httpx

BACKEND_URL = os.environ.get("PRISM_BACKEND_URL", "http://localhost:8000")


class PrismClient:
    def __init__(self) -> None:
        self._client = httpx.AsyncClient(base_url=BACKEND_URL, timeout=60.0)

    async def get(self, path: str, params: dict | None = None) -> dict:
        try:
            resp = await self._client.get(path, params=params)
            resp.raise_for_status()
            return resp.json()
        except httpx.ConnectError:
            raise PrismError(
                f"无法连接到 PRism 后端 ({BACKEND_URL})。请先启动后端："
                f"cd backend && conda run -n prism-py311 uvicorn main:app --port 8000"
            )
        except httpx.HTTPStatusError as e:
            detail = ""
            try:
                detail = e.response.json().get("detail", "")
            except Exception:
                pass
            msg = f"后端返回 {e.response.status_code}"
            if detail:
                msg += f": {detail}"
            raise PrismError(msg)
        except httpx.TimeoutException:
            raise PrismError(f"请求超时（{self._client.timeout}秒），后端可能无响应")

    async def post(self, path: str, body: dict | None = None) -> dict:
        try:
            resp = await self._client.post(path, json=body)
            resp.raise_for_status()
            return resp.json()
        except httpx.ConnectError:
            raise PrismError(
                f"无法连接到 PRism 后端 ({BACKEND_URL})。请先启动后端："
                f"cd backend && conda run -n prism-py311 uvicorn main:app --port 8000"
            )
        except httpx.HTTPStatusError as e:
            detail = ""
            try:
                detail = e.response.json().get("detail", "")
            except Exception:
                pass
            msg = f"后端返回 {e.response.status_code}"
            if detail:
                msg += f": {detail}"
            raise PrismError(msg)
        except httpx.TimeoutException:
            raise PrismError(f"请求超时（{self._client.timeout}秒），后端可能无响应")

    async def close(self) -> None:
        await self._client.aclose()


class PrismError(Exception):
    pass
