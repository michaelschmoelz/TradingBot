"""Trade-Log: append-only, mit Begründung je Order (Projektregel; Basis für Anlage KAP).

Felder je Eintrag (Entwurf): Zeitstempel (UTC), Teilstrategie (core|satellite), Venue,
Symbol, Seite, Betrag/Stückzahl, Orderart, Status, Begründung (Signal, beteiligte Trader),
Konsens-Stand, Stop-Niveau, Lauf-ID (Idempotenz).

TODO: SQLite-Schema + Writer; jeder Lauf idempotent (Lauf-ID = Handelstag + Modul).
"""
