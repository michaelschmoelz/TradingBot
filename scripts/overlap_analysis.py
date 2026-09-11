#!/usr/bin/env python3
"""Ueberschneidungsanalyse (Bestands-Ueberlapp) aus einer gespeicherten Tagesdatei.

Aufruf: python scripts/overlap_analysis.py [YYYY-MM-DD]   (Default: neueste Tagesdatei)
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tradingbot.reports import load_daily, overlap_report

REPO = Path(__file__).resolve().parents[1]


def main() -> int:
    rec = load_daily(REPO, sys.argv[1] if len(sys.argv) > 1 else None)
    print(overlap_report(rec, {k: v.get("name") for k, v in rec["instruments"].items()}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
