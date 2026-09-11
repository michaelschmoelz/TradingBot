"""Tageslauf-Bausteine: Kohorte waehlen, Portfolios abrufen, abgeleitete Daten bilden.

Entscheidung 2026-09-11 (ENTSCHEIDUNGEN.md): Rohdaten (Portfolios fremder Trader) werden NICHT
gespeichert — nur lesend verarbeitet. Persistiert wird ausschliesslich unsere Ableitung:
Kohortenliste, Kennzahlen, Neueinstiege je (Trader, Instrument) im Lookback, Signale.
Dateiformat: data/daily/YYYY-MM-DD.json (siehe build_daily_record).
"""

from __future__ import annotations

import time
from collections import Counter
from datetime import date, datetime, timezone
from typing import Any, Callable

from .satellite import aggregate_holdings

RANK_FIELDS = ["username", "type", "riskScore", "copiers", "peakToValley", "gain"]
POS_FIELDS = ["instrumentId", "isBuy", "leverage", "investmentPct", "openTimestamp"]


def select_cohort(rows: list[dict[str, Any]], sat_cfg: dict[str, Any]) -> list[dict[str, Any]]:
    """Qualitaetsfilter (Regelwerk §3) + Top-K Trader + Vergleichskohorte Smart Portfolios."""
    q = sat_cfg["quality_filter"]

    def ok(r: dict[str, Any]) -> bool:
        dd = r.get("peakToValley")  # kommt negativ (-23.28 = 23,28 % Drawdown)
        return dd is not None and abs(dd) <= q["max_drawdown_pct"]

    filtered = [r for r in rows if ok(r)]
    traders = [r for r in filtered if r.get("type") == "trader"][: int(sat_cfg["top_k"])]
    sp_k = int(sat_cfg.get("smart_portfolio_comparison_k", 0))
    smarts = [r for r in filtered if r.get("type") == "smart-portfolio"][:sp_k]
    return [{k: r.get(k) for k in RANK_FIELDS} for r in traders + smarts]


def fetch_portfolios(get: Callable[[str], Any], usernames: list[str], pause_s: float = 2.2,
                     log: Callable[[str], None] = print) -> dict[str, list[dict[str, Any]] | None]:
    """Live-Portfolios nur im Arbeitsspeicher; `get(username)` liefert die API-Antwort.
    Fehlgeschlagene Trader -> None (ein Einzelner darf fehlen)."""
    out: dict[str, list[dict[str, Any]] | None] = {}
    for i, u in enumerate(usernames, 1):
        try:
            pf = get(u)
            positions = pf.get("positions") or []
            out[u] = [{k: p.get(k) for k in POS_FIELDS} for p in positions]
            log(f"  [{i}/{len(usernames)}] {u}: {len(positions)} Positionen")
        except Exception as exc:  # noqa: BLE001 — einzelner Trader darf fehlen
            log(f"  [{i}/{len(usernames)}] {u}: FEHLER {exc}")
            out[u] = None
        time.sleep(pause_s)
    return out


def instrument_map(inst_response: Any, ids: set[int]) -> dict[str, dict[str, Any]]:
    """Anzeigedaten (Name, Typ, Boerse) nur fuer die vorkommenden Instrument-IDs."""
    items = inst_response.get("instrumentDisplayDatas",
                              inst_response if isinstance(inst_response, list) else [])
    return {str(it["instrumentID"]): {
        "name": it.get("instrumentDisplayName"),
        "typeId": it.get("instrumentTypeID"),
        "exchangeId": it.get("exchangeID"),
    } for it in items if it.get("instrumentID") in ids}


def cohort_stats(portfolios: dict[str, list[dict[str, Any]] | None]) -> dict[str, Any]:
    """Aggregierte Kennzahlen einer Kohorte (kein Abbild einzelner Portfolios)."""
    loaded = {u: ps for u, ps in portfolios.items() if ps is not None}
    holders: dict[int, set[str]] = {}
    lev: Counter = Counter()
    for u, ps in loaded.items():
        for p in ps:
            if not p.get("isBuy"):
                continue
            lev[p.get("leverage")] += 1
            holders.setdefault(int(p["instrumentId"]), set()).add(u)
    return {
        "portfolios": len(loaded),
        "failed": sum(1 for v in portfolios.values() if v is None),
        "positions_long": sum(lev.values()),
        "instruments_long": len(holders),
        "leverage": {str(k): v for k, v in sorted(lev.items(), key=lambda x: (x[0] is None, x[0]))},
        "holders_by_instrument": {str(i): len(us) for i, us in holders.items()},
    }


def derive_entries(portfolios: dict[str, list[dict[str, Any]] | None],
                   instruments: dict[str, dict[str, Any]],
                   lookback_start: date) -> list[dict[str, Any]]:
    """Alle (Trader, Instrument)-Neueinstiege (Long, aeltester openTimestamp) ab lookback_start.
    Bewusst OHNE Universum-/Gewichtsfilter, damit Regelaenderungen rueckwirkend auswertbar
    bleiben; die Filter wendet der Detektor an."""
    out = []
    for (trader, iid), (opened, pct) in aggregate_holdings(portfolios).items():
        if opened.date() < lookback_start:
            continue
        meta = instruments.get(str(iid), {})
        out.append({
            "trader": trader, "instrumentId": iid, "name": meta.get("name"),
            "typeId": meta.get("typeId"), "exchangeId": meta.get("exchangeId"),
            "firstOpen": opened.isoformat(), "weightPct": round(pct, 4),
        })
    return sorted(out, key=lambda e: (e["firstOpen"], e["trader"], e["instrumentId"]))


def build_daily_record(day: date, cohort: list[dict[str, Any]],
                       trader_stats: dict[str, Any], smart_stats: dict[str, Any] | None,
                       entries: list[dict[str, Any]], lookback_start: date,
                       signals: list[dict[str, Any]], params: dict[str, Any],
                       instruments: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Tagesdatei. `instruments` = Anzeigedaten (Name/Typ/Boerse) der vorkommenden IDs —
    Marktstammdaten, kein Portfolio-Abbild."""
    return {
        "date": day.isoformat(),
        "run_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "params": params,
        "cohort": cohort,
        "stats": {"trader": trader_stats, "smart_portfolio": smart_stats},
        "instruments": instruments,
        "entries_lookback_start": lookback_start.isoformat(),
        "entries": entries,
        "signals": signals,
    }
