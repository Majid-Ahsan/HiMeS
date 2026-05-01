"""Hint-Extraktor für Daily-Log-Texte (ADR-050 D7).

Deterministische Regex-/Wortlisten-Extraktion. Kein LLM, kein NER,
kein POS-Tagging — der Bot formuliert aus den Hints den proaktiven
Vorschlag, hier passiert nur das Erkennen.

Drei Hint-Typen plus drei Datums-Subtypen:
- date_relative ("morgen", "nächste Woche", ...)
- date_weekday  ("Freitag", ...)
- date_explicit ("7.5.", "7. Mai", "14.12.2026", ...)
- task_verb     (Stamm-Match: "kaufen", "einkauf", "anrufen", ...)
- person        (großgeschriebene Wörter abseits Stop-Listen)

Akzeptierte Schuld:
- Personen-Heuristik produziert False-Positives (z.B. "St. Johannes
  Hospital" → mehrere Hints). Der Bot filtert beim Formulieren.
  COMMON_NOUNS_DE und SENTENCE_STARTERS werden über Zeit gepflegt.
- Stemming ist simple `\\b<stem>\\w*`-Match — Compounds wie "Einkauf"
  brauchen einen eigenen Stem-Eintrag (siehe Liste).
"""

from __future__ import annotations

import re

# ─── Konstanten ──────────────────────────────────────────────────────────

WEEKDAYS_DE = [
    "Montag", "Dienstag", "Mittwoch", "Donnerstag",
    "Freitag", "Samstag", "Sonntag",
]
_WEEKDAYS_SET = set(WEEKDAYS_DE)

MONTHS_DE = [
    "Januar", "Februar", "März", "April", "Mai", "Juni",
    "Juli", "August", "September", "Oktober", "November", "Dezember",
]
_MONTHS_SET = set(MONTHS_DE)

RELATIVE_DATES_SIMPLE = [
    "heute", "morgen", "übermorgen", "gestern", "vorgestern",
]

# Multi-Word-Patterns: jeweils `wort1\s+wort2` als Regex.
RELATIVE_DATES_COMPOUND = [
    r"nächste\s+Woche", r"kommende\s+Woche",
    r"diese\s+Woche", r"letzte\s+Woche",
    r"nächsten\s+Monat", r"kommenden\s+Monat",
]

TASK_VERB_STEMS = [
    "ruf",        # rufen, anrufen, gerufen, angerufen, Anruf
    "rief",       # rief (Präteritum von rufen, irreguläre Form)
    "kauf",       # kaufen, kaufte, gekauft, einkaufen, Einkauf
    "zahl",       # bezahlen, zahlte, Zahlung, Bezahlt
    "überweis",   # überweisen, überwies, Überweisung
    "buch",       # buchen, gebucht, Buchung
    "reservier",  # reservieren, reserviert, Reservierung
    "schick",     # schicken, schickte, geschickt
    "send",       # senden, sandte, gesendet
    "schreib",    # schreiben, schrieb, geschrieben
    "hol",        # holen, holte, geholt, abholen, Abholung, abgeholt
    "bring",      # bringen, gebracht (kein "brach" — zu kollidierend)
    "termin",     # Termin (Substantiv-Hinweis)
    "erinner",    # erinnern, erinnerte, Erinnerung
    "frag",       # fragen, fragte, gefragt
    "check",      # checken (Englisch-Lehnwort)
    "prüf",       # prüfen, prüfte, geprüft
    "bestell",    # bestellen, bestellt, Bestellung
    "abgeb",      # abgeben, abgegeben (NICHT "geb" — zu generisch)
    "absag",      # absagen, sagte ab, Absage
    "abgesag",    # abgesagt (ge-Einschub im Partizip — eigener Stem nötig)
]

# Wörter, die einen Task-Verb-Stem enthalten, aber semantisch keine
# Tasks anzeigen. Case-sensitive (deutsche Substantive sind groß,
# konsistent mit COMMON_NOUNS_DE). Gefiltert nach erfolgreichem
# Stem-Match in _extract_task_verbs.
TASK_VERB_FALSE_POSITIVES = {
    # hol-Stem
    "Holz", "Holzfäller", "Wiederholung", "Wiederholungen",
    # zahl-Stem (Numerisches, kein Task)
    "Anzahl", "Mehrzahl", "Zahl", "Zahlen", "Zahlenwert",
    # bring-Stem (semantisch andere Verben)
    "verbringen", "verbracht", "verbringt", "verbringe",
    "erbringen", "erbracht", "erbringt", "Erbringung",
    # buch-Stem (Substantiv-Kollisionen)
    "Buch", "Bücher", "Büchern", "Buchstabe", "Buchstaben",
}

