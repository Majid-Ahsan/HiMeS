# HiMeS Memory-Schema

**Stand:** 2026-04-25
**Status:** Daily-Log MVP-ready. Entity-Person, Insights und Conversation sind Future Work (siehe Anhang).

Dieses Dokument definiert wie Memory in HiMeS strukturiert ist.
Es ist die Referenz für:
- Jarvis beim automatischen Erstellen von Memory-Dateien
- Claude Code beim Schreiben von Code der mit Memory arbeitet
- Menschen die nachvollziehen wollen warum Memory so aussieht

## MVP-Scope

Das MVP führt einen einzigen Pfad zu Ende:

```
Voice-Memo → Whisper-Transkript → Daily-Log-MD-Datei → Cognee-Index → Jarvis-Antwort via Cognee-MCP
```

**Leitprinzip:** Cognee macht die semantische Arbeit. Das Schema gibt
nur Struktur, keine Tiefe. Alles was nicht für diesen einen Pfad nötig
ist, steht im Future-Work-Anhang.

In Scope:
- Memory-Typ 1: Daily-Log

Future Work (im Anhang dokumentiert, im MVP nicht erstellt):
- Memory-Typ 2: Entity-Person
- Memory-Typ 2a: Insights
- Memory-Typ 4: Conversation
- detected_events / actions_created
- Beziehungs-Vokabular (rel_to_anchor, rel_via)
- 6-Sektionen-Body für Entity-Files

## Verbindung zur Masterfile

- **ADR-034** (Anchor-basiertes Memory-Schema): Beschreibt das
  rel_to_anchor-Prinzip. Im MVP nicht aktiv (Entity-Files entstehen erst
  in Phase nach MVP).
- **ADR-035** (Memory-Typen reduziert auf 4): Begründet warum HiMeS nur
  Daily-Log, Entity-Person, Insights und Conversation speichert. Termine
  bleiben in CalDAV, strukturierte Daten in Notion, Tasks in Things3.
- **ADR-036** (Initial-Daten passiv): Begründet warum Entity-Files
  organisch aus Daily-Logs entstehen, nicht via Setup-Skript. Im MVP
  konsequent: Cognee extrahiert Personen-Wissen direkt aus Daily-Logs,
  keine Entity-Files werden geschrieben.
- **Phase 2.1 Ausführung Schritte 5-8**: Voice-Memo-Pipeline, Cognee-
  Anbindung, MCP-Registrierung, End-to-End-Test. Dieses Schema-Dokument
  ist die Spezifikation für Schritt 5-6.

## Übersicht

HiMeS speichert Wissen als Markdown-Dateien in `/var/himes-data/`
(außerhalb Git). Cognee indexiert diese Dateien in einen Knowledge
Graph für schnelle, semantische Suche.

## Die 10 Grundregeln

Die Regeln 1-9 beschreiben Prinzipien des Systems. Einige beziehen sich
auf Memory-Typen, die im MVP noch nicht aktiv sind (z.B. Entity-Files);
sie bleiben dokumentiert, damit das Schema bei Aktivierung dieser Typen
konsistent ist.

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

Entity-Dateien heißen nach dem Format vorname-nachname.md (siehe
Memory-Typ 2 im Anhang für Details): `taha-ahsan.md`, `reza-ahmadi.md`,
`fatima-ahmadi.md`. Der Nutzer schreibt natürliche Prosa im Voice-Memo
("Taha hatte Fieber") und muss keine `[[Klammern]]` setzen.

Cognee und Jarvis erkennen Namen beim Ingesten automatisch und
verknüpfen sie mit Entity-Dateien (sobald diese existieren).

### Regel 4 — Tags von Jarvis automatisch gesetzt

Der Nutzer setzt nie selbst Tags. Jarvis extrahiert beim Ingesten
sinnvolle Tags aus dem Kontext. Bei Unsicherheit: Jarvis fragt nach
oder nimmt breite Defaults.

Gute Tags: breite wiederkehrende Kategorien (`familie`, `arbeit`,
`medizin`, `projekt-jarvis`).
Schlechte Tags: einmalige Ereignisse (`taha-fieber-23-april`).

