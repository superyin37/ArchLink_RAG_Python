from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # App
    APP_PORT: int = 4001
    APP_ENV: str = "development"

    # MySQL
    MYSQL_HOST: str = "127.0.0.1"
    MYSQL_PORT: int = 3306
    MYSQL_USER: str = "root"
    MYSQL_PASSWORD: str = ""
    MYSQL_DB: str = "rag_system"

    # Redis
    REDIS_HOST: str = "127.0.0.1"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: str = ""
    REDIS_DB: int = 0

    # JWT
    JWT_SECRET: str = "your-secret-key"

    # Meilisearch
    MEILISEARCH_ENABLED: bool = False
    MEILISEARCH_HOST: str = "http://localhost:7700"
    MEILISEARCH_API_KEY: str = "masterKey"

    # Doubao Embedding
    DOUBAO_HOST: str = ""
    DOUBAO_API_KEY: str = ""
    DOUBAO_EMBEDDING_MODEL: str = ""
    DOUBAO_EMBEDDING_BATCH_SIZE: int = 16

    # Qwen Embedding (DashScope)
    QWEN_API_KEY: str = ""
    QWEN_EMBEDDING_MODEL: str = "text-embedding-v4"

    # LLM Providers
    OPENAI_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    ANTHROPIC_KEY: str = ""
    AZURE_BASE: str = ""
    AZURE_KEY: str = ""
    GEMINI_KEY: str = ""
    DEEPSEEK_KEY: str = ""
    ARK_API_KEY: str = ""

    # File upload
    UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_SIZE: int = 100 * 1024 * 1024  # 100MB

    # Default model
    DEFAULT_MODEL_ID: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
