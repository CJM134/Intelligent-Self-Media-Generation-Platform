from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    # API 配置
    api_title: str = "Content Agent API"
    api_version: str = "0.1.0"
    debug: bool = False

    # 智谱AI API 配置
    zhipu_api_key: str
    zhipu_model: str = "glm-4-plus"

    # 天聚数行API 配置
    tianapi_key: str

    # 数据库配置
    database_url: str = "sqlite:///./content_agent.db"

    # 敏感词库路径
    sensitive_words_file: str = "data/sensitive_words.txt"

    class Config:
        env_file = ".env"
        case_sensitive = False

settings = Settings()
