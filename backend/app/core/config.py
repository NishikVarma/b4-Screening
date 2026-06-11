from functools import lru_cache
from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── LLM ───────────────────────────────────────────────────
    llm_provider: Literal["openai", "google"] = "google"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o"
    google_api_key: str = ""
    google_model: str = "gemini-2.5-flash"

    # ── Embeddings ────────────────────────────────────────────
    embedding_provider: Literal["local", "openai"] = "local"
    embedding_model: str = "all-MiniLM-L6-v2"

    # ── Vector Store ──────────────────────────────────────────
    chroma_persist_dir: str = "../vector_store"

    # ── Knowledge Base ────────────────────────────────────────
    knowledge_base_dir: str = "../knowledge_base"

    # ── Database ──────────────────────────────────────────────
    database_url: str = "sqlite:///./screening.db"

    # ── App ───────────────────────────────────────────────────
    app_env: Literal["development", "production"] = "development"
    secret_key: str = "asldfjawenwerajck"
    cors_origins: str = "http://localhost:3000,http://localhost:5173,https://b4-screening-git-main-nishk-varmas-projects.vercel.app/"

    # ── RAG Tuning ────────────────────────────────────────────
    chunk_size: int = 500
    chunk_overlap: int = 50
    retrieval_top_k: int = 5

    # ── Derived helpers ───────────────────────────────────────
    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]

    @property
    def is_dev(self) -> bool:
        return self.app_env == "development"


@lru_cache
def get_settings() -> Settings:
    return Settings()