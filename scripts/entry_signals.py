#!/usr/bin/env python3
"""Neueinstiegs-Detektor offline: Regelwerk §3 (v0.8) auf eine gespeicherte Tagesdatei anwenden.

Aufruf: python scripts/entry_signals.py [YYYY-MM-DD]   (Default: neueste Tagesdatei)
Liest data/daily/*.json (abgeleitete Daten, keine Portfolios), schreibt
data/reports/YYYY-MM-DD-entries.txt und aktualisiert `signals` in der Tagesdatei.
Nuetzlich, um Parameteraenderungen (N, Fenster, Universum) rueckwirkend zu bewerten —
der Lookback der gespeicherten Neueinstiege (entries_lookback_trading_days) begrenzt das Fenster.
Es werden KEINE Orders ausgeloest.
"""

from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tradingbot.config import load_config
from tradingbot.reports import (entries_report, evaluate_entries, load_daily, membership_until,
                                signals_json)

REPO = Path(__file__).resolve().parents[1]


def main() -> int:
    sat = load_config()["satellite"]
    rec = load_daily(REPO, sys.argv[1] if len(sys.argv) > 1 else None)
    day = date.fromisoformat(rec["date"])
    if int(sat["consensus"]["window_trading_days"]) > int(sat["consensus"]["entries_lookback_trading_days"]):
        sys.exit("Fenster groesser als der gespeicherte Lookback — nicht rueckwirkend auswertbar.")

    ents, hits, brought_in, start = evaluate_entries(rec, sat, membership_until(REPO, day))
    names = {k: v.get("name") for k, v in rec["instruments"].items()}
    rec["signals"] = signals_json(hits, names)
    (REPO / "data" / "daily" / f"{rec['date']}.json").write_text(
        json.dumps(rec, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    text = entries_report(rec, sat, ents, hits, brought_in, start)
    out = REPO / "data" / "reports" / f"{rec['date']}-entries.txt"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(text + "\n", encoding="utf-8")
    print(text + f"\n\nReport: {out.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
