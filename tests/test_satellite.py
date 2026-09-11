"""Tests der Neueinstiegs-Logik (tradingbot.satellite) — ohne API, ohne Snapshots."""

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tradingbot.satellite import (UniverseRule, consensus, detect_entries,  # noqa: E402
                                  parse_open_timestamp, trading_days_back)

UNI = UniverseRule(type_ids=frozenset({5, 6}), exchange_ids=frozenset({4, 5}),
                   excluded_name_patterns=("s&p 500", "qqq"))
INS = {
    "1": {"name": "Broadcom", "typeId": 5, "exchangeId": 4},
    "2": {"name": "Invesco QQQ", "typeId": 6, "exchangeId": 4},
    "3": {"name": "Bitcoin", "typeId": 10, "exchangeId": 10},
    "4": {"name": "SAP", "typeId": 5, "exchangeId": 7},
}


def pos(iid, ts, pct=1.0, buy=True):
    return {"positionId": 0, "instrumentId": iid, "isBuy": buy, "leverage": 1,
            "investmentPct": pct, "openTimestamp": ts}


def test_parse_variable_fraction_digits():
    assert parse_open_timestamp("2021-10-01T18:31:05.3").second == 5
    assert parse_open_timestamp("2020-08-14T09:55:16.443Z").hour == 9


def test_window_skips_weekend():
    # Do 10.09.2026: 3 Handelstage = 08.-10.09.
    assert trading_days_back(date(2026, 9, 10), 3) == date(2026, 9, 8)
    # Mo 14.09.: 3 Handelstage = Do 10., Fr 11., Mo 14.
    assert trading_days_back(date(2026, 9, 14), 3) == date(2026, 9, 10)
    # Snapshot am Samstag -> letzter Werktag zaehlt als Fensterende
    assert trading_days_back(date(2026, 9, 12), 1) == date(2026, 9, 11)


def test_tranches_count_once_and_oldest_wins():
    pf = {"a": [pos(1, "2026-09-09T10:00:00Z", 0.5), pos(1, "2026-09-10T10:00:00Z", 0.5),
                pos(1, "2025-01-01T10:00:00Z", 0.5)]}   # alte Tranche -> Nachkauf, kein Einstieg
    assert detect_entries(pf, INS, UNI, date(2026, 9, 8), 0.1) == []
    pf = {"a": [pos(1, "2026-09-09T10:00:00Z", 0.05), pos(1, "2026-09-10T10:00:00Z", 0.06)]}
    es = detect_entries(pf, INS, UNI, date(2026, 9, 8), 0.1)
    assert len(es) == 1 and abs(es[0].weight_pct - 0.11) < 1e-9   # Summe der Tranchen


def test_universe_and_filters():
    pf = {"a": [pos(2, "2026-09-09T10:00:00Z"),          # breiter Index-ETF raus
                pos(3, "2026-09-09T10:00:00Z"),          # Krypto raus
                pos(4, "2026-09-09T10:00:00Z"),          # Nicht-US-Boerse raus
                pos(1, "2026-09-09T10:00:00Z", buy=False),  # Short raus
                pos(1, "2026-09-09T10:00:00Z", 0.01)]}   # Staub raus
    assert detect_entries(pf, INS, UNI, date(2026, 9, 8), 0.1) == []


def test_consensus_threshold():
    pf = {t: [pos(1, "2026-09-09T10:00:00Z")] for t in "abcde"}
    pf["f"] = [pos(1, "2026-09-01T10:00:00Z")]  # vor dem Fenster
    es = detect_entries(pf, INS, UNI, date(2026, 9, 8), 0.1)
    assert len(es) == 5
    assert list(consensus(es, 5)) == [1]
    assert consensus(es, 6) == {}
