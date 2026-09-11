#!/usr/bin/env python3
"""Tageslauf: Rankings -> Kohorte -> Live-Portfolios (nur im Speicher) -> abgeleitete Daten.

Aufruf: python scripts/daily_run.py            (~10-15 Min wegen Rate-Limit-Pacing)
Schreibt: data/daily/YYYY-MM-DD.json (Kohorte, Kennzahlen, Neueinstiege im Lookback, Signale,
          Instrument-Stammdaten) sowie data/reports/YYYY-MM-DD-overlap.txt / -entries.txt.
Speichert KEINE Portfolios fremder Trader (Entscheidung 2026-09-11, eToro-Terms).
Idempotent: erneuter Lauf am selben Tag ueberschreibt dieselben Dateien. Keine Orders.
"""

from __future__ import annotations

import json
import sys
import time
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tradingbot.config import load_config, require_env
from tradingbot.daily import (build_daily_record, cohort_stats, derive_entries, fetch_portfolios,
                              instrument_map, select_cohort)
from tradingbot.etoro_client import EtoroClient
from tradingbot.reports import (entries_report, evaluate_entries, membership_until,
                                overlap_report, signals_json)
from tradingbot.satellite import trading_days_back

REPO = Path(__file__).resolve().parents[1]


def fetch_rankings(client: EtoroClient, q: dict) -> list[dict]:
    rows = []
    for page in range(1, int(q["pages"]) + 1):
        data = client.rankings(q["period"], sort=q["sort"], page=page, pageSize=q["page_size"],
                               riskScoreMax=q["risk_score_max"], copiersMin=q["copiers_min"])
        batch = data.get("results") or data.get("items") or data.get("rankings") or data
        if isinstance(batch, dict):
            batch = batch.get("items", [])
        rows.extend(batch)
        print(f"Rankings Seite {page}: {len(batch)} Zeilen")
        time.sleep(1.1)
    return rows


def fetch_portfolio_with_backoff(client: EtoroClient, username: str, attempts: int = 4) -> dict:
    for n in range(attempts):
        resp = client.get(f"/api/v1/user-info/people/{username}/portfolio/live")
        if resp.status_code == 429:
            wait = float(resp.headers.get("Retry-After") or 30 * (n + 1))
            print(f"      429 — warte {wait:.0f}s ...")
            time.sleep(wait)
            continue
        resp.raise_for_status()
        return resp.json()
    raise RuntimeError(f"429 auch nach {attempts} Versuchen")


def main() -> int:
    cfg = load_config()
    env = require_env("ETORO_API_KEY", "ETORO_USER_KEY")
    sat = cfg["satellite"]
    today = date.today()
    lookback_start = trading_days_back(today, int(sat["consensus"]["entries_lookback_trading_days"]))

    client = EtoroClient(cfg["etoro"]["base_url"], env["ETORO_API_KEY"], env["ETORO_USER_KEY"])
    try:
        cohort = select_cohort(fetch_rankings(client, sat["ranking_query"]), sat)
        traders = [r["username"] for r in cohort if r["type"] == "trader"]
        smarts = [r["username"] for r in cohort if r["type"] == "smart-portfolio"]
        print(f"Signal-Kohorte (Trader): {len(traders)}, Vergleich (Smart Portfolios): {len(smarts)}")

        portfolios = fetch_portfolios(lambda u: fetch_portfolio_with_backoff(client, u),
                                      traders + smarts)
        ids = {int(p["instrumentId"]) for ps in portfolios.values() if ps for p in ps
               if p.get("instrumentId") is not None}
        instruments = instrument_map(client.instruments(), ids)
    finally:
        client.close()

    # Ableitungen — ab hier keine API mehr, Rohdaten verlassen den Arbeitsspeicher nicht
    pf_traders = {u: portfolios[u] for u in traders}
    pf_smarts = {u: portfolios[u] for u in smarts}
    entries = derive_entries(pf_traders, instruments, lookback_start)
    rec = build_daily_record(
        today, cohort, cohort_stats(pf_traders), cohort_stats(pf_smarts) if smarts else None,
        entries, lookback_start, signals=[], instruments=instruments,
        params={"top_k": sat["top_k"], "consensus": sat["consensus"], "universe": sat["universe"]},
    )
    del portfolios, pf_traders, pf_smarts

    daily_dir = REPO / "data" / "daily"
    daily_dir.mkdir(parents=True, exist_ok=True)
    out = daily_dir / f"{today.isoformat()}.json"
    out.write_text(json.dumps(rec, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    # Detektor (Regelwerk §3, v0.8) auf den abgeleiteten Daten inkl. heutiger Kohorte
    ents, hits, brought_in, start = evaluate_entries(rec, sat, membership_until(REPO, today))
    rec["signals"] = signals_json(hits, {k: v.get("name") for k, v in instruments.items()})
    out.write_text(json.dumps(rec, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    reports = REPO / "data" / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    names = {k: v.get("name") for k, v in instruments.items()}
    ov = overlap_report(rec, names)
    en = entries_report(rec, sat, ents, hits, brought_in, start)
    (reports / f"{today.isoformat()}-overlap.txt").write_text(ov + "\n", encoding="utf-8")
    (reports / f"{today.isoformat()}-entries.txt").write_text(en + "\n", encoding="utf-8")
    print("\n" + ov + "\n\n" + en + f"\n\nTagesdatei: {out.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
