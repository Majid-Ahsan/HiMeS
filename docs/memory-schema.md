# HiMeS Memory-Schema

**Stand:** 2026-04-23
**Status:** Phase 1 konzeptionell abgeschlossen

Dieses Dokument definiert wie Memory in HiMeS strukturiert ist.
Es ist die Referenz für:
- Jarvis beim automatischen Erstellen von Memory-Dateien
- Claude Code beim Schreiben von Code der mit Memory arbeitet
- Menschen die nachvollziehen wollen warum Memory so aussieht

## Übersicht

HiMeS speichert Wissen als Markdown-Dateien in `/var/himes-data/` 
(außerhalb Git). Cognee indexiert diese Dateien in einen Knowledge 
Graph für schnelle, semantische Suche.

## Die 10 Grundregeln

### Regel 1 — Frontmatter darf nützlich lang sein

Jede .md-Datei beginnt mit YAML-Frontmatter zwischen zwei `---`-Zeilen.
Der Frontmatter darf länger sein wenn jedes Feld der Struktur und 
Durchsuchung dient. Bedingungen:
- Der Nutzer schreibt Frontmatter **nie selbst** — Jarvis füllt alles automatisch
- Keine redundanten Beziehungs-Listen (Regel 6 regelt Beziehungen)
- Mindestanforderung: `type` + ein Schlüsselfeld (bei Entities `name`, 
  bei Daily-Logs `date`)

### Regel 2 — Datum immer im ISO-Format

Im Frontmatter: `date: 2026-04-23` (Jahr-Monat-Tag). Nie `23.04.2026`.

Im Gesprochenen/Geschriebenen: Nutzer spricht deutsch frei. Jarvis 
konvertiert. "Letzten Donnerstag", "4. März", "25.3.2026" — alles okay.
Jahres-Annahmen: nächstliegendes plausibles Jahr, nicht 1938.

### Regel 3 — Entity-Erkennung automatisch, keine Wikilinks nötig

Entity-Dateien heißen nach realem Namen: `taha.md`, `reza.md`, 
`fatima.md`. Der Nutzer schreibt natürliche Prosa im Voice-Memo 
("Taha hatte Fieber") und muss keine `[[Klammern]]` setzen.

Cognee und Jarvis erkennen Namen beim Ingesten automatisch und 
verknüpfen sie mit Entity-Dateien.

### Regel 4 — Tags von Jarvis automatisch gesetzt

Der Nutzer setzt nie selbst Tags. Jarvis extrahiert beim Ingesten 
sinnvolle Tags aus dem Kontext. Bei Unsicherheit: Jarvis fragt nach 
oder nimmt breite Defaults.

Gute Tags: breite wiederkehrende Kategorien (`familie`, `arbeit`, 
`medizin`, `projekt-jarvis`).
Schlechte Tags: einmalige Ereignisse (`taha-fieber-23-april`).

### Regel 5 — Sprache: Keys englisch, Inhalt frei

Frontmatter-Keys bleiben englisch: `date`, `type`, `name`, `tags`, 
`rel_to_anchor`. Python-Code erwartet das.

Werte und Text-Body: komplett frei — deutsch, persisch, gemischt. 
Jarvis versteht alles.

### Regel 6 — Anchor-basiertes Beziehungs-System

Der Anchor ist der primäre Nutzer (Majid). Alle Personen-Beziehungen 
werden **relativ zum Anchor** im Frontmatter definiert:

```yaml
rel_to_anchor: uncle
rel_via: mother
```

Statt redundanter Beziehungs-Listen in jeder Datei: der Graph leitet 
andere Beziehungen automatisch ab. Taha ist Anchor's Sohn + Ehefrau 
ist Anchor's Spouse → Ehefrau ist Tahas Mutter (ohne explizit zu 
schreiben).

**Multi-User:** Anchor wechselt temporär zur fragenden Person. Taha 
fragt "wer ist meine Mutter" → Anchor=Taha → Antwort: Ehefrau von Majid.

### Regel 7 — Zwei-Schichten in jeder Entity-Datei

Jede Entity-Datei hat zwei Schichten:

- **Frontmatter** = Navigations-System für den Graph (Regel 6)
- **Text-Body** = Gedächtnis-Inhalt (Persönliches, Beruf, Gesundheit, 
  Historie)

Frontmatter minimal und strukturiert. Text wächst organisch mit der Zeit.

### Regel 8 — Provisorische Variablen für Graph-Traversal

