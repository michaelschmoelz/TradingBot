"""Satellit: Konsens-Signale der eToro-Top-Trader (REGELWERK §3–§6).

Einstieg: >= N der Top-K eröffnen NEU dieselbe Aktie binnen 3 Handelstagen.
Risiko: 1 % je Trade, ATR-Skalierung, max 10 %/Position, max 10 Positionen, 30 %/Sektor.
Exits (Priorität): Signal-Exit, 2.5x-ATR-Stop, 3x-ATR-Trailing, 30-Tage-Zeit-Stop.
Circuit Breaker: -12 % vom Höchststand => alles schließen, Review.
Stops führt der Bot selbst (kein Verlass auf Venue-Orderarten).

TODO: Konsens-Engine nach Überschneidungsanalyse und Backtest (OFFENE-PUNKTE).
"""
