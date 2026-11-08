"""HttpApiClient: httpx, 5 s timeout, one retry on network errors for GET only."""

from typing import Any
from urllib.parse import quote

import httpx
from pydantic import BaseModel, ValidationError
from svoi_contracts.errors import ApiError, ErrorCode

from svoi_bot.api_client.base import ApiClient, Op
from svoi_bot.api_client.errors import ApiException, ApiTimeout

TIMEOUT_S = 5.0


class HttpApiClient(ApiClient):
    """Talks to the internal API over HTTP."""

    def __init__(
        self,
        base_url: str,
        token: str,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._http = httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {token}"},
            timeout=TIMEOUT_S,
            transport=transport,
        )

    async def aclose(self) -> None:
        """Close the connection pool."""
        await self._http.aclose()

    async def _call(
        self,
        op: Op,
        tg_id: int | None,
        *,
        body: BaseModel | None = None,
        params: dict[str, Any] | None = None,
        path: dict[str, Any] | None = None,
    ) -> Any:
        url = op.path.format(**{k: quote(str(v), safe="") for k, v in (path or {}).items()})
        headers = {} if op.internal or tg_id is None else {"X-Tg-User-Id": str(tg_id)}
        content = body.model_dump_json() if body is not None else None
        if content is not None:
            headers["Content-Type"] = "application/json"
        attempts = 2 if op.method == "GET" else 1
        for attempt in range(attempts):
            try:
                response = await self._http.request(
                    op.method, url, params=params, content=content, headers=headers
                )
                break
            except httpx.TimeoutException as exc:
                raise ApiTimeout(op.name) from exc
            except httpx.TransportError as exc:
                if attempt + 1 == attempts:
                    raise ApiTimeout(op.name) from exc
        return self._parse(op, response)

    @staticmethod
    def _parse(op: Op, response: httpx.Response) -> Any:
        if response.is_error:
            try:
                err = ApiError.model_validate_json(response.content)
            except ValidationError:
                err = ApiError(code=ErrorCode.internal, message=f"HTTP {response.status_code}")
            raise ApiException(err)
        adapter = op.adapter()
        if adapter is None or response.status_code == httpx.codes.NO_CONTENT:
            return None
        return adapter.validate_json(response.content)
