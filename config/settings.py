from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


class TelegramSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="TELEGRAM_")

    bot_token: str
    allowed_users: list[int] = []

    @classmethod
    def parse_allowed_users(cls, v: str | list[int]) -> list[int]:
        if isinstance(v, list):
            return v
        return [int(uid.strip()) for uid in v.split(",") if uid.strip()]


class ClaudeSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="CLAUDE_")

    model: str = "claude-sonnet-4-20250514"
    max_turns: int = 25
    max_tool_calls: int = 20
    # Phase 1.5.10d — Feature-Flag für persistenten SDK-Client.
    # True: claude-code-sdk mit wiederverwendetem Subprocess (schneller).
    # False: ClaudeSubprocess (alter Weg, Kaltstart pro Nachricht).
    use_sdk_client: bool = True
    # Phase 1.5.10f — Debug-Flag für SDK-Event-Inspection (temporär).
    # True: jedes Event aus client.receive_response() wird geloggt
    # (Typ, elapsed_ms, repr[:300], bei AssistantMessage zusätzlich
    # Block-Struktur). NIEMALS in Production dauerhaft an — produziert
    # pro Nachricht ~10-50 zusätzliche Log-Zeilen.
    debug_sdk_events: bool = False
    # Phase 1.5.10e v2a — explizite Tool-Whitelist statt Anthropic-eigener
    # ToolSearch (5-7s Overhead pro Anfrage bei >10 Tools).
    # True: nur die 6 MCP-Server + Read sind verfügbar, ToolSearch und
    # gefährliche Built-ins (Bash/Write/Cron/TodoWrite) sind ausgeschlossen.
    # False: alle Tools deferred (bisheriges Verhalten).
    use_allowed_tools_whitelist: bool = True
    # Phase 1.5.10e v2b — ToolSearch komplett abschalten via ENABLE_TOOL_SEARCH
    # env-var an den CLI-Subprocess. Mit v2a allein bleibt ToolSearch aktiv
    # (filtert Meta-Tools nicht), verursacht aber 0.6-1.0s Roundtrip +
    # Claude-Denkzeit pro Anfrage. v2b killt den Roundtrip komplett.
    # Historisch: in 1.5.10e v1 (ohne v2a) verursachte das scheinbar CalDAV-
    # Fehler — Ursache waren aber 3 unabhängige CalDAV-Bugs (in 1.5.21 gefixt).
    # Bei Regression dieses Flag auf False setzen, v2a bleibt aktiv.
    disable_tool_search: bool = True


class MCPSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MCP_")

    config_path: Path = Path("/app/config/mcp_config.json")


class MemorySettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MEMORY_")

    file_path: Path = Path("/app/data/MEMORY.md")


class LogSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="LOG_")

    level: str = "INFO"
    file_path: Path = Path("/app/logs/himes.log")


class HealthSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="HEALTH_")

    port: int = 8080


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    telegram: TelegramSettings = TelegramSettings()
    claude: ClaudeSettings = ClaudeSettings()
    mcp: MCPSettings = MCPSettings()
    memory: MemorySettings = MemorySettings()
    log: LogSettings = LogSettings()
    health: HealthSettings = HealthSettings()


settings = Settings()
