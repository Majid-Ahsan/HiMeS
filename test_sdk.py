"""
Phase 1.5.10c — Claude Code SDK Compatibility Test

Tests whether claude-code-sdk can replace the subprocess-based Claude invocation.
Does NOT change any bot code.
"""

import asyncio
import inspect
import time
import traceback

# Monkey-patch: SDK 0.0.25 crashes on unknown message types (e.g. rate_limit_event).
# Patch parse_message directly in the module so all callers use the patched version.
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

        # Also patch the import in the client module that already holds a reference
        import claude_code_sdk._internal.client as cl
        cl.parse_message = _safe_parse
        print("✅ SDK-Patch angewendet (skip unknown message types)")
    except Exception as e:
        print(f"⚠️  SDK-Patch fehlgeschlagen: {e}")

_patch_sdk()


# ── Step A: Import SDK ──────────────────────────────────────────────────────

def step_a_import():
    """Try importing the SDK and report available classes."""
    print("=" * 60)
    print("STEP A: Import claude-code-sdk")
    print("=" * 60)

    try:
        import claude_code_sdk
        print(f"✅ claude_code_sdk importiert (Version: {getattr(claude_code_sdk, '__version__', 'unbekannt')})")
        print(f"   Verfügbare Exports: {[x for x in dir(claude_code_sdk) if not x.startswith('_')]}")
        return claude_code_sdk
    except ImportError as e:
        print(f"❌ Import fehlgeschlagen: {e}")
        traceback.print_exc()
        return None


# ── Step B: Inspect ClaudeCodeOptions ────────────────────────────────────────

def step_b_inspect(sdk):
    """Inspect available options/config classes."""
    print("\n" + "=" * 60)
    print("STEP B: SDK-Parameter inspizieren")
    print("=" * 60)

    # Try common class names
    options_class = None
    for name in ["ClaudeCodeOptions", "ClaudeAgentOptions", "ClaudeSDKOptions", "Options"]:
        cls = getattr(sdk, name, None)
        if cls:
            options_class = cls
            print(f"✅ Options-Klasse gefunden: {name}")
            break

    if not options_class:
        print("⚠️  Keine Options-Klasse gefunden, suche in allen Exports...")
        for attr_name in dir(sdk):
            attr = getattr(sdk, attr_name)
            if isinstance(attr, type) and "option" in attr_name.lower():
                options_class = attr
                print(f"✅ Gefunden: {attr_name}")
                break

    if options_class:
        # Inspect parameters
        sig = inspect.signature(options_class)
        print(f"\n   Parameter von {options_class.__name__}:")
        for param_name, param in sig.parameters.items():
            default = param.default if param.default != inspect.Parameter.empty else "REQUIRED"
            annotation = param.annotation if param.annotation != inspect.Parameter.empty else "Any"
            print(f"   - {param_name}: {annotation} = {default}")

        # Check for specific fields we care about
        important = ["system_prompt", "model", "max_turns", "mcp_config",
                      "mcp_config_path", "mcp_servers", "permission_mode",
                      "permissions", "cwd", "allowed_tools"]
        print(f"\n   Wichtige Parameter-Checks:")
        for key in important:
            found = key in sig.parameters
            print(f"   {'✅' if found else '❌'} {key}")
    else:
        print("❌ Keine Options-Klasse gefunden")

    # Check for query function
    query_fn = getattr(sdk, "query", None)
    if query_fn:
        print(f"\n✅ query() Funktion gefunden")
        sig = inspect.signature(query_fn)
        print(f"   Parameter: {list(sig.parameters.keys())}")
    else:
        print("\n❌ query() Funktion nicht gefunden")

    # Check for client class
    for name in ["ClaudeSDKClient", "ClaudeCodeClient", "Client"]:
        cls = getattr(sdk, name, None)
        if cls:
            print(f"✅ Client-Klasse gefunden: {name}")
            break

    return options_class, query_fn


# ── Step C: Create options instance ──────────────────────────────────────────

def step_c_create_options(sdk, options_class):
    """Create an options instance matching current bot config."""
    print("\n" + "=" * 60)
    print("STEP C: Options-Instanz erstellen")
    print("=" * 60)

    if not options_class and not getattr(sdk, "query", None):
        print("❌ Weder Options-Klasse noch query() verfügbar — Skip")
        return None

    # Build kwargs based on what the class accepts
    kwargs = {}
    sig = inspect.signature(options_class) if options_class else None

    if sig:
        params = sig.parameters
        if "system_prompt" in params:
            kwargs["system_prompt"] = "Du bist ein Test-Assistent. Antworte kurz auf Deutsch."
        if "model" in params:
            kwargs["model"] = "claude-sonnet-4-20250514"
        if "max_turns" in params:
            kwargs["max_turns"] = 5
        if "permission_mode" in params:
            kwargs["permission_mode"] = "bypassPermissions"
        if "mcp_servers" in params:
            kwargs["mcp_servers"] = "/app/config/mcp_config.json"
        if "cwd" in params:
            kwargs["cwd"] = "/app"

    try:
        if options_class:
            options = options_class(**kwargs)
            print(f"✅ Options erstellt: {options}")
        else:
            options = kwargs  # pass as dict to query()
            print(f"✅ Options als Dict: {kwargs}")
        return options
    except Exception as e:
        print(f"❌ Options-Erstellung fehlgeschlagen: {e}")
        traceback.print_exc()
        return None


# ── Steps D/E/F: Run tests ──────────────────────────────────────────────────

