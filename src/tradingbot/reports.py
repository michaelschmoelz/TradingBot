"""Reports aus abgeleiteten Tagesdaten (data/daily/*.json) — Text fuer Log/Step-Summary."""

from __future__ import annotations

import json
from collections import Counter
from datetime import date
from pathlib import Path
from typing import Any

from .satellite import Entry, Membership, UniverseRule, consensus, filter_entries, trading_days_back

DAILY_DIR = "data/daily"


def load_daily(repo: Path, day: str | None = None) -> dict[str, Any]:
    """Tagesdatei laden (Default: neueste)."""
    d = repo / DAILY_DIR
    if day:
        return json.loads((d / f"{day}.json").read_text(encoding="utf-8"))
    files = sorted(d.glob("????-??-??.json")) if d.exists() else []
    if not files:
        raise SystemExit("Keine Tagesdatei gefunden — erst scripts/daily_run.py laufen lassen.")
    return json.loads(files[-1].read_text(encoding="utf-8"))


def membership_until(repo: Path, until: date) -> Membership:
    """Kohorten-Mitgliedschaft aus den Kohortenlisten aller Tagesdateien bis `until`."""
    hist = {}
    for f in sorted((repo / DAILY_DIR).glob("????-??-??.json")):
        d = date.fromisoformat(f.stem)
        if d <= until:
            hist[d] = json.loads(f.read_text(encoding="utf-8"))["cohort"]
    return Membership.from_rankings(hist)


def overlap_report(rec: dict[str, Any], names: dict[str, str], n_threshold: int = 5,
                   top: int = 15) -> str:
    """Bestands-Ueberlapp je Kohorte aus den aggregierten Halterzahlen."""
    lines = [f"Tagesdaten {rec['date']} — Signal-Kohorte {rec['stats']['trader']['portfolios']} "
             f"Portfolios geladen, {rec['stats']['trader']['failed']} fehlgeschlagen"]
    for title, key, top_n in [("SIGNAL-KOHORTE (echte Trader)", "trader", top),
                              ("VERGLEICH (Smart Portfolios — speist NICHT das Signal)",
                               "smart_portfolio", 10)]:
        st = rec["stats"].get(key)
        if not st:
            continue
        n = st["portfolios"]
        counts = Counter({i: c for i, c in st["holders_by_instrument"].items()})
        lines.append(f"\n### {title}: {n} Portfolios, {st['positions_long']} Positionen, "
                     f"{st['instruments_long']} Instrumente (long)")
        lines.append(f"{'Instrument':38} {'Halter':>6} {'Anteil':>7}")
        for iid, c in counts.most_common(top_n):
            lines.append(f"{(names.get(iid) or f'ID {iid}')[:38]:38} {c:>6} {c / n:>6.0%}")
        dist = Counter(counts.values())
        lines.append("Verteilung: " + ", ".join(f"{k}x:{dist[k]}" for k in sorted(dist, reverse=True)))
        lines.append(f"Instrumente mit >={n_threshold} Haltern: "
                     f"{sum(1 for c in counts.values() if c >= n_threshold)} | Hebel: "
                     + "{" + ", ".join(f"{k}: {v}" for k, v in st["leverage"].items()) + "}")
    lines.append("\nHinweis: Bestands-Ueberlapp, KEIN Einstiegssignal — das Signal zaehlt NEU")
    lines.append("eroeffnete Positionen binnen 3 Handelstagen (Regelwerk §3).")
    return "\n".join(lines)


def evaluate_entries(rec: dict[str, Any], sat_cfg: dict[str, Any], membership: Membership
                     ) -> tuple[list[Entry], dict[int, list[Entry]], int, date]:
    """Detektor auf einer Tagesdatei: (gefilterte Einstiege, Signale, als Bestand
    ausgeschlossene, Fensterbeginn)."""
    c = sat_cfg["consensus"]
    snap_date = date.fromisoformat(rec["date"])
    start = trading_days_back(snap_date, int(c["window_trading_days"]))
    universe = UniverseRule.from_config(sat_cfg)
    min_w = float(c["min_weight_pct"])
    entries = filter_entries(rec["entries"], universe, start, min_w, membership)
    unfiltered = filter_entries(rec["entries"], universe, start, min_w)
    return entries, consensus(entries, int(c["min_traders_n"])), len(unfiltered) - len(entries), start


def entries_report(rec: dict[str, Any], sat_cfg: dict[str, Any], entries: list[Entry],
                   hits: dict[int, list[Entry]], brought_in: int, start: date) -> str:
    c = sat_cfg["consensus"]
    names = {str(e["instrumentId"]): e.get("name") for e in rec["entries"]}
    name = lambda iid: names.get(str(iid)) or f"ID {iid}"  # noqa: E731
    per_inst = Counter(e.instrument_id for e in entries)
    cohort_n = sum(1 for r in rec["cohort"] if r.get("type") == "trader")
    fmt = lambda es: ", ".join(  # noqa: E731
        f"{e.trader} ({e.first_open:%d.%m.} {e.weight_pct:.1f}%)" for e in es)
    lines = [f"Neueinstiege {rec['date']} — Fenster {start} bis {rec['date']} "
             f"({c['window_trading_days']} Handelstage), Kohorte {cohort_n} Trader, "
             f"Schwelle N>={c['min_traders_n']}, Mindestgewicht {c['min_weight_pct']} %",
             f"Echte Neueinstiege im Universum: {len(entries)} in {len(per_inst)} Instrumenten "
             f"von {len({e.trader for e in entries})} Tradern "
             f"(davon ausgeschlossen als Bestand vor Kohorteneintritt: {brought_in})"]
    if hits:
        lines.append(f"\n*** KAUFSIGNAL ({len(hits)}) ***")
        for iid, es in hits.items():
            lines.append(f"{name(iid)[:38]:38} N={len(es)}  {fmt(es)}")
    else:
        top = per_inst.most_common(1)[0][1] if per_inst else 0
        lines.append(f"\nKein Kaufsignal (Maximum N={top}).")
    lines.append(f"\n{'Instrument':38} {'N':>3}  Trader (Einstieg, Gewicht)")
    for iid, n in per_inst.most_common(15):
        es = sorted((e for e in entries if e.instrument_id == iid), key=lambda e: e.first_open)
        lines.append(f"{name(iid)[:38]:38} {n:>3}  {fmt(es)}")
    return "\n".join(lines)


def signals_json(hits: dict[int, list[Entry]], names: dict[str, str]) -> list[dict[str, Any]]:
    return [{"instrumentId": iid, "name": names.get(str(iid)), "n": len(es),
             "traders": [e.trader for e in es]} for iid, es in hits.items()]
