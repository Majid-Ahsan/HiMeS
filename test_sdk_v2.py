"""
Phase 1.5.10c-verify — ClaudeSDKClient Subprocess Reuse Test

Frage: Nutzt ClaudeSDKClient als async context manager den gleichen
Claude-Subprocess für mehrere Nachrichten, oder startet er jedesmal neu?
"""

import asyncio
import subprocess
import time
import traceback


# ── Monkey-patch (rate_limit_event ist in SDK 0.0.25 unbekannt) ─────────────

def _patch_sdk():
    try:
        import claude_code_sdk._internal.message_parser as mp
        _original_parse = mp.parse_message

        def _safe_parse(data):
            try:
                return _original_parse(data)
            except mp.MessageParseError:
                return None

        mp.parse_message = _safe_parse

        import claude_code_sdk._internal.client as cl
        cl.parse_message = _safe_parse
    except Exception as e:
        print(f"⚠️  SDK-Patch fehlgeschlagen: {e}")

_patch_sdk()


from claude_code_sdk import (
    ClaudeSDKClient,
    ClaudeCodeOptions,
    AssistantMessage,
    TextBlock,
    ToolUseBlock,
    ResultMessage,
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def get_claude_pids() -> set[str]:
    """Findet alle laufenden claude-Prozesse via pgrep."""
    try:
        result = subprocess.run(
            ["pgrep", "-f", "claude"],
            capture_output=True, text=True, timeout=5,
        )
        if result.stdout.strip():
            return set(result.stdout.strip().split("\n"))
        return set()
    except Exception:
        return set()


async def send_and_measure(client, prompt: str, label: str) -> tuple[float, float | None, set[str], str]:
    """Sendet eine Nachricht, misst Zeit, sammelt Antwort + PIDs."""
    t0 = time.perf_counter()
    await client.query(prompt)

    first_token_time = None
    result_text = ""
    tools_used = []

    async for msg in client.receive_response():
        if msg is None:
            continue
        if isinstance(msg, AssistantMessage):
            for block in msg.content:
                if isinstance(block, TextBlock):
                    if first_token_time is None:
                        first_token_time = time.perf_counter() - t0
                    result_text += block.text
                elif isinstance(block, ToolUseBlock):
                    tools_used.append(block.name)
        elif isinstance(msg, ResultMessage):
            # Final message — session complete
            if hasattr(msg, "result") and msg.result and not result_text:
                result_text = str(msg.result)
            break

    total_time = time.perf_counter() - t0
    pids = get_claude_pids()

    print(f"\n[{label}]")
    print(f"  Prompt:        {prompt[:70]}")
    print(f"  First token:   {f'{first_token_time:.2f}s' if first_token_time else 'N/A'}")
    print(f"  Total time:    {total_time:.2f}s")
    print(f"  Tools used:    {tools_used or '-'}")
    print(f"  Response:      {result_text[:150]}")
    print(f"  Claude PIDs:   {sorted(pids)}")

    return total_time, first_token_time, pids, result_text


# ── Main ─────────────────────────────────────────────────────────────────────

async def main():
    options = ClaudeCodeOptions(
        system_prompt="Du bist Jarvis, ein Test-Assistent. Antworte kurz auf Deutsch.",
        model="claude-sonnet-4-20250514",
        max_turns=5,
        permission_mode="bypassPermissions",
        mcp_servers="/app/config/mcp_config.json",
        cwd="/app",
    )

    print("=" * 70)
    print("PIDs vor Client-Start")
    print("=" * 70)
    pids_before = get_claude_pids()
    print(f"Claude PIDs: {sorted(pids_before)}")

    print("\n" + "=" * 70)
    print("Starte ClaudeSDKClient als async context manager")
    print("=" * 70)
    t_start = time.perf_counter()

    results: list[tuple[float, float | None, set[str], str]] = []

    try:
        async with ClaudeSDKClient(options=options) as client:
            t_connected = time.perf_counter() - t_start
            print(f"Client verbunden in {t_connected:.2f}s")

            pids_after_connect = get_claude_pids()
            print(f"Claude PIDs nach connect: {sorted(pids_after_connect)}")
            new_pids = pids_after_connect - pids_before
            print(f"Neue PIDs durch Client:   {sorted(new_pids)}")

            # 4 Nachrichten im GLEICHEN async with Block
            results.append(await send_and_measure(
                client,
                "Merk dir die Zahl 42 und nenne sie mir am Ende wieder.",
                "Message 1",
            ))

            results.append(await send_and_measure(
                client,
                "Sag mir den Wochentag heute. Nutze das current_time Tool.",
                "Message 2 (mit MCP-Tool)",
            ))

            results.append(await send_and_measure(
                client,
                "Was ist 7 mal 8?",
                "Message 3",
            ))

            results.append(await send_and_measure(
                client,
                "Welche Zahl sollte ich mir merken?",
                "Message 4 (Session-Continuity Test)",
            ))
    except Exception as e:
        print(f"\n❌ Fehler im Client-Block: {e}")
        traceback.print_exc()

    pids_after_exit = get_claude_pids()
    print(f"\nClaude PIDs nach Client-Exit: {sorted(pids_after_exit)}")

    # ── Analyse ─────────────────────────────────────────────────────────────

    if not results:
        print("\n❌ Keine Ergebnisse — Abbruch.")
        return

    print("\n" + "=" * 70)
    print("ZUSAMMENFASSUNG")
    print("=" * 70)
    print(f"{'Message':<30} {'Total':>10} {'FirstTok':>10} {'PIDs':>25}")
    for i, (total, first, pids, _) in enumerate(results, 1):
        first_str = f"{first:.2f}s" if first else "N/A"
        pid_str = ",".join(sorted(pids))[:25]
        print(f"Message {i:<22} {total:>8.2f}s {first_str:>10} {pid_str:>25}")

    # PID-Analyse
    print("\n" + "=" * 70)
    print("ANALYSE")
    print("=" * 70)
    all_pids = [r[2] for r in results]
    unique_pid_sets = set(frozenset(p) for p in all_pids)

    if len(unique_pid_sets) == 1:
        print(f"✅ Gleiche PIDs über alle Messages: {sorted(all_pids[0])}")
        print("   → Subprocess wird WIEDERVERWENDET")
    else:
        print(f"❌ PIDs ändern sich pro Message:")
        for i, p in enumerate(all_pids, 1):
            print(f"   Message {i}: {sorted(p)}")
        print("   → Neuer Subprocess pro Message")

    # Latenz-Analyse
    times = [r[0] for r in results]
    first_time = times[0]
    rest = times[1:]
    avg_rest = sum(rest) / len(rest) if rest else 0

    print(f"\nMessage 1:      {first_time:.2f}s")
    print(f"Messages 2-4:   avg {avg_rest:.2f}s, range {min(rest):.2f}s - {max(rest):.2f}s")

    if avg_rest < first_time * 0.5:
        print(f"✅ Folge-Nachrichten DEUTLICH schneller ({avg_rest:.1f}s vs {first_time:.1f}s)")
        print("   → SDK mit async with ist der richtige Weg!")
    elif avg_rest < first_time * 0.8:
        print(f"🔶 Folge-Nachrichten etwas schneller ({avg_rest:.1f}s vs {first_time:.1f}s)")
        print("   → SDK bringt moderate Verbesserung")
    else:
        print(f"❌ Folge-Nachrichten NICHT schneller ({avg_rest:.1f}s vs {first_time:.1f}s)")
        print("   → SDK bringt KEINEN Vorteil, roher CLI mit --input-format stream-json nötig")

    # Session-Continuity
    print("\n" + "=" * 70)
    print("SESSION-CONTINUITY")
    print("=" * 70)
    last_response = results[3][3] if len(results) >= 4 else ""
    mentions_42 = "42" in last_response
    print(f"Message 4 Antwort: {last_response[:200]}")
    if mentions_42:
        print("✅ '42' in Antwort gefunden — Session-Continuity funktioniert")
    else:
        print("❌ '42' NICHT in Antwort — jeder query() startet neue Session")


if __name__ == "__main__":
    asyncio.run(main())
