"""Kern-Strategie: Faber 10-Monats-SMA (REGELWERK §2).

Regel: Am 1. Handelstag des Monats — Schlusskurs > 10-Monats-SMA -> SPY, sonst BIL.
Keine Eingriffe zwischen den Monatsterminen. Signalquelle SMA-Modul => Kern-Trade (§1).

TODO: Implementierung nach Backtest (OFFENE-PUNKTE: Faber vs. GEM vs. Buy-and-Hold).
"""