Beziehungen werden verkettet durchlaufen:
- `anchor.son.mother` = Tahas Mutter = Ehefrau
- `anchor.spouse.mother` = Schwiegermutter
- `anchor.uncle.son` = Cousin

Dies ist die interne Query-Sprache. Der Nutzer fragt natürlich 
("Wer ist Tahas Mutter?"), Jarvis übersetzt intern.

### Regel 9 — Schema speichert alles, Antwort selektiert

Entity-Dateien enthalten maximal viel Information.
Jarvis antwortet aber nur auf die konkrete Frage.

- "Hat Reza angerufen?" → "Ja, gestern um 18 Uhr."
- "Was weißt du über Reza?" → Voller Kontext wird geliefert.

Keine proaktiven Lebensläufe. Kein unangefragtes Erzählen.

### Regel 10 — Memory hat 7 Typen, nicht nur Personen

Das Memory-System speichert verschiedene Kategorien:

1. **Entity: Person** — Familie, Freunde, Kollegen, Patienten
2. **Entity: Ort** — Städte, Krankenhäuser, Wohnorte
3. **Entity: Medikament** — Wirkstoffe, Handelsnamen, Interaktionen
4. **Entity: Konzept/Projekt** — Themen, Projekte, Tools
5. **Daily-Log** — Alltag, Voice-Memos
6. **Meeting/Termin** — Zeitgebundene Ereignisse
7. **Research** — Medizinisches Fachwissen, Leitlinien
8. **Conversation** — Chat-Sessions mit Jarvis (auto-generiert)

Jeder Typ hat ähnliches Grund-Schema (Frontmatter + Text), aber 
typ-spezifische Detail-Felder. Konkrete Templates kommen in 
folgenden Sessions.

## Memory-Typ 1: Daily-Log

**Definition:** Ein Daily-Log ist ein Voice-Memo oder Text-Eintrag 
eines Users zu einem bestimmten Tag. Jarvis verarbeitet es automatisch 
und erstellt die .md-Datei mit Frontmatter und strukturiertem Inhalt.

### Dateipfad und Benennung

`/var/himes-data/memory/daily-logs/YYYY-MM-DD_user.md`

Beispiele:
- `2026-04-23_majid.md`
- `2026-04-23_taha.md`
- `2026-04-24_majid.md`

Eine Datei pro Tag pro User. Mehrere Memos desselben Users am selben 
Tag werden in dieselbe Datei angehängt (siehe Text-Body-Struktur unten).

### Frontmatter-Felder

**Pflicht:**
- `type: daily-log`
- `date: YYYY-MM-DD`
- `user: <user_id>` — wer dieses Memo gesprochen hat

**Optional (von Jarvis automatisch gefüllt):**
- `entries: <number>` — Anzahl der Memos an diesem Tag (nur wenn >1)
- `tags: [kategorie1, kategorie2, ...]` — breite Kategorien, automatisch 
  extrahiert
- `entities: [name1, name2, ...]` — erkannte Personen, Orte, Konzepte
- `detected_events: [...]` — erkannte triggernde Ereignisse (Details 
  siehe unten)
- `actions_created: [...]` — Referenzen auf automatisch erstellte 
  Tickets im Format `YYYY-MM-DD_NNN_TYPE-slug`

### Struktur von detected_events

Flexibles Schema pro Event-Typ. Jedes Event hat mindestens das Feld 
`type`. Weitere Felder variieren je nach Event-Art. Jarvis entscheidet 
welche Detail-Felder sinnvoll sind, ohne unnötige Info hinzuzufügen.

Beispiele:

```yaml
detected_events:
  - type: calendar_event
    date: 2026-04-26
    title: "Mathe-Klassenarbeit Bruchrechnung"
    category: schule
  
  - type: shopping_need
    item: hefte
    urgency: "morgen"
  
  - type: health_observation
    person: taha
    observation: fieber
    since: 2026-04-21
  
  - type: medication_mentioned
    person: reza
    medication: metformin
    context: "seit 2019 wegen Diabetes"
  
  - type: contact
    person: klaus
    action: telefoniert
  
  - type: sozialer_kontakt
    person: klaus
    proposed_date: 2026-04-24
```

### Extraktion-Regeln für Jarvis

**Jarvis extrahiert großzügig** wenn ein Event-Kandidat erkannt wird. 
Grund: Das Ticket-System ist das Sicherheitsnetz — User bestätigt 
oder lehnt ab.

