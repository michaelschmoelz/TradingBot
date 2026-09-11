"""Satellit: Konsens-Signale der eToro-Top-Trader (REGELWERK §3–§6).

Einstieg: >= N der Top-K eröffnen NEU dieselbe Aktie binnen 3 Handelstagen.
Risiko: 1 % je Trade, ATR-Skalierung, max 10 %/Position, max 10 Positionen, 30 %/Sektor.
Exits (Priorität): Signal-Exit, 2.5x-ATR-Stop, 3x-ATR-Trailing, 30-Tage-Zeit-Stop.
Circuit Breaker: -12 % vom Höchststand => alles schließen, Review.
Stops führt der Bot selbst (kein Verlass auf Venue-Orderarten).

Dieses Modul enthält die reine Signal-Logik (ohne I/O), damit sie testbar bleibt und
vom Detektor-Skript, vom Backtest und später vom Bot gleich verwendet wird.

Neueinstiegs-Detektor (Entscheidung 2026-09-09, OFFENE-PUNKTE):
- Aggregation je (Trader, Instrument), nicht je Position — Positionen sind Tranchen
  (Sparplan, Nachkauf, Ordersplitting). Einstieg = ältester openTimestamp je
  Trader/Instrument liegt im Fenster. Nachkäufe zählen nicht (Zählvariante A).
- Nur Long (isBuy=true), Hebel egal (Regelwerk v0.7).
- Universum: Aktien/ETFs an US-Börsen; breite Index-ETFs ausgeschlossen.
- Mindest-Gewicht je (Trader, Instrument) gegen Staub-Positionen.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any, Iterable


def parse_open_timestamp(ts: str) -> datetime:
    """eToro liefert variable Nachkommastellen ('2021-10-01T18:31:05.3Z') — nur Sekunden nutzen."""
    return datetime.strptime(ts[:19], "%Y-%m-%dT%H:%M:%S")


def trading_days_back(day: date, n: int) -> date:
    """Erster Tag eines Fensters von n Handelstagen, das mit `day` endet (Mo–Fr; Feiertage
    werden nicht berücksichtigt — das Fenster ist dann höchstens einen Tag zu kurz)."""
    if n < 1:
        raise ValueError("Fenster muss >= 1 Handelstag sein")
    d = day
    while d.weekday() >= 5:  # auf letzten Werktag zurück
        d -= timedelta(days=1)
    remaining = n - 1
    while remaining > 0:
        d -= timedelta(days=1)
        if d.weekday() < 5:
            remaining -= 1
    return d


@dataclass(frozen=True)
class UniverseRule:
    """Universum-Filter aus config.yaml (satellite.universe)."""

    type_ids: frozenset[int]          # 5 Aktie, 6 ETF
    exchange_ids: frozenset[int]      # 4 NASDAQ, 5 NYSE
    excluded_name_patterns: tuple[str, ...]  # breite Index-ETFs (Regelwerk §3)

    @classmethod
    def from_config(cls, sat_cfg: dict[str, Any]) -> "UniverseRule":
        u = sat_cfg["universe"]
        return cls(
            type_ids=frozenset(int(x) for x in u["type_ids"]),
            exchange_ids=frozenset(int(x) for x in u["exchange_ids"]),
            excluded_name_patterns=tuple(
                str(p).lower() for p in sat_cfg.get("excluded_broad_index_etf_names", [])
            ),
        )

    def allows(self, meta: dict[str, Any] | None) -> bool:
        if not meta:
            return False
        if int(meta.get("typeId", -1)) not in self.type_ids:
            return False
        if int(meta.get("exchangeId", -1)) not in self.exchange_ids:
            return False
        name = str(meta.get("name", "")).lower()
        return not any(p in name for p in self.excluded_name_patterns)


@dataclass(frozen=True)
class Entry:
    """Ein echter Neueinstieg eines Traders in ein Instrument."""

    trader: str
    instrument_id: int
    first_open: datetime
    weight_pct: float  # Summe investmentPct aller Tranchen


def aggregate_holdings(
    portfolios: dict[str, list[dict[str, Any]] | None],
) -> dict[tuple[str, int], tuple[datetime, float]]:
    """Je (Trader, Instrument): ältester openTimestamp und Gesamtgewicht der Long-Tranchen."""
    agg: dict[tuple[str, int], tuple[datetime, float]] = {}
    for trader, positions in portfolios.items():
        for p in positions or []:
            if not p.get("isBuy"):
                continue
            key = (trader, int(p["instrumentId"]))
            opened = parse_open_timestamp(p["openTimestamp"])
            pct = float(p.get("investmentPct") or 0.0)
            prev = agg.get(key)
            agg[key] = (opened if prev is None else min(prev[0], opened),
                        pct if prev is None else prev[1] + pct)
    return agg


def detect_entries(
    portfolios: dict[str, list[dict[str, Any]] | None],
    instruments: dict[str, dict[str, Any]],
    universe: UniverseRule,
    window_start: date,
    min_weight_pct: float,
) -> list[Entry]:
    """Neueinstiege im Fenster [window_start, ∞) nach Regelwerk §3 (Zählvariante A)."""
    out: list[Entry] = []
    for (trader, iid), (opened, pct) in aggregate_holdings(portfolios).items():
        if opened.date() < window_start or pct < min_weight_pct:
            continue
        if not universe.allows(instruments.get(str(iid))):
            continue
        out.append(Entry(trader, iid, opened, pct))
    return out


def consensus(entries: Iterable[Entry], min_traders_n: int) -> dict[int, list[Entry]]:
    """Instrumente mit >= N Neueinstiegen (das eigentliche Kaufsignal), sortiert nach N."""
    by_inst: dict[int, list[Entry]] = defaultdict(list)
    for e in entries:
        by_inst[e.instrument_id].append(e)
    hits = {iid: es for iid, es in by_inst.items() if len(es) >= min_traders_n}
    return dict(sorted(hits.items(), key=lambda kv: -len(kv[1])))
