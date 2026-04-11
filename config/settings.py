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
