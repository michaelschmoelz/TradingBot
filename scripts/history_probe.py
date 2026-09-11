#!/usr/bin/env python3
"""Sonde: Wie tief reicht die Allokations-Historie der eToro-API je Trader?

Prueft /api/v2/portfolios/{username}/assets/history (taegliche investedPct je Instrument)
fuer einige Trader der aktuellen Signal-Kohorte — entscheidet, ob der Backtest Jahre oder
nur die selbst gesammelten Snapshots zur Verfuegung hat (OFFENE-PUNKTE).

Aufruf: python scripts/history_probe.py [anzahl_trader=3]
Speichert NICHTS (Terms: kein Caching ueber das Noetige hinaus) — nur Kennzahlen auf stdout.
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

REPO = Path(__file__).resolve().parents[1]


def summarize(label: str, data) -> None:
    rows = (data or {}).get("results") or []
    if not rows:
        print(f"  {label}: keine Zeilen (Antwort-Keys: {list(data) if isinstance(data, dict) else type(data).__name__})")
        return
    days = sorted(r["date"] for r in rows)
    n_assets = [len(r.get("assets") or []) for r in rows]
    first, last = date.fromisoformat(days[0]), date.fromisoformat(days[-1])
    span = (last - first).days + 1
    print(f"  {label}: {len(days)} Tage von {days[0]} bis {days[-1]} "
          f"(Kalendertage {span}, Abdeckung {len(days) / span:.0%}), "
          f"Instrumente/Tag min {min(n_assets)} max {max(n_assets)}")
    sample = rows[-1]
    a = (sample.get("assets") or [None])[0]
    print(f"    letzte Zeile: cashPct={sample.get('cashPct')} erstes Asset={a}")


def main() -> int:
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    cfg = load_config()
    env = require_env("ETORO_API_KEY", "ETORO_USER_KEY")
    snaps = sorted(d for d in (REPO / "data" / "snapshots").iterdir() if d.is_dir())
    rankings = json.loads((snaps[-1] / "rankings.json").read_text())
    traders = [r["username"] for r in rankings if r.get("type") == "trader"][:n]

    c = EtoroClient(cfg["etoro"]["base_url"], env["ETORO_API_KEY"], env["ETORO_USER_KEY"])
    try:
        for u in traders:
            print(f"\n{u}")
            for label, params in [
                ("period=LastTwoYears", {"period": "LastTwoYears"}),
                ("minDate=2015-01-01", {"minDate": "2015-01-01", "maxDate": date.today().isoformat()}),
            ]:
                try:
                    summarize(label, c.assets_history(u, **params))
                except Exception as e:  # noqa: BLE001 — Sonde: Fehler anzeigen, weiterlaufen
                    print(f"  {label}: FEHLER {e}")
                time.sleep(1.1)
    finally:
        c.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