async def step_d_test_hello(sdk, options):
    """Test 1: Send 'Sage Hallo' and measure cold start time."""
    print("\n" + "=" * 60)
    print("STEP D: Test 1 — Kaltstart ('Sage Hallo')")
    print("=" * 60)

    query_fn = getattr(sdk, "query", None)
    if not query_fn:
        print("❌ query() nicht verfügbar — Skip")
        return None, None

    start = time.monotonic()
    full_text = ""
    try:
        async for msg in query_fn(prompt="Sage Hallo", options=options):
            if msg is None:
                continue
            # Collect text from response
            if hasattr(msg, "content"):
                for block in msg.content:
                    if hasattr(block, "text"):
                        full_text += block.text
            elif hasattr(msg, "result"):
                full_text = msg.result if isinstance(msg.result, str) else str(msg.result)

        elapsed = time.monotonic() - start
        print(f"✅ Antwort ({elapsed:.1f}s): {full_text[:200]}")
        return elapsed, full_text
    except Exception as e:
        elapsed = time.monotonic() - start
        print(f"❌ Fehler nach {elapsed:.1f}s: {e}")
        traceback.print_exc()
        return elapsed, None


async def step_e_test_followup(sdk, options):
    """Test 2: Send follow-up to check warm start."""
    print("\n" + "=" * 60)
    print("STEP E: Test 2 — Warmstart ('Was war meine erste Frage?')")
    print("=" * 60)

    query_fn = getattr(sdk, "query", None)
    if not query_fn:
        print("❌ query() nicht verfügbar — Skip")
        return None, None

    start = time.monotonic()
    full_text = ""
    try:
        async for msg in query_fn(
            prompt="Was war meine erste Frage?",
            options=options,
        ):
            if msg is None:
                continue
            if hasattr(msg, "content"):
                for block in msg.content:
                    if hasattr(block, "text"):
                        full_text += block.text
            elif hasattr(msg, "result"):
                full_text = msg.result if isinstance(msg.result, str) else str(msg.result)

        elapsed = time.monotonic() - start
        print(f"✅ Antwort ({elapsed:.1f}s): {full_text[:200]}")
        return elapsed, full_text
    except Exception as e:
        elapsed = time.monotonic() - start
        print(f"❌ Fehler nach {elapsed:.1f}s: {e}")
        traceback.print_exc()
        return elapsed, None


async def step_f_test_tools(sdk, options):
    """Test 3: Send tool-requiring prompt, check for tool use."""
    print("\n" + "=" * 60)
    print("STEP F: Test 3 — MCP Tool-Test ('Welcher Wochentag ist heute?')")
    print("=" * 60)

    query_fn = getattr(sdk, "query", None)
    if not query_fn:
        print("❌ query() nicht verfügbar — Skip")
        return False

    tools_used = []
    full_text = ""
    try:
        async for msg in query_fn(
            prompt="Welcher Wochentag ist heute? Nutze das current_time Tool.",
            options=options,
        ):
            if msg is None:
                continue

            # Check for tool use blocks
            if hasattr(msg, "content"):
                for block in msg.content:
                    block_type = type(block).__name__
                    if "ToolUse" in block_type or "tool_use" in getattr(block, "type", ""):
                        tool_name = getattr(block, "name", getattr(block, "tool_name", "unknown"))
                        tools_used.append(tool_name)
                        print(f"   🔧 Tool verwendet: {tool_name}")
                    if hasattr(block, "text"):
                        full_text += block.text
            elif hasattr(msg, "result"):
                full_text = msg.result if isinstance(msg.result, str) else str(msg.result)

        mcp_ok = len(tools_used) > 0
        print(f"{'✅' if mcp_ok else '⚠️'} Tools: {tools_used or 'keine'}")
        print(f"   Antwort: {full_text[:200]}")
        return mcp_ok
    except Exception as e:
        print(f"❌ Fehler: {e}")
        traceback.print_exc()
        return False


# ── Step G: Summary ──────────────────────────────────────────────────────────

def step_g_summary(cold_time, warm_time, mcp_ok):
    print("\n" + "=" * 60)
    print("ZUSAMMENFASSUNG")
    print("=" * 60)
    print(f"  Kaltstart-Zeit:  {f'{cold_time:.1f}s' if cold_time else 'N/A'}")
    print(f"  Warmstart-Zeit:  {f'{warm_time:.1f}s' if warm_time else 'N/A'}")
    if cold_time and warm_time:
        speedup = cold_time - warm_time
        print(f"  Speedup:         {f'{speedup:+.1f}s' if speedup > 0 else 'kein Speedup'}")
    print(f"  MCP funktioniert: {'✅ Ja' if mcp_ok else '❌ Nein'}")
    print("=" * 60)


# ── Main ─────────────────────────────────────────────────────────────────────

async def main():
    # Step A
    sdk = step_a_import()
    if not sdk:
        print("\n❌ SDK nicht verfügbar. Abbruch.")
        return

    # Step B
    options_class, query_fn = step_b_inspect(sdk)

    # Step C
    options = step_c_create_options(sdk, options_class)

    # Steps D, E, F
    cold_time, cold_text = await step_d_test_hello(sdk, options)
    warm_time, warm_text = await step_e_test_followup(sdk, options)
    mcp_ok = await step_f_test_tools(sdk, options)

    # Step G
    step_g_summary(cold_time, warm_time, mcp_ok)


if __name__ == "__main__":
    asyncio.run(main())
