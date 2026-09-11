#!/usr/bin/env python3
"""Neueinstiegs-Detektor (Satellit, Regelwerk §3): Wer ist im Fenster NEU eingestiegen?

Aufruf: python scripts/entry_signals.py [YYYY-MM-DD]   (Default: neuester Snapshot)
Ausgabe: Textreport auf stdout + data/reports/YYYY-MM-DD-entries.json (maschinenlesbar,
         fuer Dashboard/Backtest). Idempotent: gleicher Snapshot -> gleiche Dateien.

Zaehlt nur echte Neueinstiege je (Trader, Instrument) — Tranchen/Nachkaeufe sind kein
Signal. Meldet ein KAUFSIGNAL, wenn >= N Trader der Signal-Kohorte dasselbe Instrument
im Fenster neu eroeffnet haben. Es werden KEINE Orders ausgeloest.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tradingbot.config import load_config
from tradingbot.satellite import UniverseRule, consensus, detect_entries, trading_days_back

REPO = Path(__file__).resolve().parents[1]


def pick_snapshot(arg: str | None) -> Path:
    snaps = REPO / "data" / "snapshots"
    if arg:
        return snaps / arg
    days = sorted(d for d in snaps.iterdir() if d.is_dir()) if snaps.exists() else []
    if not days:
        sys.exit("Kein Snapshot gefunden — erst scripts/snapshot.py laufen lassen.")
    return days[-1]


def main() -> int:
    cfg = load_config()
    sat = cfg["satellite"]
    n_min = int(sat["consensus"]["min_traders_n"])
    window = int(sat["consensus"]["window_trading_days"])
    min_w = float(sat["consensus"]["min_weight_pct"])
    universe = UniverseRule.from_config(sat)

    day = pick_snapshot(sys.argv[1] if len(sys.argv) > 1 else None)
    snap_date = date.fromisoformat(day.name)
    start = trading_days_back(snap_date, window)

    rankings = json.loads((day / "rankings.json").read_text())
    portfolios = json.loads((day / "portfolios.json").read_text())
    instruments = json.loads((day / "instruments.json").read_text())
    types = {r.get("username"): r.get("type") for r in rankings}
    cohort = {u: ps for u, ps in portfolios.items() if ps is not None and types.get(u) == "trader"}

    entries = detect_entries(cohort, instruments, universe, start, min_w)
    hits = consensus(entries, n_min)
    per_inst = Counter(e.instrument_id for e in entries)
    name = lambda iid: instruments.get(str(iid), {}).get("name") or f"ID {iid}"  # noqa: E731

    print(f"Neueinstiege {day.name} — Fenster {start} bis {snap_date} ({window} Handelstage), "
          f"Kohorte {len(cohort)} Trader, Schwelle N>={n_min}, Mindestgewicht {min_w} %")
    print(f"Echte Neueinstiege im Universum: {len(entries)} in {len(per_inst)} Instrumenten "
          f"von {len({e.trader for e in entries})} Tradern")

    if hits:
        print(f"\n*** KAUFSIGNAL ({len(hits)}) ***")
        for iid, es in hits.items():
            print(f"{name(iid)[:38]:38} N={len(es)}  "
                  + ", ".join(f"{e.trader} ({e.first_open:%d.%m.} {e.weight_pct:.1f}%)" for e in es))
    else:
        top = per_inst.most_common(1)[0][1] if per_inst else 0
        print(f"\nKein Kaufsignal (Maximum N={top}).")

    print(f"\n{'Instrument':38} {'N':>3}  Trader (Einstieg, Gewicht)")
    for iid, n in per_inst.most_common(15):
        es = sorted((e for e in entries if e.instrument_id == iid), key=lambda e: e.first_open)
        print(f"{name(iid)[:38]:38} {n:>3}  "
              + ", ".join(f"{e.trader} ({e.first_open:%d.%m.} {e.weight_pct:.1f}%)" for e in es))

    out = REPO / "data" / "reports" / f"{day.name}-entries.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "snapshot": day.name, "window_start": start.isoformat(), "window_end": snap_date.isoformat(),
        "params": {"min_traders_n": n_min, "window_trading_days": window, "min_weight_pct": min_w,
                   "counting_variant": sat["consensus"].get("counting_variant", "A")},
        "cohort_size": len(cohort),
        "signals": [{"instrumentId": iid, "name": name(iid), "n": len(es),
                     "traders": [e.trader for e in es]} for iid, es in hits.items()],
        "entries": [{"trader": e.trader, "instrumentId": e.instrument_id, "name": name(e.instrument_id),
                     "firstOpen": e.first_open.isoformat(), "weightPct": round(e.weight_pct, 4)}
                    for e in sorted(entries, key=lambda e: (e.instrument_id, e.first_open))],
    }, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"\nJSON: {out.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