**Extrahieren:**
- Ereignisse mit zukünftigem Zeitpunkt (Termine, Klassenarbeiten, 
  Geburtstage)
- Actions die Tickets triggern können (Einkauf, Erinnerung, Medikament, 
  Kalender-Event)
- Gesundheits-Infos (Symptome, Medikamente, Arztbesuche)
- Soziale Kontakte (Anrufe, Besuche, geplante Treffen)

**Nicht extrahieren:**
- Reine Gefühls-Beobachtungen ohne Action-Bezug ("bin müde")
- Trivialitäten ("Kaffee getrunken", "Regen heute")
- Rein sensorische Details ohne Kontext

### Text-Body-Struktur

**Bei einem einzelnen Memo am Tag:**

```markdown
Der Voice-Memo-Text als Fließtext, ohne Header.
```

**Bei mehreren Memos am Tag:**

```markdown
## 08:01

Erstes Memo als Text...

## 15:30

Zweites Memo...

## 22:45

Drittes Memo...
```

Uhrzeit-Header werden automatisch aus dem Telegram-Zeitstempel 
abgeleitet. Der User muss keine Uhrzeit diktieren.

### Dual-Layer-Prinzip (Memory + Action)

Jedes extrahierte Event hat zwei Schichten:

1. **Memory-Schicht:** Das Event wird im `detected_events:`-Array 
   des Daily-Log-Frontmatters gespeichert. Bleibt durchsuchbar für immer.

2. **Action-Schicht:** Für actionable Events erstellt Jarvis automatisch 
   ein Ticket in `/var/himes-data/tickets/inbox/` das den User nach 
   Bestätigung fragt. Das Ticket wird im `actions_created:`-Feld 
   des Daily-Logs referenziert.

Dieser Dual-Layer ist robust: Wenn das Ticket-System ausfällt bleibt 
das Wissen im Daily-Log. Wenn der User später fragt "hab ich X 
gemacht?" findet Jarvis beide Schichten.

### Multi-User-Kontext

Der `user:`-Wert bestimmt:
- Aus wessen Perspektive Actions zugeordnet werden
- Welcher Anchor für Beziehungs-Queries aktiv ist
- Welche Kalender-Integration angesprochen wird

Beim Start des Systems ist nur Majid als User konfiguriert. 
Multi-User-Aktivierung (Taha, Hossein, Ehefrau mit eigenen 
Telegram-Accounts) kommt in späterer Phase.

### Vollständiges Beispiel

Datei: `/var/himes-data/memory/daily-logs/2026-04-23_taha.md`

```markdown
---
type: daily-log
date: 2026-04-23
user: taha
tags: [schule, einkauf, freunde]
entities: [taha, klaus]
detected_events:
  - type: calendar_event
    date: 2026-04-26
    title: "Mathe-Klassenarbeit Bruchrechnung"
    category: schule
  - type: shopping_need
    item: hefte
  - type: sozialer_kontakt
    person: klaus
    proposed_date: 2026-04-24
actions_created:
  - 2026-04-23_001_ACTION-kalender-klassenarbeit
  - 2026-04-23_002_ACTION-erinnerung-hefte
---

Ich hab Mathe-Klassenarbeit am Freitag über Bruchrechnung. 
Muss noch Hefte kaufen. Klaus hat angerufen, will morgen mit 
mir was machen.
```

## Offene Punkte für nächste Sessions

- [ ] Beziehungs-Vokabular: Welche Werte sind in `rel_to_anchor` erlaubt?
- [ ] Ableitungs-Regeln: Welche automatischen Schlüsse sind valide?
- [ ] Initial-Daten-Strategie: Setup-Skript vs passives Lernen
- [ ] Konkrete Templates pro Memory-Typ (Daily-Log ✓, Person ⬜, Ort ⬜, Medikament ⬜, Konzept ⬜, Meeting ⬜, Research ⬜, Conversation ⬜)
- [ ] Erste Beispiel-Dateien mit echten Daten
- [ ] Jarvis-Prompt-Regeln die Regel 9 umsetzen

## Änderungs-Historie

- 2026-04-23: Initial. Die 10 Regeln festgelegt in Session mit Claude.
- 2026-04-23: Daily-Log-Schema als erster konkreter Memory-Typ definiert. Dual-Layer-Prinzip (Memory-Frontmatter + Action-Tickets) etabliert.
