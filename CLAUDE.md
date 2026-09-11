# Trading Bot — Arbeitsregeln für Claude

## Zuerst lesen

Quelle der Wahrheit für alle Handelsregeln: `../REGELWERK.md` (aktuell v0.8).
Dazu `../ENTSCHEIDUNGEN.md` (Entscheidungslog) und `../OFFENE-PUNKTE.md` (Stand).
Architektur: `../ARCHITEKTUR.md`. Diese Dateien liegen eine Ebene über dem Repo.

## Harte Leitplanken

- **Nur Paper/Demo.** Kein Echtgeld, keine Live-Keys, kein Real-Trading — Freigabe kann nur Michel ausdrücklich erteilen. Der eToro-Key hat bewusst keine Real-Trading-Berechtigung.
- **Regeländerungen nie im Code.** Handelsregeln ändern = neue Version von `../REGELWERK.md` + Eintrag in `../ENTSCHEIDUNGEN.md`, erst danach Code/Config nachziehen.
- **Keys niemals in Dateien** außer lokaler `.env` (in `.gitignore`) bzw. GitHub Secrets.
- **Ordergrößen nur nach Cash-Bestand des jeweiligen Topfs**, nie nach Buying Power. Kern-Topf 7.500 USD (Alpaca Paper), Satellit-Topf 2.500 USD (eToro Demo) — Topf-Buchhaltung führt der Bot.
- Kein Microtrading, keine Hebel, keine CFDs, keine Shorts.
- Parameter in `config/config.yaml`, nicht als Konstanten im Code. Jeder Lauf idempotent. Trade-Log mit Begründung je Order.

## Setup & Betrieb

- Python 3.12 (CI) / venv in `.venv`; Deps: httpx, python-dotenv, PyYAML, exchange_calendars (NYSE-Kalender fuers Signalfenster; zieht pandas mit).
- Smoke-Test: `python scripts/smoke_test.py` · Tageslauf: `python scripts/daily_run.py` · Offline-Neubewertung aus Tagesdateien: `python scripts/entry_signals.py [Datum]`, `python scripts/overlap_analysis.py [Datum]` · Tests: `python -m pytest -q tests`.
- Nächtlicher Cron (`.github/workflows/daily.yml`, Mo–Fr 21:30 UTC): Tests → Smoke-Test → Tageslauf (Top-50 Trader + Top-20 Smart Portfolios, Portfolios nur im Arbeitsspeicher) → `data/daily/<Datum>.json` + `data/reports/<Datum>-overlap.txt/-entries.txt` → Commit. Vor lokaler Arbeit `git pull` (Actions committet nachts).
- **Keine Rohdaten fremder Trader speichern** (Entscheidung 2026-09-11, eToro-Terms): Portfolios/Historien nur lesend verarbeiten, persistiert werden ausschließlich abgeleitete Daten (Kohortenliste, Kennzahlen, Neueinstiege je Trader/Instrument, Signale, Backtest-Ergebnisse). Das gilt auch für Backtests: Historie bei jedem Lauf frisch abrufen, nur Ergebnisse ablegen.
- eToro-API-Fallstricke (empirisch verifiziert): Header-Zuordnung siehe `.env.example`; Rankings unter `/api/v2/portfolios/rankings`, Zeilen im Feld `results`; `peakToValley` ist negativ; Portfolio-Endpunkt drosselt bei ~30 Requests/min (Client hat Backoff).

## Commit-Konventionen

Deutsche Commit-Messages, präzise; Doku-Änderungen (Regelwerk/Entscheidungen) gehören in den Projektordner eine Ebene höher, nicht ins Repo.
