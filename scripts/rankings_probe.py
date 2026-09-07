#!/usr/bin/env python3
"""Sonde: Rankings-Abfrage stufenweise aufbauen — welcher Parameter leert das Ergebnis?

Aufruf: python scripts/rankings_probe.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tradingbot.config import load_config, require_env
from tradingbot.etoro_client import EtoroClient

VARIANTS = [
    ("nur period",              {"period": "LastTwoYears", "pageSize": 10}),
    ("+ sort=-copiers",         {"period": "LastTwoYears", "pageSize": 10, "sort": "-copiers"}),
    ("+ riskScoreMax=6",        {"period": "LastTwoYears", "pageSize": 10, "sort": "-copiers", "riskScoreMax": 6}),
    ("+ copiersMin=1 (unsere)", {"period": "LastTwoYears", "pageSize": 10, "sort": "-copiers", "riskScoreMax": 6, "copiersMin": 1}),
    ("period=OneYearAgo pur",   {"period": "OneYearAgo", "pageSize": 10}),
]


def main() -> int:
    cfg = load_config()
    env = require_env("ETORO_API_KEY", "ETORO_USER_KEY")
    c = EtoroClient(cfg["etoro"]["base_url"], env["ETORO_API_KEY"], env["ETORO_USER_KEY"])
    try:
        for name, params in VARIANTS:
            r = c.get("/api/v2/portfolios/rankings", params)
            try:
                d = r.json()
            except Exception:
                d = {}
            res = d.get("results") or []
            pag = d.get("pagination")
            first = ""
            if res:
                row = res[0]
                first = f" | 1. Zeile: {row.get('username')} copiers={row.get('copiers')} risk={row.get('riskScore')} p2v={row.get('peakToValley')}"
            print(f"{r.status_code}  {name:26} -> {len(res)} Zeilen, pagination={pag}{first}")
            if r.status_code != 200 and not res:
                print(f"      Body: {r.text[:200]}")
            time.sleep(1.1)

        r = c.get("/api/v2/portfolios/rankings/presets")
        d = r.json() if r.status_code == 200 else {}
        names = [p.get("name") for p in (d.get("results") or [])]
        print(f"{r.status_code}  Presets -> {names}")
        return 0
    finally:
        c.close()


if __name__ == "__main__":
    raise SystemExit(main())
