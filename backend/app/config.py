from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    DATABASE_URL: str
    REDIS_URL: str
    MINIO_ENDPOINT: str
    MINIO_ACCESS_KEY: str
    MINIO_SECRET_KEY: str
    MINIO_BUCKET: str = "documents"
    MINIO_SECURE: bool = False
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    # OCR provider: "tesseract" (default, local) | "openai" (GPT-4o Vision)
    OCR_PROVIDER: str = "tesseract"
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o"


settings = Settings()