Sprache der Tag-Werte: **deutsch** (siehe Sektion "Tag-Sprache" unten).

### Regel 5 — Sprache: Keys englisch, Inhalt frei

Frontmatter-Keys bleiben englisch: `date`, `type`, `name`, `tags`,
`rel_to_anchor`. Python-Code erwartet das.

Werte und Text-Body: komplett frei — deutsch, persisch, gemischt.
Jarvis versteht alles.

**Ausnahme:** Enumeration-Werte für type-Felder (zum Beispiel
`daily-log`, `entity`, `insights`) bleiben strikt englisch. Diese
Werte werden von Code als Enum verwendet, daher ist Konsistenz
kritisch. Freie Beschreibungs-Werte dürfen weiter in jeder Sprache
sein.

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

(Im MVP nicht aktiv — keine Entity-Files werden geschrieben.)

### Regel 7 — Zwei-Schichten in jeder Entity-Datei

Jede Entity-Datei hat zwei Schichten:

- **Frontmatter** = Navigations-System für den Graph (Regel 6)
- **Text-Body** = Gedächtnis-Inhalt (Persönliches, Beruf, Gesundheit,
  Historie)

Frontmatter minimal und strukturiert. Text wächst organisch mit der Zeit.

(Im MVP nicht aktiv.)

### Regel 8 — Provisorische Variablen für Graph-Traversal

Beziehungen werden verkettet durchlaufen:
- `anchor.son.mother` = Tahas Mutter = Ehefrau
- `anchor.spouse.mother` = Schwiegermutter
- `anchor.uncle.son` = Cousin

Dies ist die interne Query-Sprache. Der Nutzer fragt natürlich
("Wer ist Tahas Mutter?"), Jarvis übersetzt intern.

(Im MVP nicht aktiv.)

### Regel 9 — Schema speichert alles, Antwort selektiert

Memory-Dateien enthalten maximal viel Information.
Jarvis antwortet aber nur auf die konkrete Frage.

- "Hat Reza angerufen?" → "Ja, gestern um 18 Uhr."
- "Was weißt du über Reza?" → Voller Kontext wird geliefert.

Keine proaktiven Lebensläufe. Kein unangefragtes Erzählen.

### Regel 10 — Memory hat vier Typen (ADR-035)

Das Memory-System speichert genau vier Kategorien — und nur diese:

1. **Daily-Log** — Persönlicher Gedanken-Strom (Voice-Memos, Text-Einträge)
2. **Entity-Person** — Persönliche Sicht auf Menschen (Familie, Freunde, Kollegen, Patienten)
3. **Insights** — Erschlossene Charaktermuster, Vorlieben, Gewohnheiten
4. **Conversation** — Gesprächs-Gedächtnis mit Jarvis selbst

**Klarstellung (ADR-035):** HiMeS speichert nur Daten, die in keinem
anderen Tool existieren. Andere Datenarten gehen ausdrücklich nicht
in HiMeS:

| Datenart                  | Speicherort       |
| ------------------------- | ----------------- |
| Termine, Kalender-Events  | CalDAV (iCloud)   |
| Strukturierte Notizen     | Notion            |
| Tasks, Erinnerungen       | Things3           |
| Research-Material         | Notion / extern   |
| Medikamente, Orte, Konzepte | Notion          |

Jarvis als Orchestrator routet Anfragen zur richtigen Quelle.

**MVP-Scope:** Nur Typ 1 (Daily-Log) wird aktiv erstellt. Typen 2, 2a
und 4 sind im Anhang dokumentiert, im MVP aber nicht aktiv. Personen-
Wissen extrahiert Cognee direkt aus den Daily-Logs (passive Strategie
ADR-036).

## Memory-Typ 1: Daily-Log (MVP)

**Definition:** Ein Daily-Log ist ein Voice-Memo oder Text-Eintrag
eines Users zu einem bestimmten Tag. Jarvis verarbeitet es automatisch
und erstellt die .md-Datei mit Frontmatter und Text-Body.

