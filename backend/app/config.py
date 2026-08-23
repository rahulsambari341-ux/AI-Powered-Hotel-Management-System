"""
Centralized application settings.

All environment-variable access is kept here.
Other modules should import `settings` from this module.
"""

import os

from urllib.parse import quote_plus
from dotenv import load_dotenv



# ============================================================
# Load .env
# ============================================================

load_dotenv()


class Settings:

    # ========================================================
    # App
    # ========================================================

    APP_ENV: str = os.getenv(
        "APP_ENV",
        "development",
    )

    # ========================================================
    # Database
    # ========================================================

    MYSQL_HOST: str = os.getenv(
        "MYSQL_HOST",
        "localhost",
    )

    MYSQL_PORT: str = os.getenv(
        "MYSQL_PORT",
        "3306",
    )

    MYSQL_USER: str = os.getenv(
        "MYSQL_USER",
        "",
    )

    MYSQL_PASSWORD: str = os.getenv(
        "MYSQL_PASSWORD",
        "",
    )

    MYSQL_DATABASE: str = os.getenv(
        "MYSQL_DATABASE",
        "",
    )

    # ========================================================
    # AI / LLM
    # ========================================================

    # Optional OpenAI API key.
    #
    # Chat can use Ollama.
    # Kokoro TTS does NOT require this key.

    OPENAI_API_KEY: str = os.getenv(
        "OPENAI_API_KEY",
        "",
    )

    LLM_PROVIDER: str = os.getenv(
        "LLM_PROVIDER",
        "ollama",
    ).lower()

    OLLAMA_BASE_URL: str = os.getenv(
        "OLLAMA_BASE_URL",
        "http://localhost:11434/v1",
    )

    OLLAMA_MODEL: str = os.getenv(
        "OLLAMA_MODEL",
        "qwen2.5:7b-instruct",
    )

    # ========================================================
    # Telephony
    # ========================================================

    TWILIO_ACCOUNT_SID: str = os.getenv(
        "TWILIO_ACCOUNT_SID",
        "",
    )

    TWILIO_AUTH_TOKEN: str = os.getenv(
        "TWILIO_AUTH_TOKEN",
        "",
    )

    PUBLIC_BASE_URL: str = os.getenv(
        "PUBLIC_BASE_URL",
        "http://localhost:8000",
    )

    # ========================================================
    # Shared State - Phase 9.2
    # ========================================================

    REDIS_URL: str = os.getenv(
        "REDIS_URL",
        "",
    )

    SESSION_TTL_SECONDS: int = int(
        os.getenv(
            "SESSION_TTL_SECONDS",
            "3600",
        )
    )

    AUDIO_CACHE_TTL_SECONDS: int = int(
        os.getenv(
            "AUDIO_CACHE_TTL_SECONDS",
            "300",
        )
    )

    # ========================================================
    # CORS - Phase 9.4
    # ========================================================

    CORS_ORIGINS: str = os.getenv(
        "CORS_ORIGINS",
        (
            "http://localhost:5500,"
            "http://127.0.0.1:5500,"
            "http://localhost:3000,"
            "null"
        ),
    )

    # ========================================================
    # Rate Limiting - Phase 9.4
    # ========================================================

    RATE_LIMIT_ENABLED: bool = (
        os.getenv(
            "RATE_LIMIT_ENABLED",
            "true",
        ).lower()
        == "true"
    )

    # ========================================================
    # Notifications - Phase 8.4
    # ========================================================

    TWILIO_SMS_FROM_NUMBER: str = os.getenv(
        "TWILIO_SMS_FROM_NUMBER",
        "",
    )

    # ========================================================
    # Database URL
    # ========================================================

    @property
    def database_url(self) -> str:
        """
        SQLAlchemy MySQL connection URL.
        """

        return (
            f"mysql+pymysql://"
            f"{self.MYSQL_USER}:"
            f"{quote_plus(self.MYSQL_PASSWORD)}"
            f"@{self.MYSQL_HOST}:"
            f"{self.MYSQL_PORT}/"
            f"{self.MYSQL_DATABASE}"
    )


# ============================================================
# Shared settings instance
# ============================================================

settings = Settings()