"""Schmaler Client für die Alpaca Trading API (Paper) — Kern-Strategie und Marktdaten.

Leitplanken (REGELWERK §7): Ordergrößen NUR nach Cash-Bestand des Kern-Topfs,
nie nach Buying Power — das Paper-Konto ist technisch ein Margin-Konto (4x), Margin bleibt ungenutzt.
"""

from __future__ import annotations

from typing import Any

import httpx


class AlpacaClient:
    def __init__(self, base_url: str, key_id: str, secret_key: str, timeout: float = 30.0) -> None:
        self._client = httpx.Client(
            base_url=base_url,
            timeout=timeout,
            headers={
                "APCA-API-KEY-ID": key_id,
                "APCA-API-SECRET-KEY": secret_key,
                "Accept": "application/json",
            },
        )

    def get_account(self) -> dict[str, Any]:
        resp = self._client.get("/v2/account")
        resp.raise_for_status()
        return resp.json()

    # TODO: Orders (SPY/BIL-Umschichtung, Regelwerk §2), Positionsabgleich (idempotent),
    #       Marktdaten (IEX) für Kurse/ATR — separate Data-URL, kommt mit dem Kern-Modul.

    def close(self) -> None:
        self._client.close()