### Dateipfad und Benennung

`/var/himes-data/memory/daily-logs/YYYY-MM-DD_user.md`

Beispiele:
- `2026-04-23_majid.md`
- `2026-04-23_taha.md`
- `2026-04-24_majid.md`

Eine Datei pro Tag pro User. Mehrere Memos desselben Users am selben
Tag werden in dieselbe Datei angehängt (siehe Text-Body-Struktur unten).

### Frontmatter-Felder

**Pflicht (drei Felder):**
- `type: daily-log`
- `date: YYYY-MM-DD`
- `user: <user_id>` — wer dieses Memo gesprochen hat

**Optional:**
- `tags: [kategorie1, kategorie2, ...]` — breite deutsche Kategorien,
  von Jarvis automatisch extrahiert. Leer wenn nichts klar erkennbar.
- `entities: [name1, name2, ...]` — erkannte Personen. Leer wenn keine.

Mehr ist im MVP nicht nötig. Cognee macht den Rest beim Indexieren.

### Was NICHT mehr im Frontmatter steht (im Vergleich zu früheren Entwürfen)

- `entries: <number>` — redundant. Anzahl der Memos lässt sich aus dem
  Body ablesen (Anzahl der `## HH:MM`-Header oder 1 wenn keine).
- `detected_events: [...]` — gestrichen aus dem MVP. Die ursprüngliche
  Idee war ein strukturiertes Event-Vokabular, das automatisch
  Tickets triggert. Im MVP ersetzt: Jarvis liest den Daily-Log-Text
  bei Bedarf neu und erstellt Tickets ad-hoc — oder Tickets sind ein
  separater, später entstehender Mechanismus. **Daily-Logs persistieren
  keine Domänen-Events; sie persistieren den Gedanken-Strom.**
- `actions_created: [...]` — gestrichen aus demselben Grund. Tickets
  sind ein eigenes System mit eigenem Speicherort, nicht Teil des
  Daily-Log-Frontmatters.

Volle ursprüngliche Spezifikation siehe Anhang A1.

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

### Multi-User-Kontext

Der `user:`-Wert bestimmt:
- Aus wessen Perspektive Antworten generiert werden
- Welcher Anchor für Beziehungs-Queries aktiv ist (sobald Entity-
  Schicht aktiv ist — im MVP irrelevant)
- Welche Kalender-Integration angesprochen wird

Beim Start des Systems ist nur Majid als User konfiguriert.
Multi-User-Aktivierung (Taha, Hossein, Ehefrau mit eigenen
Telegram-Accounts) kommt in späterer Phase.

### Vollständiges MVP-Beispiel

Datei: `/var/himes-data/memory/daily-logs/2026-04-23_taha.md`

```markdown
---
type: daily-log
date: 2026-04-23
user: taha
tags: [schule, einkauf, freunde]
entities: [taha, klaus]
---

Ich hab Mathe-Klassenarbeit am Freitag über Bruchrechnung.
Muss noch Hefte kaufen. Klaus hat angerufen, will morgen mit
mir was machen.
```

Datei mit mehreren Memos:

```markdown
---
type: daily-log
date: 2026-04-23
user: majid
tags: [familie, arbeit]
entities: [reza, fatima]
---

## 08:01

Reza hat heute morgen angerufen. Mama ist erkältet.

## 22:15

Termin mit Fatima morgen um 14 Uhr verschoben auf Donnerstag.
```

## Memory-Typ 2: Entity-Person — Future Work

Schema vollständig spezifiziert (siehe Anhang A2). Wird aktiviert wenn
Jarvis tatsächlich beginnt, Entity-Files zu schreiben (passive
Strategie ADR-036).

**Im MVP:** Diese Files werden nicht erstellt. Cognee extrahiert
Personen-Wissen direkt aus Daily-Logs.

## Memory-Typ 2a: Insights — Future Work

Schema vollständig spezifiziert (siehe Anhang A3). Wird aktiviert
parallel zu Memory-Typ 2.

