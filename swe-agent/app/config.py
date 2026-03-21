"""
Central configuration loaded from environment / .env file.
All other modules import from here instead of reading os.environ directly.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # LLM
    openai_api_key: str = "sk-placeholder"
    openai_base_url: str = "https://api.openai.com/v1"
    model_name: str = "gpt-4o"

    # Embeddings
    embedding_model: str = "all-MiniLM-L6-v2"

    # Retrieval
    top_k_chunks: int = 20

    # Agent
    max_retries: int = 3
    test_timeout: int = 120

    # Sandbox
    sandbox_base_dir: str = "/tmp/swe_agent_sandboxes"


# Singleton – import this everywhere
settings = Settings()