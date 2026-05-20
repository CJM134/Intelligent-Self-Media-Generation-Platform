import os

from pydantic_settings import BaseSettings
from typing import Optional

# .env 文件位于项目根目录（backend/ 的上级）
_env_path = os.path.join(os.path.dirname(__file__), "..", ".env")


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

    # 即梦AI 图片生成配置（火山引擎 Ark）
    jimeng_api_key: str = "ark-10f4c9c6-d219-45a2-b292-e1cbe132ac0a-d279c"
    jimeng_api_base: str = "https://ark.cn-beijing.volces.com"
    jimeng_endpoint: str = "ep-20260520182901-hgg9z"

    # 数据库配置
    database_url: str = "sqlite:///./content_agent.db"

    # 敏感词库路径
    sensitive_words_file: str = "data/sensitive_words.txt"

    class Config:
        env_file = _env_path
        case_sensitive = False

settings = Settings()