**Im MVP:** Nicht aktiv.

## Memory-Typ 4: Conversation — Stub

Definition folgt wenn Phase 2.5 (Dream Phase) ansteht. Verhältnis zu
ADR-037 (Drei-Schichten-Gedächtnis) noch zu klären.

**Im MVP:** Nicht aktiv. Platzhalter.

## Tag-Sprache: Deutsch (verbindlich)

Tags und andere freie Beschreibungs-Werte werden auf **deutsch**
geschrieben.

Begründung:
- Voice-Memos sind deutsch — Tags in derselben Sprache vermeiden
  Übersetzungs-Mismatch beim Embedding-Lookup.
- Embedding-Suche ist sprachagnostisch — eine deutsche Tag-Sprache
  kostet nichts an Suchqualität.
- Mischmasch (mal `family`, mal `familie`) erzeugt Duplikate im Graph
  und macht Tag-Filter unzuverlässig.

Beispiele: `familie`, `arbeit`, `medizin`, `projekt-jarvis`, `schule`,
`einkauf`, `freunde`, `iran`.

(Ausnahme: Enumeration-Werte für `type`-Felder bleiben englisch,
siehe Regel 5.)

## Offene Punkte für nächste Sessions

- [ ] Memory-Typ 4 (Conversation) designen
- [ ] Drei-Schichten-Gedächtnis-Architektur ausarbeiten (ADR-037)
- [ ] Tool-Routing-Regeln definieren (wann Calendar, wann Notion, wann Memory)
- [ ] Jarvis-Prompt-Regeln die Regel 9 umsetzen
- [ ] Erste Anchor-Datei `majid-ahsan.md` erstellen (wenn Entity-Schicht aktiviert wird)
- [ ] Voice-Memo-zu-Markdown-Mapper-Skript spezifizieren (Phase 2.1 Schritt 5)

## Änderungs-Historie

- 2026-04-23: Initial. Die 10 Regeln festgelegt in Session mit Claude.
- 2026-04-23: Daily-Log-Schema als erster konkreter Memory-Typ definiert. Dual-Layer-Prinzip (Memory-Frontmatter + Action-Tickets) etabliert.
- 2026-04-23: Cleanup. Regel 10 Überschrift korrigiert (7 Typen → mehrere Typen). Event-Type-Werte strikt englisch (sozialer_kontakt → social_contact). Regel 5 um Enum-Klarstellung erweitert.
- 2026-04-23: Entity-Person-Schema definiert. Dateinamen-Konvention (vorname-nachname.md), 12 Frontmatter-Felder in 5 Gruppen, 6-Sektionen-Text-Body. Insights-Datei-Schema als paralleler Memory-Typ 2a eingeführt. Dual-Datei-Prinzip (Entity für Fakten, Insights für Charakter-Muster) etabliert.
- 2026-04-23: Cleanup. Regel 3 auf neue Dateinamen-Konvention (vorname-nachname.md) aktualisiert. Platzhalter `<n>` zu `<name>` an drei Stellen korrigiert. Header-Status auf Phase 2.1 aktualisiert. Offene-Punkte-Eintrag für Beziehungs-Vokabular präzisiert.
- 2026-04-23: Beziehungs-Vokabular für rel_to_anchor vollständig definiert (9 semantische Gruppen, 44 Werte). Vokabular für rel_via formalisiert (4 Werte). Unterscheidung mütterlich/väterlich konsequent über rel_via gelöst.
- 2026-04-25: MVP-Cleanup. Schema reduziert auf das, was für den MVP-Pfad (Voice-Memo → MD → Cognee → Jarvis-Antwort) tatsächlich nötig ist. Daily-Log-Frontmatter auf 3 Pflichtfelder + 2 optionale Felder reduziert. `detected_events`, `actions_created`, `entries` aus dem Daily-Log-Schema gestrichen (Tickets sind separates Konzept). Regel 10 auf 4 Memory-Typen aktualisiert (ADR-035). Tag-Sprache auf deutsch festgeschrieben. Memory-Typ 2, 2a und 4 als Future Work markiert. Vollständige Original-Spezifikationen (Entity-Person, Insights, Beziehungs-Vokabular, detected_events) in den Anhang verschoben — bleiben erhalten, sind aber klar von der MVP-Spec abgegrenzt.

