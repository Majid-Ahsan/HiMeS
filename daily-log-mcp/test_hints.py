"""Tests für daily-log-mcp/hints.py.

Deterministisch — keine Mocks nötig, reine Funktion.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("hints_under_test", _HERE / "hints.py")
hints = importlib.util.module_from_spec(_spec)
assert _spec.loader is not None
_spec.loader.exec_module(hints)


def _types_values(result: list[dict]) -> list[tuple[str, str]]:
    return [(h["type"], h["value"]) for h in result]


# ─── Datums-Tests ────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "weekday",
    ["Montag", "Dienstag", "Mittwoch", "Donnerstag",
     "Freitag", "Samstag", "Sonntag"],
)
def test_weekday_extraction(weekday):
    result = hints.extract_hints(f"Wir treffen uns am {weekday} morgens.")
    weekdays = [(h["type"], h["value"]) for h in result if h["type"] == "date_weekday"]
    assert weekdays == [("date_weekday", weekday)]


@pytest.mark.parametrize(
    "term",
    ["heute", "morgen", "übermorgen", "gestern", "vorgestern"],
)
def test_relative_date_simple(term):
    result = hints.extract_hints(f"Das war {term} der Fall.")
    rels = [(h["type"], h["value"]) for h in result if h["type"] == "date_relative"]
    assert rels == [("date_relative", term)]


@pytest.mark.parametrize(
    "phrase",
    ["nächste Woche", "kommende Woche", "diese Woche",
     "letzte Woche", "nächsten Monat", "kommenden Monat"],
)
def test_relative_date_compound(phrase):
    result = hints.extract_hints(f"Das passiert {phrase} bestimmt.")
    rels = [(h["type"], h["value"]) for h in result if h["type"] == "date_relative"]
    # value behält die Original-Schreibweise (kein lower für Compounds).
    assert any(v == phrase for _, v in rels)


def test_relative_compound_does_not_double_match():
    """nächste Woche darf nicht zusätzlich als simple-relative gelten."""
    result = hints.extract_hints("Wir machen das nächste Woche.")
    rels = [h["value"] for h in result if h["type"] == "date_relative"]
    assert rels == ["nächste Woche"]
    # Insbesondere nicht ["nächste", "Woche", "nächste Woche"] oder ähnlich.


def test_explicit_date_numeric_short():
    result = hints.extract_hints("Termin am 7.5. wurde verschoben.")
    explicits = [h["value"] for h in result if h["type"] == "date_explicit"]
    assert explicits == ["7.5."]


def test_explicit_date_numeric_full():
    result = hints.extract_hints("Geboren am 14.12.2026 in Bonn.")
    explicits = [h["value"] for h in result if h["type"] == "date_explicit"]
    assert explicits == ["14.12.2026"]


def test_explicit_date_numeric_two_digit_day():
    result = hints.extract_hints("Bis 30.04. erledigen.")
    explicits = [h["value"] for h in result if h["type"] == "date_explicit"]
    assert explicits == ["30.04."]


@pytest.mark.parametrize(
    "phrase",
    ["7. Mai", "14. Dezember", "1. Januar", "31. März"],
)
def test_explicit_date_named_month(phrase):
    result = hints.extract_hints(f"Geplant für den {phrase}.")
    explicits = [h["value"] for h in result if h["type"] == "date_explicit"]
    assert explicits == [phrase]


def test_explicit_date_named_with_year():
    result = hints.extract_hints("Stichtag ist der 7. Mai 2026.")
    explicits = [h["value"] for h in result if h["type"] == "date_explicit"]
    assert explicits == ["7. Mai 2026"]


def test_no_date_in_pure_prose():
    result = hints.extract_hints(
        "Das Wetter war angenehm und alle waren guter Laune."
    )
    dates = [h for h in result if h["type"].startswith("date_")]
    assert dates == []


# ─── Task-Verb-Tests ─────────────────────────────────────────────────────


def test_task_verb_infinitive():
    result = hints.extract_hints("Ich muss heute Brot kaufen.")
    assert ("task_verb", "kaufen") in _types_values(result)


def test_task_verb_kaufte_matched():
    """Mit kauf-Stem matched 'kaufte', 'gekauft', 'Einkauf' alle."""
    result = hints.extract_hints("Ich kaufte gestern Brot.")
    task_verbs = [v for t, v in _types_values(result) if t == "task_verb"]
    assert "kaufte" in task_verbs


@pytest.mark.parametrize("text,expected_match", [
    ("Habe gestern eingekauft.", "eingekauft"),
    ("Ich rief Reza an.", "rief"),
    ("Habe ihn angerufen.", "angerufen"),
    ("Der Einkauf war lang.", "Einkauf"),
    ("Heute geprüft.", "geprüft"),
    ("Den Termin abgesagt.", "abgesagt"),
    ("Pakete abgeholt.", "abgeholt"),
    ("Bezahlt habe ich gestern.", "Bezahlt"),
])
def test_task_verb_extended_forms(text, expected_match):
    """Generalisierte Stems matchen Partizipien, Konjugationen, Substantive."""
    result = hints.extract_hints(text)
    matches = [v for t, v in _types_values(result) if t == "task_verb"]
    assert expected_match in matches


def test_task_verb_acknowledged_false_positives():
    """Generischere Stems erzeugen erwartete False-Positives.
    Bot filtert beim Formulieren."""
    result = hints.extract_hints("Eine kaufmännische Aufgabe.")
    task_verbs = [h for h in result if h["type"] == "task_verb"]
    assert task_verbs  # nicht-leer — kaufmännisch via kauf-Stem


def test_task_verb_abgeb_not_match_geben():
    """abgeb-Stem matcht NICHT 'geben', 'gibt', 'gegeben' alleine.
    (Test-Text vermeidet bewusst 'Buch', das via buch-Stem matchen würde.)"""
    result = hints.extract_hints("Er gibt es ihm. Sie hat es gegeben.")
    task_verbs = [h for h in result if h["type"] == "task_verb"]
    assert task_verbs == []


@pytest.mark.parametrize("text,word", [
    ("Wir haben Holz fürs Lagerfeuer", "Holz"),
    ("Eine Wiederholung der Untersuchung", "Wiederholung"),
    ("Die Anzahl der Patienten war hoch", "Anzahl"),
    ("Mehrzahl statt Einzahl", "Mehrzahl"),
    ("Eine Zahl auf dem Display", "Zahl"),
    ("Wir haben den Tag verbracht", "verbracht"),
    ("Die Erbringung der Leistung", "Erbringung"),
    ("Ich lese ein Buch", "Buch"),
    ("Drei Bücher auf dem Tisch", "Bücher"),
])
def test_task_verb_false_positives_filtered(text, word):
    """Wörter mit Task-Verb-Stems, die semantisch keine Tasks sind,
    werden gefiltert."""
    result = hints.extract_hints(text)
    task_values = [h["value"] for h in result if h["type"] == "task_verb"]
    assert word not in task_values


def test_task_verb_real_tasks_still_match():
    """Sanity: Stop-Liste filtert nicht zu aggressiv."""
    cases = [
        ("Muss morgen einkaufen", "einkaufen"),
        ("Habe Reza angerufen", "angerufen"),
        ("Die Bezahlung steht aus", "Bezahlung"),
        ("Termin abgesagt", "abgesagt"),
        ("Pakete abgeholt", "abgeholt"),
    ]
    for text, expected in cases:
        result = hints.extract_hints(text)
        task_values = [h["value"] for h in result if h["type"] == "task_verb"]
        assert expected in task_values, f"Failed for: {text!r} (got {task_values})"


def test_task_verb_uberweis():
    """überweis-Stem deckt Verb- und Substantiv-Form ab."""
    result = hints.extract_hints("Habe die Überweisung gestern gemacht.")
    matches = [v for t, v in _types_values(result) if t == "task_verb"]
    assert "Überweisung" in matches


def test_task_verb_einkauf_noun_form():
    result = hints.extract_hints("Der Einkauf war anstrengend.")
    task_verbs = [v.lower() for t, v in _types_values(result) if t == "task_verb"]
    assert "einkauf" in task_verbs


def test_task_verb_einkaufen_compound():
    result = hints.extract_hints("Heute muss ich noch einkaufen.")
    task_verbs = [v.lower() for t, v in _types_values(result) if t == "task_verb"]
    # "einkauf" matched "einkaufen" via \beinkauf\w*.
    assert any(v.startswith("einkauf") for v in task_verbs)


def test_task_verb_anrufen():
    result = hints.extract_hints("Reza will ich morgen anrufen.")
    task_verbs = [v.lower() for t, v in _types_values(result) if t == "task_verb"]
    assert "anrufen" in task_verbs


def test_task_verb_termin():
    result = hints.extract_hints("Brauche einen Termin beim Zahnarzt.")
    task_verbs = [v.lower() for t, v in _types_values(result) if t == "task_verb"]
    assert any(v.startswith("termin") for v in task_verbs)


def test_task_verb_no_match():
    result = hints.extract_hints("Heute war es einfach nur ruhig.")
    task_verbs = [h for h in result if h["type"] == "task_verb"]
    assert task_verbs == []


# ─── Personen-Tests ──────────────────────────────────────────────────────


def test_person_simple():
    result = hints.extract_hints("Reza kam vorbei.")
    persons = [v for t, v in _types_values(result) if t == "person"]
    assert "Reza" in persons


def test_person_excludes_weekday():
    result = hints.extract_hints("Am Freitag kam Reza.")
    persons = [v for t, v in _types_values(result) if t == "person"]
    assert "Freitag" not in persons
    assert "Reza" in persons


def test_person_excludes_month_name():
    result = hints.extract_hints("Im Mai war alles ruhig.")
    persons = [v for t, v in _types_values(result) if t == "person"]
    assert "Mai" not in persons


def test_person_excludes_common_noun():
    result = hints.extract_hints("Der Patient war heute stabil.")
    persons = [v for t, v in _types_values(result) if t == "person"]
    assert "Patient" not in persons


def test_person_excludes_sentence_starter():
    result = hints.extract_hints("Heute war anstrengend. Ich gehe schlafen.")
    persons = [v for t, v in _types_values(result) if t == "person"]
    assert "Heute" not in persons
    assert "Ich" not in persons


def test_person_multiple_in_text():
    result = hints.extract_hints("Neda und Taha haben gespielt.")
    persons = [v for t, v in _types_values(result) if t == "person"]
    assert "Neda" in persons
    assert "Taha" in persons


def test_person_after_punctuation_starter_filtered():
    """'Aber' am Satzanfang nach Punkt darf keine Person sein."""
    result = hints.extract_hints("Es regnete. Aber Reza kam trotzdem.")
    persons = [v for t, v in _types_values(result) if t == "person"]
    assert "Aber" not in persons
    assert "Reza" in persons


# ─── Integration ─────────────────────────────────────────────────────────


def test_full_text_three_hint_types():
    text = (
        "Heute war OP-Tag, am Freitag kommt Reza, "
        "ich muss morgen noch Brot kaufen."
    )
    result = hints.extract_hints(text)
    tv = _types_values(result)

    assert ("date_weekday", "Freitag") in tv
    assert ("date_relative", "morgen") in tv
    assert ("task_verb", "kaufen") in tv
    assert ("person", "Reza") in tv

    persons = [v for t, v in tv if t == "person"]
    assert "Heute" not in persons   # sentence starter
    assert "Brot" not in persons    # common noun
    assert "Tag" not in persons     # common noun (OP-Tag)


def test_real_daily_log_excerpt():
    """Realitätscheck mit Auszug im Daily-Log-Stil (synthetisch — die
    echten 2026-04-13/14/15-Files leben nur auf VPS).

    Verb-Formen bewusst in matchbarer Variante (Infinitiv, Substantiv-
    Form). Partizipien (angerufen) und trennbare Verben (holt … ab)
    werden vom aktuellen Stem-Set NICHT erfasst — siehe Schuld-Linie
    im Modul-Docstring von hints.py.
    """
    text = (
        "Heute ist Mittwoch, der 15. April 2026.\n"
        "\n"
        "Reza will ich heute Morgen anrufen, geht ihm schlecht. "
        "Am Freitag wollten wir uns treffen — das muss ich noch checken. "
        "Neda will die Kinder am 17.4. von der Schule abholen."
    )
    result = hints.extract_hints(text)
    tv = _types_values(result)

    assert ("date_weekday", "Mittwoch") in tv
    assert ("date_explicit", "15. April 2026") in tv
    assert ("date_weekday", "Freitag") in tv
    assert ("date_explicit", "17.4.") in tv
    assert ("person", "Reza") in tv
    assert ("person", "Neda") in tv

    task_verbs = [v.lower() for t, v in tv if t == "task_verb"]
    assert "anrufen" in task_verbs
    assert "checken" in task_verbs
    assert "abholen" in task_verbs


def test_dedupe_same_type_value():
    result = hints.extract_hints("Am Freitag, ja Freitag, kommt Besuch.")
    weekdays = [h for h in result if h["type"] == "date_weekday"]
    assert len(weekdays) == 1
    assert weekdays[0]["value"] == "Freitag"


def test_position_order_preserved():
    text = "Reza am Freitag, dann Neda."
    result = hints.extract_hints(text)
    # Reihenfolge im Text: Reza, Freitag, Neda
    relevant = [
        h for h in result
        if (h["type"], h["value"]) in {
            ("person", "Reza"),
            ("date_weekday", "Freitag"),
            ("person", "Neda"),
        }
    ]
    values_in_order = [h["value"] for h in relevant]
    assert values_in_order == ["Reza", "Freitag", "Neda"]


def test_no_position_field_in_output():
    """_position ist intern, darf nicht im finalen Hint-Dict auftauchen."""
    result = hints.extract_hints("Reza kam am Freitag.")
    for h in result:
        assert "_position" not in h
        assert set(h.keys()) == {"type", "value", "context"}


# ─── Context-Tests ───────────────────────────────────────────────────────


def test_context_short_snippet_max_seven_words_for_single_match():
    text = "eins zwei drei vier fünf sechs sieben acht neun zehn"
    # "fünf" als Match-Wort (Position 5 von 10 Wörtern)
    # Heuristisch: 3 davor + Match + 3 danach = 7 Wörter
    # Wir simulieren das mit einem Stem-Match — nehme "checken" + Text mit Marker.
    text2 = "eins zwei drei checken fünf sechs sieben acht"
    result = hints.extract_hints(text2)
    task = next(h for h in result if h["type"] == "task_verb")
    words = task["context"].split()
    assert len(words) == 7
    assert words == ["eins", "zwei", "drei", "checken", "fünf", "sechs", "sieben"]


def test_context_at_text_start():
    text = "checken ist wichtig heute."
    result = hints.extract_hints(text)
    task = next(h for h in result if h["type"] == "task_verb")
    # Match am Anfang → kein "vor"-Kontext.
    words = task["context"].split()
    assert words[0] == "checken"
    assert len(words) <= 4


def test_context_at_text_end():
    text = "alle Aufgaben muss ich noch checken"
    result = hints.extract_hints(text)
    task = next(h for h in result if h["type"] == "task_verb")
    words = task["context"].split()
    assert words[-1] == "checken"
    assert len(words) <= 7


def test_context_whitespace_normalized():
    text = "morgens\n\n\n  ist\tReza  \n\nda"
    result = hints.extract_hints(text)
    person = next(h for h in result if h["type"] == "person" and h["value"] == "Reza")
    # Context enthält keine \n oder \t, alle Trenner sind einzelne Spaces.
    assert "\n" not in person["context"]
    assert "\t" not in person["context"]
    assert "  " not in person["context"]


def test_context_includes_match_value():
    text = "ich muss heute noch Reza anrufen unbedingt"
    result = hints.extract_hints(text)
    person = next(h for h in result if h["type"] == "person")
    assert "Reza" in person["context"]
