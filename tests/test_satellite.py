"""Tests der Neueinstiegs-Logik (tradingbot.satellite) — ohne API, ohne Snapshots."""

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tradingbot.satellite import (Membership, UniverseRule, consensus,  # noqa: E402
                                  detect_entries, parse_open_timestamp, trading_days_back)

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


def test_membership_excludes_brought_in_positions():
    rk = lambda *names: [{"username": n, "type": "trader"} for n in names]  # noqa: E731
    m = Membership.from_rankings({date(2026, 9, 7): rk("a"), date(2026, 9, 8): rk("a"),
                                  date(2026, 9, 10): rk("a", "b")})
    # a: seit 07.09. dabei -> Eroeffnung ab 08.09. zaehlt, am 07.09. selbst noch nicht
    assert m.was_member("a", date(2026, 9, 8)) and not m.was_member("a", date(2026, 9, 7))
    # b: erstmals im Snapshot 10.09. -> Eroeffnungen bis 10.09. sind Bestand, ab 11.09. Signal
    assert not m.was_member("b", date(2026, 9, 10)) and m.was_member("b", date(2026, 9, 11))
    # Luecke (kein Snapshot 09.09.): letzter Snapshot davor gilt
    assert m.was_member("a", date(2026, 9, 9)) and not m.was_member("b", date(2026, 9, 9))
    pf = {"b": [pos(1, "2026-09-09T10:00:00Z"), pos(1, "2026-09-11T10:00:00Z")]}
    assert detect_entries(pf, INS, UNI, date(2026, 9, 8), 0.1, m) == []   # aeltester Kauf vorher
    pf = {"b": [pos(1, "2026-09-11T10:00:00Z")]}
    assert len(detect_entries(pf, INS, UNI, date(2026, 9, 9), 0.1, m)) == 1