---

# Anhang: Future Work

Alles ab hier ist **nicht MVP**. Diese Spezifikationen bleiben erhalten,
weil sie gute Vorarbeit sind — sie werden aktiviert, sobald die
zugehörige Phase ansteht. Nichts hier darf mit der MVP-Spec verwechselt
werden.

## A1. Erweiterte Daily-Log-Frontmatter-Felder (gestrichen aus MVP)

Die folgenden Felder waren ursprünglich Teil des Daily-Log-Schemas. Sie
sind aus dem MVP entfernt, weil:
- `entries` redundant zum Body ist
- `detected_events` und `actions_created` ein separates Ticket-System
  voraussetzen, das im MVP nicht existiert

### A1.1 Optional gewesene Felder

- `entries: <number>` — Anzahl der Memos an diesem Tag (nur wenn >1)
- `detected_events: [...]` — erkannte triggernde Ereignisse (siehe A1.2)
- `actions_created: [...]` — Referenzen auf automatisch erstellte
  Tickets im Format `YYYY-MM-DD_NNN_TYPE-slug`

### A1.2 Struktur von detected_events

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

  - type: social_contact
    person: klaus
    proposed_date: 2026-04-24
```

### A1.3 Extraktions-Regeln (waren für Jarvis gedacht)

**Großzügig extrahieren** wenn ein Event-Kandidat erkannt wird. Grund:
Das Ticket-System wäre das Sicherheitsnetz — User bestätigt oder lehnt ab.

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

### A1.4 Dual-Layer-Prinzip (war Begründung für die Felder)

Jedes extrahierte Event hatte zwei Schichten gehabt:

1. **Memory-Schicht:** Das Event wäre im `detected_events:`-Array des
   Daily-Log-Frontmatters gespeichert worden.
2. **Action-Schicht:** Für actionable Events hätte Jarvis automatisch
   ein Ticket in `/var/himes-data/tickets/inbox/` erstellt, referenziert
   im `actions_created:`-Feld.

Diese Architektur ist für eine spätere Phase nicht ausgeschlossen, im
MVP aber bewusst weggelassen.

## A2. Memory-Typ 2: Entity-Person (volle Spezifikation)

**Definition:** Eine Person-Entity ist eine Datei über einen Menschen
im Leben des Users: Familie, Freunde, Kollegen, Patienten, lose
Kontakte. Jarvis erstellt und pflegt diese Dateien automatisch
basierend auf Daily-Log-Erwähnungen (passive Strategie, ADR-036).

### A2.1 Dateipfad und Benennung

Pfad: `/var/himes-data/memory/entities/<vorname-nachname>.md`

Format: Kleinbuchstaben, Umlaute erhalten, Vorname und Nachname
durch Bindestrich getrennt.

Beispiele:
- majid-ahsan.md (Anchor)
- taha-ahsan.md
- reza-ahmadi.md
- fatima-ahmadi.md
- klaus-müller.md

Konvention: Alle Personen bekommen Vorname+Nachname im Dateinamen wenn
bekannt. Kulturell bedingt bei persischer Familie (Mr./Mrs. + Vorname +
Nachname). Falls Nachname nicht bekannt: nur Vorname, Datei kann später
umbenannt werden.

### A2.2 Frontmatter-Felder (12 Felder in 5 Gruppen)

**Gruppe 1 — Pflicht:**
- `type: entity`
- `entity_type: person`
- `name: <voller Anzeigename>`

**Gruppe 2 — Identität:**
- `aliases: [kurz_name, kose_name, ...]` — wichtig für Voice-Memo-Erkennung
- `gender: male oder female` — verpflichtend. Jarvis erschließt aus
  Namen oder fragt nach wenn unklar

**Gruppe 3 — Anchor-Beziehung (Kern):**
- `rel_to_anchor: <direkte Beziehung zum Default-Anchor>`
- `rel_via: <Vermittler-Person>` — nur bei indirekten Beziehungen
  (uncle + via mother), bei direkten null
- `birth_order: <1/2/3/null>` — nur bei Geschwistern oder Kindern

**Gruppe 4 — Sonderrollen:**
- `is_anchor: false` (nur majid-ahsan.md hat true)
- `is_primary_user: false` (nur Hauptnutzer hat true)

**Gruppe 5 — Auto-gepflegt (von Jarvis aktualisiert):**
- `first_mentioned: YYYY-MM-DD`
- `last_mentioned: YYYY-MM-DD`
- `mention_count: <integer>`

Plus: `tags` (automatisch extrahiert, wie bei Daily-Log)

### A2.3 Multi-User-Kontext

Bei Queries von anderen Usern (Taha, Hossein) wechselt der Query-Anchor
temporär. Die `rel_to_anchor`-Werte in den Dateien bleiben aber immer
relativ zum Default-Anchor (Majid).

### A2.4 Text-Body-Struktur (6 feste Sektionen)

Der Text-Body folgt einer festen Sektion-Struktur. Leere Sektionen
können weggelassen werden, aber die Reihenfolge ist konsistent.

```markdown
# <name>

