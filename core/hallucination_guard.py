"""Hallucination guard — detects when assistant output contains domain-specific
factual claims (train numbers, gleis, delays) that weren't backed by a tool call
in the current turn.

Does NOT rewrite the output. Appends a disclaimer and logs a warning, so that
false positives don't destroy UX.

Design:
- Modular per-domain registration: add patterns + tool-name prefixes per domain
- Easy to extend (calendar, notion, weather later) without refactor
- Soft guard: disclaimer only, never blocks/rewrites
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Pattern

import structlog

log = structlog.get_logger("himes.guard")


@dataclass
class _Domain:
    name: str
    patterns: list[Pattern[str]] = field(default_factory=list)
    tool_prefixes: list[str] = field(default_factory=list)
    disclaimer: str = ""


class HallucinationGuard:
    """Domain-based soft guard against fabricated tool data.

    Workflow:
      1. Register a domain with (name, regex patterns, tool-name prefixes, disclaimer).
      2. After each assistant turn, call .check(text, tools_called).
      3. If domain patterns match but no tool from that domain was called
         in the current turn → append domain's disclaimer, log warning.

    Multiple domains are independent: DB patterns trigger only DB disclaimer, etc.
    """

    def __init__(self) -> None:
        self._domains: dict[str, _Domain] = {}

    def register_domain(
        self,
        name: str,
        patterns: list[str],
        tool_prefixes: list[str],
        disclaimer: str,
    ) -> None:
        """Register a domain to guard.

        Args:
            name: Domain identifier, e.g. "deutsche_bahn"
            patterns: List of regex strings — if ANY matches the output,
                the domain is considered "claimed" in the response.
            tool_prefixes: List of tool-name prefixes — if ANY tool call in
                the current turn starts with one of these, the claim is
                considered backed.
            disclaimer: Text appended to response when claim is unbacked.
        """
        compiled = [re.compile(p, re.IGNORECASE) for p in patterns]
        self._domains[name] = _Domain(
            name=name,
            patterns=compiled,
            tool_prefixes=tool_prefixes,
            disclaimer=disclaimer,
        )
        log.info("guard.domain_registered", domain=name,
                 patterns=len(compiled), prefixes=tool_prefixes)

    def check(self, text: str, tools_called: list[str]) -> tuple[bool, str]:
        """Check a response against all registered domains.

        Returns:
            (is_suspect, appended_disclaimers) — if no issue, returns (False, "").
            If suspect, returns (True, disclaimer_text_to_append).
            When multiple domains flag, disclaimers are joined with newlines.
        """
        if not text or not self._domains:
            return False, ""

        disclaimers: list[str] = []

        for domain in self._domains.values():
            # Does the text claim something in this domain?
            claimed = False
            matched_patterns: list[str] = []
            for pat in domain.patterns:
                m = pat.search(text)
                if m:
                    claimed = True
                    matched_patterns.append(m.group(0))
                    if len(matched_patterns) >= 3:
                        break

            if not claimed:
                continue

            # Was any tool from this domain called?
            backed = any(
                any(tool.startswith(pref) for pref in domain.tool_prefixes)
                for tool in tools_called
            )

            if not backed:
                log.warning(
                    "guard.unbacked_claim",
                    domain=domain.name,
                    matched=matched_patterns,
                    tools_called=tools_called,
                    text_len=len(text),
                )
                disclaimers.append(domain.disclaimer)
            else:
                log.debug(
                    "guard.claim_backed",
                    domain=domain.name,
                    tools_called=tools_called,
                )

        if not disclaimers:
            return False, ""

        # Join disclaimers with newline if multiple domains flagged
        combined = "\n\n".join(disclaimers)
        return True, combined


# ── Default-Registration für HiMeS ──────────────────────────────────────

def build_default_guard() -> HallucinationGuard:
    """Build the guard with all HiMeS domains pre-registered.

    Currently only Deutsche Bahn / VRR is registered. Calendar/Notion can be
    added later without changing the guard logic.
    """
    guard = HallucinationGuard()

    # Deutsche Bahn + VRR — the critical one (user runs to wrong platform)
    db_patterns = [
        # Train line identifiers (with optional space)
        r'\b(?:ICE|IC|EC|RE|RB|NX)\s?\d{1,5}\b',
        r'\b[SU]\s?\d{1,3}\b(?!\s*[%])',  # S1, S-Bahn number; exclude percentages
        r'\b(?:STR|Tram)\s?\d{1,3}\b',
        r'\bBus\s?\d{1,3}\b',
        # Gleis / Platform references
        r'\bGleis\s?\d+[a-zA-Z]?\b',
        r'\bGl\.\s?\d+[a-zA-Z]?\b',
        # Delay mentions
        r'\+\s?\d+\s?[Mm]in(?:uten)?\s+Verspätung',
        r'\bVerspätung\s+(?:von\s+)?\d+\s?[Mm]in',
        # Gleiswechsel (platform change — very scary if hallucinated)
        r'\bGleiswechsel\b',
        r'\bGleisänderung\b',
        # Specific disruption mentions with location + line
        # Accept both ö/oe spellings (Telegram users type both)
        r'\bSt(?:ö|oe)rung\s+(?:zwischen|auf|bei)\b',
        r'\bAusfall\s+(?:der|zwischen|auf)\b',
    ]
    db_tool_prefixes = [
        "mcp__deutsche-bahn__",     # stdio FastMCP tool name format
        "mcp__deutsche_bahn__",     # alternate naming
        "db_",                       # internal/unprefixed tool names
    ]
    db_disclaimer = (
        "\n\n⚠️ _Ohne Live-Verifikation — die oben genannten Zugdaten "
        "(Zeiten, Gleise, Verspätungen) konnten nicht über die DB-API bestätigt "
        "werden. Bitte im DB Navigator oder auf bahn.de gegenprüfen._"
    )

    guard.register_domain(
        name="deutsche_bahn",
        patterns=db_patterns,
        tool_prefixes=db_tool_prefixes,
        disclaimer=db_disclaimer,
    )

    return guard
