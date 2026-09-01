#!/usr/bin/env python3
"""Smoke-Test: Sind Keys gesetzt und beide APIs erreichbar? (Paper/Demo, keine Orders!)

Lokal:  python scripts/smoke_test.py            (Keys aus .env)
CI:     laeuft im GitHub-Actions-Workflow       (Keys aus GitHub Secrets)
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tradingbot.alpaca_client import AlpacaClient
from tradingbot.config import load_config, require_env
from tradingbot.etoro_client import EtoroClient


def main() -> int:
    cfg = load_config()
    ok = True

    print("1/3 Env-Variablen ...")
    try:
        env = require_env(
            "ALPACA_API_KEY_ID", "ALPACA_API_SECRET_KEY", "ETORO_API_KEY", "ETORO_USER_KEY"
        )
        print("    OK — alle 4 vorhanden")
    except RuntimeError as exc:
        print(f"    FEHLER: {exc}")
        return 1

    print("2/3 Alpaca Paper API ...")
    alpaca = AlpacaClient(cfg["alpaca"]["base_url"], env["ALPACA_API_KEY_ID"], env["ALPACA_API_SECRET_KEY"])
    try:
        acct = alpaca.get_account()
        print(f"    OK — Konto {acct.get('account_number')}, Status {acct.get('status')}, "
              f"Cash {acct.get('cash')} {acct.get('currency')}")
    except Exception as exc:  # noqa: BLE001 — Smoke-Test soll alles melden
        print(f"    FEHLER: {exc}")
        ok = False
    finally:
        alpaca.close()

    print("3/3 eToro Public API ...")
    etoro = EtoroClient(cfg["etoro"]["base_url"], env["ETORO_API_KEY"], env["ETORO_USER_KEY"])
    try:
        resp = etoro.get(cfg["etoro"]["smoke_endpoint"])
        body = resp.text[:200].replace("\n", " ")
        print(f"    HTTP {resp.status_code} — {body}")
        if resp.status_code == 200:
            print("    OK")
        elif resp.status_code in (401, 403):
            print("    Hinweis: Keys pruefen; 403 kann auch 'KYC required' bedeuten.")
            ok = False
        elif resp.status_code == 404:
            print("    Hinweis: Endpunkt-Pfad in config.yaml (etoro.smoke_endpoint) an die "
                  "API-Referenz anpassen: api-portal.etoro.com")
            ok = False
        else:
            ok = False
    except Exception as exc:  # noqa: BLE001
        print(f"    FEHLER: {exc}")
        ok = False
    finally:
        etoro.close()

    print("Ergebnis:", "ALLES OK" if ok else "FEHLGESCHLAGEN")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