## Persönliches
Wohnort, Herkunft, familiäre Stellung, Alter wenn bekannt

## Beruf
Tätigkeit, Arbeitsstelle, beruflicher Werdegang

## Gesundheit
Krankheiten, Medikamente, Allergien, medizinische Besonderheiten

## Familie
Ehepartner, Kinder, familiäre Zusammenhänge

## Kontakt
Telefon, Adresse, Messenger, bevorzugte Kommunikationswege

## Ereignisse
Selektiv kuratierte narrative Chronik wichtiger Lebensereignisse
```

### A2.5 Ereignisse-Sektion (kritisches Detail)

Diese Sektion ist das narrative Gegenstück zu den statistischen
Feldern im Frontmatter. Unterschied:

- Frontmatter (first_mentioned, last_mentioned, mention_count) =
  statistische Daten, maschinenlesbar
- Text-Body Ereignisse-Sektion = erzählende Einträge mit Kontext

Jarvis pflegt diese Sektion **selektiv**. Regel für was rein kommt:

**Rein:**
- Große Lebensereignisse (Heirat, Geburt, Tod, Scheidung)
- Medizinische Ereignisse (Diagnose, Operation, Genesung)
- Geographische Veränderungen (Umzug, Auswanderung)
- Berufliche Meilensteine (Abschluss, Beförderung, Jobwechsel)
- Beziehungs-relevante Events (Verlobung, erste Begegnung)

**Nicht rein:**
- Triviale Telefonate ("Reza hat angerufen" ohne wichtigen Inhalt)
- Alltägliche Erwähnungen ohne Relevanz
- Stimmungs-Beobachtungen ("war heute gut drauf")

Raw-Details bleiben in den Daily-Logs, die Ereignisse-Sektion ist
eine kuratierte Mini-Biografie für schnellen Überblick.

### A2.6 Dual-Layer-Prinzip (Entity + Insights)

Jede Person hat zwei parallele Dateien:

1. **Entity-Datei** (memory/entities/<name>.md) — harte verifizierbare Fakten
2. **Insights-Datei** (memory/insights/<name>.md) — erschlossene Charakter-Muster

Die Trennung ist bewusst: Fakten sind überprüfbar, Insights sind
Interpretationen. Siehe A3 für Details zur Insights-Datei.

### A2.7 Vollständiges Beispiel Entity-Datei

Datei: `/var/himes-data/memory/entities/reza-ahmadi.md`

```markdown
---
type: entity
entity_type: person
name: Reza Ahmadi
aliases: [Reza, Onkel Reza, Reza Jan]
gender: male
rel_to_anchor: uncle
rel_via: mother
birth_order: null
is_anchor: false
is_primary_user: false
first_mentioned: 2026-04-23
last_mentioned: 2026-05-08
mention_count: 7
tags: [familie, medizin, iran]
---

