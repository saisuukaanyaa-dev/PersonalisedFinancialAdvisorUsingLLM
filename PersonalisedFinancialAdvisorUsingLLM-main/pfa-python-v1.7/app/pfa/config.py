"""Settings from environment variables (see .env.example)."""
import os
from dataclasses import dataclass, field


def _env(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


@dataclass(frozen=True)
class Settings:
    database_url: str = field(default_factory=lambda: _env("DATABASE_URL", "postgresql://pfa:pfa@localhost:5432/finance_advisor"))
    market_api_url: str = field(default_factory=lambda: _env("MARKET_API_URL", "http://localhost:8000").rstrip("/"))
    public_base_url: str = field(default_factory=lambda: _env("PUBLIC_BASE_URL", "http://localhost:8080").rstrip("/"))
    session_secret: str = field(default_factory=lambda: _env("SESSION_SECRET"))
    cookie_secure: bool = field(default_factory=lambda: _env("COOKIE_SECURE", "false").lower() == "true")

    openai_api_key: str = field(default_factory=lambda: _env("OPENAI_API_KEY"))
    openai_base_url: str = field(default_factory=lambda: _env("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/"))
    chat_model: str = field(default_factory=lambda: _env("OPENAI_MODEL", "gpt-5-mini"))
    reasoning_effort: str = field(default_factory=lambda: _env("OPENAI_REASONING_EFFORT", "low"))
    embed_model: str = field(default_factory=lambda: _env("OPENAI_EMBED_MODEL", "text-embedding-3-small"))
    llm_timeout_s: float = field(default_factory=lambda: float(_env("LLM_TIMEOUT_S", "90")))

    google_client_id: str = field(default_factory=lambda: _env("GOOGLE_CLIENT_ID"))
    google_client_secret: str = field(default_factory=lambda: _env("GOOGLE_CLIENT_SECRET"))

    # SerpAPI: live web data (optional). Free plan = 250 searches/month, 50/hour.
    serpapi_key: str = field(default_factory=lambda: _env("SERPAPI_API_KEY"))
    serpapi_base_url: str = field(default_factory=lambda: _env("SERPAPI_BASE_URL", "https://serpapi.com").rstrip("/"))
    serpapi_monthly_limit: int = field(default_factory=lambda: int(_env("SERPAPI_MONTHLY_LIMIT", "250")))
    serpapi_chat_reserve: int = field(default_factory=lambda: int(_env("SERPAPI_CHAT_RESERVE", "60")))
    serpapi_refresh_budget: int = field(default_factory=lambda: int(_env("SERPAPI_REFRESH_BUDGET", "10")))
    serpapi_refresh_hours: float = field(default_factory=lambda: float(_env("SERPAPI_REFRESH_HOURS", "24")))
    serpapi_quotes_per_refresh: int = field(default_factory=lambda: int(_env("SERPAPI_QUOTES_PER_REFRESH", "6")))
    serpapi_cache_hours: float = field(default_factory=lambda: float(_env("SERPAPI_CACHE_HOURS", "12")))

    kb_dir: str = field(default_factory=lambda: _env("KB_DIR", "/knowledge-base"))
    kb_table: str = "finance_kb_embeddings"

    @property
    def ai_enabled(self) -> bool:
        return bool(self.openai_api_key)

    @property
    def live_enabled(self) -> bool:
        return bool(self.serpapi_key)

    @property
    def google_enabled(self) -> bool:
        return bool(self.google_client_id and self.google_client_secret)


settings = Settings()