# Großgeschriebene Wörter, die fast nie Eigennamen sind.
COMMON_NOUNS_DE = {
    # Familie
    "Mutter", "Vater", "Bruder", "Schwester", "Sohn", "Tochter",
    "Kinder", "Familie", "Eltern", "Frau", "Mann", "Partner",
    # Arbeit/Medizin (Majid-spezifisch)
    "Arbeit", "Klinik", "Krankenhaus", "Patient", "Patienten",
    "Kollege", "Kollegen", "Chef", "OP", "Termin", "Termine",
    "Schicht", "Echo", "TEE", "Diagnose", "Therapie",
    # Schule/Kinder
    "Schule", "Lehrer", "Klassenarbeit", "Hausaufgaben",
    # Alltag
    "Haus", "Wohnung", "Garten", "Auto", "Bahn", "Zug",
    "Frühstück", "Mittagessen", "Abendessen", "Tee", "Kaffee",
    "Morgen", "Mittag", "Abend", "Nacht",
    "Brot", "Tag", "Tage", "Woche", "Wochen", "Monat", "Monate", "Jahr", "Jahre",
    # Iran/Krieg-Kontext (aus Beispielen 2026-04-13)
    "Iran", "USA", "Krieg",
    # Generisch
    "Internet", "Telefon", "Computer", "KI",
}

# Wörter, die am Satzanfang großgeschrieben stehen, ohne Eigennamen zu sein.
SENTENCE_STARTERS = {
    "Ich", "Du", "Er", "Sie", "Es", "Wir", "Ihr",
    "Der", "Die", "Das", "Ein", "Eine", "Einen",
    "Heute", "Gestern", "Morgen", "Jetzt", "Dann", "Danach",
    "Aber", "Und", "Oder", "Weil", "Wenn", "Als", "Nach",
    "Vor", "Bei", "Auf", "In", "Im", "Mit", "Ohne", "Für",
}


# ─── Vorkompilierte Regex ────────────────────────────────────────────────

_WEEKDAY_RE = re.compile(r"\b(" + "|".join(WEEKDAYS_DE) + r")\b")
_RELATIVE_SIMPLE_RE = re.compile(
    r"\b(" + "|".join(RELATIVE_DATES_SIMPLE) + r")\b", re.IGNORECASE
)
_RELATIVE_COMPOUND_RE = re.compile(
    "|".join(RELATIVE_DATES_COMPOUND), re.IGNORECASE
)
_EXPLICIT_NUMERIC_RE = re.compile(
    r"\b(\d{1,2}\.\s?\d{1,2}\.(?:\s?\d{2,4})?)"
)
_EXPLICIT_NAMED_RE = re.compile(
    r"\b(\d{1,2}\.\s+(?:" + "|".join(MONTHS_DE) + r"))(?:\s+\d{2,4})?\b"
)
# Großgeschriebene Wörter ≥2 Buchstaben (deutsche Umlaute zulässig).
_CAPITAL_WORD_RE = re.compile(r"\b([A-ZÄÖÜ][a-zäöüß]+)\b")
# Satzgrenze-Marker.
_SENTENCE_BREAK_RE = re.compile(r"[.!?]\s+")


# ─── Helpers ──────────────────────────────────────────────────────────────


def _context_snippet(text: str, start: int, end: int) -> str:
    """3 Wörter vor + Match + 3 Wörter nach. Whitespace normalisiert.

    Bei Match am Text-Anfang/-Ende entsprechend kürzer.
    """
    tokens = list(re.finditer(r"\S+", text))
    if not tokens:
        return ""
    first_idx: int | None = None
    last_idx: int | None = None
    for i, tok in enumerate(tokens):
        if tok.end() > start and tok.start() < end:
            if first_idx is None:
                first_idx = i
            last_idx = i
    if first_idx is None or last_idx is None:
        return ""
    lo = max(0, first_idx - 3)
    hi = min(len(tokens), last_idx + 4)
    return " ".join(tok.group() for tok in tokens[lo:hi])


def _hint(htype: str, value: str, position: int, context: str) -> dict:
    return {
        "type": htype,
        "value": value,
        "context": context,
        "_position": position,
    }


# ─── Extraktoren ─────────────────────────────────────────────────────────


