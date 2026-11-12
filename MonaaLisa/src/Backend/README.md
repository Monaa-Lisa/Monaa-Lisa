# Monaa-Lisa Backend

Dieses Repository enthält das Backend für unser Uni-Projekt. Wir haben uns für **NestJS** entschieden, weil es Struktur bringt, Typescript nutzt und sich super für größere Projekte eignet.

Da es für mich unübersichtlich ist über jede Funktion "Nico - DD-MM-YY" zu schreiben schreibe ich es hier einmal hin. Fragen zum Backend an mich (Nico). Ich werde trotzdem unsere Struktur einhalten, es aber *an den Anfang* jeder Datei schreiben damit man die Funktionen besser kommentieren kann für Code-Editoren

---

## Features

- REST-API für die wichtigsten Endpunkte
- DB-Schutz (Client sieht jetzt nicht mehr die SQL Logindaten und queries)
- Strukturierte Module und Services dank NestJS
- Verbindung zur Datenbank über TypeORM / Prisma (je nach Setup)
- Grundlegende Fehlerbehandlung und Validierung
- Optional: Authentifizierung via JWT

---

## Testing

Ich habe eine komplette Testing Suite eingebaut die einfach bei jedem Commit laufen lassen dann kann man eventuelle Probleme bei Updates schnell finden
