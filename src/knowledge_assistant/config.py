"""Centralized, env-driven settings.

Per docs/CODING-GUIDELINES.md section 6: every RAG-tunable parameter lives here, not hardcoded
at call sites, so the evaluation experiment workflow (change one variable, re-run, compare) is
practical.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    database_url: str = "postgresql+psycopg://knowledge_assistant:knowledge_assistant@localhost:5432/knowledge_assistant"

    # Embeddings
    # Decision (docs/ARCHITECTURE.md, Open Decisions): sentence-transformers/all-MiniLM-L6-v2 -
    # small, fast, CPU-friendly, well-established default for local embedding inference. Changing
    # this requires a migration (vector column dimension) and re-embedding existing chunks.
    embedding_model_name: str = "sentence-transformers/all-MiniLM-L6-v2"
    embedding_dimension: int = 384

    # Chunking
    chunk_size: int = 800
    chunk_overlap: int = 100

    # Retrieval
    top_k: int = 5
    similarity_threshold: float | None = None

    # LLM (Bedrock)
    bedrock_model_id: str = "anthropic.claude-3-haiku-20240307-v1:0"
    bedrock_region: str = "us-east-1"

    # Prompts
    prompt_template_version: str = "v1"


settings = Settings()
