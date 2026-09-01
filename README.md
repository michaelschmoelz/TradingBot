# trading-bot

Claude-gestützter Trading-Bot in der **Paper-Phase**. Kern (Faber 10-Monats-SMA, Alpaca Paper)
+ Satellit (Konsens-Signale der eToro-Top-Trader, Ausführung im eToro-**Demo**-Konto).

**Quelle der Wahrheit für alle Handelsregeln:** `REGELWERK.md` im übergeordneten Projektordner
(dazu `ENTSCHEIDUNGEN.md`, `OFFENE-PUNKTE.md`, `ARCHITEKTUR.md`). `config/config.yaml` spiegelt
die Parameter maschinenlesbar — Regeländerungen laufen immer über eine neue REGELWERK-Version,
nie nur über die Config.

## Leitplanken

- Nur Paper/Demo — kein Echtgeld, keine Live-Keys ohne ausdrückliche Freigabe von Michel
- Keine Hebel, keine Shorts, keine CFDs; Ordergrößen nur nach Cash-Bestand des Topfs, nie Buying Power
- Keys niemals im Repo — nur GitHub Secrets bzw. lokale `.env` (in `.gitignore`)
- Jeder Lauf idempotent; Trade-Log mit Begründung je Order

## Setup (lokal, Python 3.12)

```bash
python3.12 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env   # Keys eintragen (Passwortmanager), Datei bleibt lokal
```

## Smoke-Test (erster API-Check)

```bash
python scripts/smoke_test.py
```

Prüft: Env-Variablen vorhanden → Alpaca-Paper-Konto erreichbar → eToro-API erreichbar (Demo).
Hinweise bei 401/403 (Keys/KYC) und 404 (Endpunkt-Pfad ggf. an api-portal.etoro.com anpassen).

## Struktur

```
config/config.yaml        Parameter (gespiegelt aus REGELWERK v0.5)
src/tradingbot/           Module: Config, eToro-/Alpaca-Client, Kern, Satellit, Trade-Log
scripts/smoke_test.py     Verbindungstest beider APIs
.github/workflows/        GitHub-Actions-Gerüst (manuell auslösbar; Cron erst später)
data/                     State/Snapshots (SQLite/Parquet) — Backtest-Rohmaterial
```
