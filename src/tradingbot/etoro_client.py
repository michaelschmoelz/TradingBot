"""Schmaler Client für die eToro Public API (Satellit, NUR Demo-Modus).

Header je Request: x-api-key, x-user-key, x-request-id (eindeutig), Accept: application/json.
Rate-Limit laut Doku 60 Requests/60 s (geteilt) — Abfragen bündeln, Snapshot 1x/Tag.
Endpunkt-Pfade: siehe api-portal.etoro.com (OpenAPI-Referenz).
"""

from __future__ import annotations

import uuid
from typing import Any

import httpx


class EtoroClient:
    def __init__(self, base_url: str, api_key: str, user_key: str, timeout: float = 30.0) -> None:
        self._client = httpx.Client(
            base_url=base_url,
            timeout=timeout,
            headers={
                "x-api-key": api_key,
                "x-user-key": user_key,
                "Accept": "application/json",
            },
        )

    def get(self, path: str, params: dict[str, Any] | None = None) -> httpx.Response:
        return self._client.get(path, params=params, headers={"x-request-id": str(uuid.uuid4())})

    # TODO (Analyse-Phase): rankings(), user_portfolio(), user_stats()
    # TODO (Plan-B-De-Risking): Demo-Order platzieren/schliessen (/api/v1/trading, Demo-Pfad)

    def close(self) -> None:
        self._client.close()
