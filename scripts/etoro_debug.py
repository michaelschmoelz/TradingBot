#!/usr/bin/env python3
"""Diagnose fuer das eToro-401: testet Endpunkte x Header-Kombinationen.

Aufruf: python scripts/etoro_debug.py  (liest .env)
"""

from __future__ import annotations

import os
import sys
import uuid
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[1] / ".env")

API = os.environ.get("ETORO_API_KEY", "")
USER = os.environ.get("ETORO_USER_KEY", "")
if not API or not USER:
    sys.exit("ETORO_API_KEY / ETORO_USER_KEY fehlen in .env")

BASE = "https://public-api.etoro.com"
ENDPOINTS = [
    "/api/v1/market-data/instruments",
    "/api/v1/rankings",
]
COMBOS = {
    "wie konfiguriert (api/user)": {"x-api-key": API, "x-user-key": USER},
    "vertauscht (user/api)":       {"x-api-key": USER, "x-user-key": API},
    "nur x-api-key":               {"x-api-key": API},
}

with httpx.Client(base_url=BASE, timeout=30) as c:
    for ep in ENDPOINTS:
        print(f"\n== {ep}")
        for name, hdrs in COMBOS.items():
            h = dict(hdrs)
            h["x-request-id"] = str(uuid.uuid4())
            h["Accept"] = "application/json"
            try:
                r = c.get(ep, headers=h)
                body = r.text[:120].replace("\n", " ")
                print(f"   {r.status_code}  {name}  ->  {body}")
            except Exception as exc:
                print(f"   ERR  {name}  ->  {exc}")
