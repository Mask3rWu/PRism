from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file="backend/.env",
        extra="ignore",
        populate_by_name=True,
    )

    PORT: int = 8000
    LLM_API_KEY: str = Field(default="", alias="DEFAULT_LLM_API_KEY")
    LLM_MODEL: str = Field(default="", alias="DEFAULT_LLM_MODEL")
    LLM_ENDPOINT: str = Field(default="", alias="DEFAULT_LLM_BASE_URL")
    FERNET_KEY: str = ""
    FRONTEND_URL: str = "http://localhost:3000"
    ENABLE_SEED: bool = False
    LANGFUSE_PUBLIC_KEY: str = ""
    LANGFUSE_SECRET_KEY: str = ""
    LANGFUSE_HOST: str = "https://cloud.langfuse.com"
    LANGFUSE_ENVIRONMENT: str = "development"
    LANGFUSE_RELEASE: str = ""
    LANGFUSE_TRACE_CONTENT: bool = False
    LANGFUSE_INPUT_COST_PER_1M_TOKENS: float = 0.0
    LANGFUSE_CACHE_HIT_INPUT_COST_PER_1M_TOKENS: float = 0.0
    LANGFUSE_CACHE_MISS_INPUT_COST_PER_1M_TOKENS: float = 0.0
    LANGFUSE_OUTPUT_COST_PER_1M_TOKENS: float = 0.0


settings = Settings()
