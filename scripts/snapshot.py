#!/usr/bin/env python3
"""Tages-Snapshot: Top-K-Trader nach Qualitaetsfilter + deren Live-Portfolios.

Aufruf: python scripts/snapshot.py            (dauert ~1-2 Min wegen Rate-Limit-Pacing)
Ablage: data/snapshots/YYYY-MM-DD/  (rankings.json, portfolios.json, instruments.json)
Idempotent: erneuter Lauf am selben Tag ueberschreibt denselben Ordner.
Datensparsam (eToro-Terms): nur regel-/backtestrelevante Felder werden gespeichert.
"""

from __future__ import annotations

import json
import sys
import time
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tradingbot.config import load_config, require_env
from tradingbot.etoro_client import EtoroClient

RANK_FIELDS = ["cid", "username", "gain", "riskScore", "copiers", "winRatio",
               "peakToValley", "trades", "aumValue", "lastActivity", "popularInvestor"]
POS_FIELDS = ["positionId", "instrumentId", "isBuy", "leverage", "investmentPct", "openTimestamp"]


def main() -> int:
    cfg = load_config()
    env = require_env("ETORO_API_KEY", "ETORO_USER_KEY")
    sat = cfg["satellite"]
    q = sat["ranking_query"]
    top_k = sat["top_k"]

    out = Path(__file__).resolve().parents[1] / "data" / "snapshots" / date.today().isoformat()
    out.mkdir(parents=True, exist_ok=True)

    client = EtoroClient(cfg["etoro"]["base_url"], env["ETORO_API_KEY"], env["ETORO_USER_KEY"])
    try:
        # 1) Rankings holen (mehrere Seiten), serverseitig grob vorfiltern
        rows = []
        for page in range(1, int(q["pages"]) + 1):
            data = client.rankings(
                q["period"], sort=q["sort"], page=page, pageSize=q["page_size"],
                riskScoreMax=q["risk_score_max"], copiersMin=q["copiers_min"],
            )
            batch = data.get("items") or data.get("rankings") or data
            if isinstance(batch, dict):
                batch = batch.get("items", [])
            if not batch and page == 1:
                print("WARNUNG: unerwartetes Antwortformat, Top-Level-Keys:",
                      list(data.keys()) if isinstance(data, dict) else type(data).__name__)
            rows.extend(batch)
            print(f"Rankings Seite {page}: {len(batch)} Zeilen")
            time.sleep(1.1)

        # 2) Clientseitiger Qualitaetsfilter (Regelwerk §3)
        def ok(r):
            dd = r.get("peakToValley")
            return dd is not None and dd <= q["max_drawdown_pct"]

        filtered = [r for r in rows if ok(r)]
        top = filtered[:top_k]
        print(f"Nach Drawdown-Filter: {len(filtered)} — Top-K genommen: {len(top)}")
        (out / "rankings.json").write_text(json.dumps(
            [{k: r.get(k) for k in RANK_FIELDS} for r in top], indent=1))

        # 3) Live-Portfolios der Top-K (dediziertes Limit 60/60s -> Pacing)
        portfolios = {}
        for i, r in enumerate(top, 1):
            u = r.get("username")
            if not u:
                continue
            try:
                pf = client.user_live_portfolio(u)
                positions = pf.get("positions") or []
                portfolios[u] = [{k: p.get(k) for k in POS_FIELDS} for p in positions]
                print(f"  [{i}/{len(top)}] {u}: {len(positions)} Positionen")
            except Exception as exc:  # noqa: BLE001 — einzelner Trader darf fehlen
                print(f"  [{i}/{len(top)}] {u}: FEHLER {exc}")
                portfolios[u] = None
            time.sleep(1.1)
        (out / "portfolios.json").write_text(json.dumps(portfolios, indent=1))

        # 4) Instrument-Mapping nur fuer vorkommende IDs
        ids = {p["instrumentId"] for ps in portfolios.values() if ps for p in ps
               if p.get("instrumentId") is not None}
        inst = client.instruments()
        items = inst.get("instrumentDisplayDatas", inst if isinstance(inst, list) else [])
        mapping = {str(it["instrumentID"]): {
            "name": it.get("instrumentDisplayName"),
            "typeId": it.get("instrumentTypeID"),
            "exchangeId": it.get("exchangeID"),
        } for it in items if it.get("instrumentID") in ids}
        (out / "instruments.json").write_text(json.dumps(mapping, indent=1))

        print(f"\nSnapshot gespeichert unter {out}")
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    raise SystemExit(main())