# Reza Ahmadi

## Persönliches
Bruder von Majids Mutter Fatima. Wohnt in Teheran.
Älterer Bruder von Fatima.

## Beruf
Arzt, Kardiologe. Eigene Praxis in Teheran seit 2015.

## Gesundheit
Diabetes Typ 2 seit 2019. Nimmt Metformin.

## Familie
Verheiratet mit Tahere. Tahere schwanger (Stand 2026-05-08).

## Kontakt
Telefon +98 xxx xxx

## Ereignisse
- 2019: Diabetes Typ 2 diagnostiziert
- 2022: Heirat mit Tahere
- 2026-05-08: Telefonat — Tahere ist schwanger
```

## A3. Memory-Typ 2a: Insights-Datei (volle Spezifikation)

**Definition:** Eine Insights-Datei speichert von Jarvis erschlossene
Charakter-Muster, Vorlieben und Gewohnheiten einer Person. Sie ist die
parallele Datei zur Entity-Datei und enthält weiche, interpretative
Informationen — nicht verifizierbare Fakten.

### A3.1 Zweck und Abgrenzung

Entity-Datei enthält: "Reza ist Arzt" (überprüfbar)
Insights-Datei enthält: "Reza ist großzügig" (erschlossen aus Mustern)

Diese Trennung ist wichtig weil:
- Fakten sind verifizierbar und wenig umstritten
- Charakterzüge sind Interpretationen die falsch sein können

Die Trennung verhindert dass weiche Schlussfolgerungen als harte
Fakten missverstanden werden.

### A3.2 Dateipfad und Benennung

Pfad: `/var/himes-data/memory/insights/<vorname-nachname>.md`

Derselbe Dateiname wie die Entity-Datei, nur in anderem Verzeichnis.

### A3.3 Frontmatter-Felder (6 Felder)

- `type: insights`
- `entity: <vorname-nachname>` — Referenz auf die Entity-Datei
- `generated_by: jarvis`
- `confidence: low oder medium oder high` — wie sicher ist Jarvis
  insgesamt bei diesen Insights
- `last_updated: YYYY-MM-DD`
- `evidence_count: <integer>` — wie viele Daily-Log-Erwähnungen sind
  die Basis

### A3.4 Text-Body (4 Sektionen)

```markdown
## Vorlieben
Was die Person mag oder bevorzugt

## Charaktermerkmale
Persönlichkeits-Eigenschaften (großzügig, freundlich, etc.)

## Gewohnheiten
Verhaltensmuster (wann ruft sie an, was bringt sie mit, etc.)

## Vermutungen (niedrige Konfidenz)
Einschätzungen die Jarvis für wahrscheinlich hält aber nicht
sicher ist
```

### A3.5 Keine Evidence-Referenzen

Insights werden narrativ formuliert, nicht mit Fußnoten oder Zählern
belegt. Wenn Details zu einer Einschätzung gebraucht werden, führt die
Spur zurück zu den Daily-Logs über die Erwähnungs-Statistik der
Entity-Datei.

### A3.6 Pflege-Regeln

- Jarvis aktualisiert Insights periodisch, nicht nach jedem Daily-Log
- Bei Widerspruch zwischen alten und neuen Beobachtungen: Jarvis fragt
  nach oder revidiert
- Insights beginnen in der Sektion "Vermutungen" und wandern bei
  genügend Bestätigung in "Charaktermerkmale" oder andere Sektionen

### A3.7 Vollständiges Beispiel Insights-Datei

Datei: `/var/himes-data/memory/insights/reza-ahmadi.md`

```markdown
---
type: insights
entity: reza-ahmadi
generated_by: jarvis
confidence: medium
last_updated: 2026-05-08
evidence_count: 14
---

# Insights über Reza Ahmadi

## Vorlieben
Trinkt gerne Kaffee — bei allen gemeinsamen Treffen bestellt er
türkischen Kaffee. Mag klassische persische Musik, erwähnt das
regelmäßig in Gesprächen.

