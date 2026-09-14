"""Centralized, env-driven settings.

Per docs/CODING-GUIDELINES.md section 6: every RAG-tunable parameter lives here, not hardcoded
at call sites, so the evaluation experiment workflow (change one variable, re-run, compare) is
practical.
"""

from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    database_url: str

    # Embeddings
    # Decision (docs/ARCHITECTURE.md, Open Decisions): sentence-transformers/all-MiniLM-L6-v2 -
    # small, fast, CPU-friendly, well-established default for local embedding inference. Changing
    # this requires a migration (vector column dimension) and re-embedding existing chunks.
    embedding_model_name: str
    embedding_dimension: int

    # Chunking
    chunk_size: int
    chunk_overlap: int

    # Retrieval
    top_k: int
    similarity_threshold: float | None

    # LLM (Bedrock)
    bedrock_model_id: str
    bedrock_region: str

    # LLM (local/CPU)
    # "local" is the only supported value for now - Bedrock support (Step 8 continuation) isn't
    # implemented yet, so selecting it must fail loudly (see llm/factory.py), not silently.
    llm_provider: Literal["local"]
    local_llm_model_name: str

    # Observability (optional)
    # Empty/unset by design (not a "your call" default - see config.py's existing convention:
    # every field is env-required, .env.example is the single source of defaults, per the
    # earlier "no raw values baked into source code" hardening). LANGSMITH_API_KEY= (empty) is
    # the documented "disabled" state - tracing is then fully inert, no error, no warning spam
    # (see rag_service.py's @traceable usage and dependencies.py's env wiring, and the
    # empty-string-to-None handling shared with similarity_threshold below).
    langsmith_api_key: str | None

    # Prompts
    prompt_template_version: str

    # pydantic-settings does not coerce an empty .env string to None for Optional[float]/
    # Optional[str] fields (for the float case it tries to parse "" as a float and fails; for
    # the str case "" would otherwise stay a valid-but-empty string instead of None).
    # SIMILARITY_THRESHOLD= and LANGSMITH_API_KEY= must both still resolve to None.
    @field_validator("similarity_threshold", "langsmith_api_key", mode="before")
    @classmethod
    def _empty_string_to_none(cls, value: object) -> object:
        return None if value == "" else value


settings = Settings()