def _extract_dates(text: str) -> list[dict]:
    out: list[dict] = []

    for m in _WEEKDAY_RE.finditer(text):
        out.append(_hint(
            "date_weekday", m.group(1), m.start(),
            _context_snippet(text, m.start(), m.end()),
        ))

    # Compounds zuerst: damit "nächste Woche" als ein Hint erkannt wird,
    # bevor "nächste" alleine als simple-relative gelesen werden könnte.
    compound_spans: list[tuple[int, int]] = []
    for m in _RELATIVE_COMPOUND_RE.finditer(text):
        out.append(_hint(
            "date_relative", m.group(0), m.start(),
            _context_snippet(text, m.start(), m.end()),
        ))
        compound_spans.append((m.start(), m.end()))

    def _in_compound(pos: int) -> bool:
        return any(s <= pos < e for s, e in compound_spans)

    for m in _RELATIVE_SIMPLE_RE.finditer(text):
        if _in_compound(m.start()):
            continue
        out.append(_hint(
            "date_relative", m.group(1).lower(), m.start(),
            _context_snippet(text, m.start(), m.end()),
        ))

    for m in _EXPLICIT_NUMERIC_RE.finditer(text):
        out.append(_hint(
            "date_explicit", m.group(1), m.start(),
            _context_snippet(text, m.start(), m.end()),
        ))

    for m in _EXPLICIT_NAMED_RE.finditer(text):
        out.append(_hint(
            "date_explicit", m.group(0).rstrip(), m.start(),
            _context_snippet(text, m.start(), m.end()),
        ))

    return out


def _extract_task_verbs(text: str) -> list[dict]:
    """Stem darf irgendwo innerhalb eines Wortes stehen.

    Pattern \\b\\w*<stem>\\w*\\b matched das ganze Wort, das den Stem
    irgendwo enthält — nicht nur am Wort-Anfang. Damit deckt z.B. der
    kauf-Stem auch "eingekauft" und "Einkauf" ab. value im Hint ist
    das vollständige umgebende Wort.

    Akzeptierte False-Positives: "kaufmännisch" (kauf), "Anzahl" (zahl),
    "Holz" (hol). Bot filtert beim Formulieren.
    """
    out: list[dict] = []
    for stem in TASK_VERB_STEMS:
        pattern = re.compile(
            r"\b\w*" + re.escape(stem) + r"\w*\b", re.IGNORECASE
        )
        for m in pattern.finditer(text):
            word = m.group(0)
            if word in TASK_VERB_FALSE_POSITIVES:
                continue
            out.append(_hint(
                "task_verb", word, m.start(),
                _context_snippet(text, m.start(), m.end()),
            ))
    return out


def _extract_persons(text: str) -> list[dict]:
    sentence_start_positions = {0}
    for m in _SENTENCE_BREAK_RE.finditer(text):
        sentence_start_positions.add(m.end())

    out: list[dict] = []
    for m in _CAPITAL_WORD_RE.finditer(text):
        word = m.group(1)
        pos = m.start()
        if word in _WEEKDAYS_SET or word in _MONTHS_SET:
            continue
        if word in COMMON_NOUNS_DE:
            continue
        if pos in sentence_start_positions and word in SENTENCE_STARTERS:
            continue
        out.append(_hint(
            "person", word, pos,
            _context_snippet(text, pos, m.end()),
        ))
    return out


# ─── Public API ──────────────────────────────────────────────────────────


def _dedupe_and_sort(hints: list[dict]) -> list[dict]:
    seen: set[tuple[str, str]] = set()
    unique: list[dict] = []
    for h in sorted(hints, key=lambda h: h["_position"]):
        key = (h["type"], h["value"])
        if key in seen:
            continue
        seen.add(key)
        unique.append({k: v for k, v in h.items() if k != "_position"})
    return unique


def extract_hints(text: str) -> list[dict]:
    """Extrahiert Datums-, Task-Verb- und Personen-Hints aus dem Text.

    Returns:
        Liste von Hint-Dicts mit ``type``, ``value``, ``context``,
        sortiert nach Position des ersten Auftretens. Duplikate
        gleichen ``(type, value)``-Paares werden entfernt.

        Hint-Typen:
          - ``date_weekday``  — z.B. "Freitag"
          - ``date_relative`` — z.B. "morgen", "nächste Woche"
          - ``date_explicit`` — z.B. "7.5.", "7. Mai", "14.12.2026"
          - ``task_verb``     — z.B. "kaufen", "einkaufen", "Einkauf"
          - ``person``        — z.B. "Reza"
    """
    hints: list[dict] = []
    hints.extend(_extract_dates(text))
    hints.extend(_extract_task_verbs(text))
    hints.extend(_extract_persons(text))
    return _dedupe_and_sort(hints)
