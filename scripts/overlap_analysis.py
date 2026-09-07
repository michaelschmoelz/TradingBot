#!/usr/bin/env python3
"""Ueberschneidungsanalyse je Kohorte: Signal (echte Trader) vs. Vergleich (Smart Portfolios).

Aufruf: python scripts/overlap_analysis.py [YYYY-MM-DD]   (Default: neuester Snapshot)
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path


def analyze(title: str, cohort: dict, instruments: dict, n_threshold: int = 5, top: int = 15) -> None:
    holders: dict[int, set] = {}
    lev = Counter()
    for u, ps in cohort.items():
        for p in ps:
            if not p.get("isBuy"):
                continue
            lev[p.get("leverage")] += 1
            holders.setdefault(p["instrumentId"], set()).add(u)
    n = len(cohort)
    counts = Counter({iid: len(us) for iid, us in holders.items()})
    print(f"\n### {title}: {n} Portfolios, "
          f"{sum(len(ps) for ps in cohort.values())} Positionen, {len(holders)} Instrumente (long)")
    print(f"{'Instrument':38} {'Halter':>6} {'Anteil':>7}")
    for iid, c in counts.most_common(top):
        name = instruments.get(str(iid), {}).get("name") or f"ID {iid}"
        print(f"{name[:38]:38} {c:>6} {c / n:>6.0%}")
    dist = Counter(counts.values())
    print("Verteilung:", ", ".join(f"{k}x:{dist[k]}" for k in sorted(dist, reverse=True)))
    print(f"Instrumente mit >={n_threshold} Haltern: {len([c for c in counts.values() if c >= n_threshold])}"
          f" | Hebel: {dict(sorted(lev.items(), key=lambda x: (x[0] is None, x[0])))}")


def main() -> int:
    snaps = Path(__file__).resolve().parents[1] / "data" / "snapshots"
    if len(sys.argv) > 1:
        day = snaps / sys.argv[1]
    else:
        days = sorted(d for d in snaps.iterdir() if d.is_dir()) if snaps.exists() else []
        if not days:
            sys.exit("Kein Snapshot gefunden — erst scripts/snapshot.py laufen lassen.")
        day = days[-1]

    rankings = json.loads((day / "rankings.json").read_text())
    portfolios = json.loads((day / "portfolios.json").read_text())
    instruments = json.loads((day / "instruments.json").read_text())
    types = {r.get("username"): r.get("type") for r in rankings}
    loaded = {u: ps for u, ps in portfolios.items() if ps is not None}

    print(f"Snapshot {day.name} — {len(loaded)} Portfolios geladen, "
          f"{sum(1 for v in portfolios.values() if v is None)} fehlgeschlagen")
    analyze("SIGNAL-KOHORTE (echte Trader)",
            {u: ps for u, ps in loaded.items() if types.get(u) == "trader"}, instruments)
    sp = {u: ps for u, ps in loaded.items() if types.get(u) == "smart-portfolio"}
    if sp:
        analyze("VERGLEICH (Smart Portfolios — speist NICHT das Signal)", sp, instruments, top=10)

    print("\nHinweis: Bestands-Ueberlapp, KEIN Einstiegssignal — das Signal zaehlt NEU")
    print("eroeffnete Positionen binnen 3 Handelstagen (Regelwerk §3).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