## Charaktermerkmale
Großzügig mit Geld und Zeit — zahlt oft für andere, bringt
Geschenke bei Besuchen. Durchgehend freundlich in allen erfassten
Interaktionen, keine negativen Erwähnungen.

## Gewohnheiten
Ruft meistens abends an, etwa 19:00 Teheran-Zeit. Bei Besuchen
bringt er traditionell Süßigkeiten mit.

## Vermutungen (niedrige Konfidenz)
Könnte einsamer sein als er zugibt — erwähnt häufig Vergangenheit
und alte Freunde. Scheint gesundheitlich besorgter zu sein als er
in Gesprächen äußert.
```

## A4. Beziehungs-Vokabular für rel_to_anchor

Vollständige Liste der erlaubten Werte für `rel_to_anchor`, organisiert
in 9 semantische Gruppen. (Im MVP nicht aktiv — Entity-Files werden
nicht erstellt.)

### A4.1 Gruppe 1 — Direkte Kernfamilie

- mother — Mutter
- father — Vater
- son — Sohn
- daughter — Tochter
- brother — Bruder
- sister — Schwester

### A4.2 Gruppe 2 — Ehe und Partnerschaft

- husband — Ehemann
- wife — Ehefrau
- ex_husband — geschiedener Ehemann
- ex_wife — geschiedene Ehefrau
- partner — nicht-verheirateter Lebenspartner

### A4.3 Gruppe 3 — Großeltern und Enkel

- grandfather — Großvater
- grandmother — Großmutter
- grandson — Enkel
- granddaughter — Enkelin

Unterscheidung mütterlich/väterlich: über `rel_via` (siehe A5).

### A4.4 Gruppe 4 — Onkel, Tante, Cousins

- uncle — Onkel
- aunt — Tante
- cousin_male — männlicher Cousin
- cousin_female — weibliche Cousine

Weitere Details zur Herkunft (mütterlich/väterlich) über `rel_via` und
`gender`-Feld.

### A4.5 Gruppe 5 — Nichte und Neffe

- nephew — Neffe
- niece — Nichte

### A4.6 Gruppe 6 — Schwiegerverwandte

- father_in_law — Schwiegervater
- mother_in_law — Schwiegermutter
- brother_in_law — Schwager
- sister_in_law — Schwägerin
- son_in_law — Schwiegersohn
- daughter_in_law — Schwiegertochter

### A4.7 Gruppe 7 — Stiefverwandte

- stepfather — Stiefvater
- stepmother — Stiefmutter
- stepson — Stiefsohn
- stepdaughter — Stieftochter
- stepbrother — Stiefbruder
- stepsister — Stiefschwester

### A4.8 Gruppe 8 — Nicht-familiär

- friend — Freund/Freundin
- close_friend — enger Freund/beste Freundin
- colleague — Kollege/Kollegin
- boss — Vorgesetzter
- employee — Mitarbeiter
- patient — Patient (medizinischer Kontext)
- neighbor — Nachbar
- acquaintance — Bekannter, loser Kontakt

### A4.9 Gruppe 9 — Sonderfälle

- adopted_son — Adoptivsohn
- adopted_daughter — Adoptivtochter
- godparent — Patenelternteil
- godchild — Patenkind
- unknown — Beziehung nicht klar

## A5. Vokabular für rel_via

`rel_via` gibt den Vermittler-Weg bei indirekten Beziehungen an.
Erlaubte Werte:

- mother — über die Mutter (mütterlicherseits)
- father — über den Vater (väterlicherseits)
- spouse — über den Ehepartner
- null — nicht anwendbar (bei direkten Beziehungen wie mother, son, wife)

Beispiele:
- uncle mit `rel_via: mother` = Onkel mütterlicherseits (Bruder der Mutter)
- grandfather mit `rel_via: father` = Großvater väterlicherseits
- sister_in_law mit `rel_via: spouse` = Schwester des Ehepartners
- mother mit `rel_via: null` = eigene Mutter (direkte Beziehung)
