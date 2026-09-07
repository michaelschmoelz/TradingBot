#!/usr/bin/env python3
"""Ueberschneidungsanalyse: Wie stark ueberlappen die Long-Positionen der Top-K?

Aufruf: python scripts/overlap_analysis.py [YYYY-MM-DD]   (Default: neuester Snapshot)
Beantwortet die Kernfrage der Analyse-Phase (OFFENE-PUNKTE): Gibt es ueberhaupt
gemeinsame Positionen, und wie konzentriert sind sie?
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path


def main() -> int:
    snaps = Path(__file__).resolve().parents[1] / "data" / "snapshots"
    if len(sys.argv) > 1:
        day = snaps / sys.argv[1]
    else:
        days = sorted(d for d in snaps.iterdir() if d.is_dir()) if snaps.exists() else []
        if not days:
            sys.exit("Kein Snapshot gefunden — erst scripts/snapshot.py laufen lassen.")
        day = days[-1]

    portfolios = json.loads((day / "portfolios.json").read_text())
    instruments = json.loads((day / "instruments.json").read_text())
    traders = {u: ps for u, ps in portfolios.items() if ps is not None}

    holders: dict[int, set] = {}
    lev_counter = Counter()
    for u, ps in traders.items():
        for p in ps:
            if not p.get("isBuy"):
                continue
            lev_counter[p.get("leverage")] += 1
            holders.setdefault(p["instrumentId"], set()).add(u)

    n = len(traders)
    counts = Counter({iid: len(us) for iid, us in holders.items()})
    print(f"Snapshot {day.name}: {n} Trader mit Portfolio, "
          f"{sum(len(ps) for ps in traders.values())} Positionen, "
          f"{len(holders)} verschiedene Instrumente (long)\n")

    print(f"{'Instrument':38} {'Halter':>6} {'Anteil':>7}")
    for iid, c in counts.most_common(20):
        name = instruments.get(str(iid), {}).get("name") or f"ID {iid}"
        print(f"{name[:38]:38} {c:>6} {c / n:>6.0%}")

    dist = Counter(counts.values())
    print("\nVerteilung (x Trader halten dasselbe Instrument -> Anzahl Instrumente):")
    for k in sorted(dist, reverse=True):
        print(f"  {k:>3} Trader: {dist[k]} Instrumente")

    print("\nHebel-Verteilung der Long-Positionen:", dict(sorted(lev_counter.items(), key=lambda x: (x[0] is None, x[0]))))
    thresh = [c for c in counts.values() if c >= 5]
    print(f"\nInstrumente mit >=5 Haltern (unser N): {len(thresh)}")
    print("Hinweis: Das ist ein Bestands-Ueberlapp (Snapshot), noch KEIN Einstiegssignal —")
    print("das Signal zaehlt NEU eroeffnete Positionen binnen 3 Handelstagen (Regelwerk §3).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
