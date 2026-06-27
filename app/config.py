from pathlib import Path
import os

from pydantic_settings import BaseSettings, SettingsConfigDict

_data_root = Path(os.getenv("DATA_ROOT", "D:/bars-support-bot-data"))


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    telegram_bot_token: str = ""
    telegram_support_chat_id: str = ""
    telegram_proxy_url: str = ""

    llm_provider: str = "ollama"
    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_api_key: str = ""
    ollama_model: str = "qwen2.5:3b-instruct"
    ollama_vision_model: str = ""
    gigachat_credentials: str = ""
    gigachat_client_id: str = ""
    gigachat_client_secret: str = ""
    gigachat_model: str = "GigaChat"
    gigachat_scope: str = "GIGACHAT_API_PERS"

    embed_provider: str = "sentence-transformers"
    embed_model: str = "intfloat/multilingual-e5-base"

    qdrant_url: str = "http://127.0.0.1:6333"
    qdrant_collection: str = "bars_docs"

    redis_url: str = "redis://127.0.0.1:6379/0"

    confidence_threshold: float = 0.45
    top_k_chunks: int = 3
    chunk_size: int = 600
    chunk_overlap: int = 80

    app_host: str = "0.0.0.0"
    app_port: int = 8026
    docs_dir: Path = Path("data/docs")
    upload_dir: Path = Path("data/uploads")
    doc_images_dir: Path = _data_root / "doc-images"

    bot_name: str = "DocHelper Барс"
    bot_product_name: str = "БАРС-Офис и корпоративных сервисов Барс Груп"
    auto_index_on_start: bool = True
    telegram_enabled: bool = True

    whisper_enabled: bool = True
    whisper_model: str = "base"

    telegram_bot_username: str = ""
    public_demo_url: str = ""

    operator_pin: str = ""

    escalation_keywords: str = "оператор,человек,живой,менеджер"


settings = Settings()

ESCALATION_WORDS = {
    w.strip().lower()
    for w in settings.escalation_keywords.split(",")
    if w.strip()
}


def telegram_proxy_url() -> str | None:
    url = settings.telegram_proxy_url.strip()
    return url or None
