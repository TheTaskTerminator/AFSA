"""
Application configuration management.
"""
from functools import lru_cache
from typing import Literal, Optional

from pydantic_settings import BaseSettings


class LLMProviderSettings:
    """LLM provider specific settings."""

    # OpenAI
    openai_api_key: str = ""
    openai_base_url: Optional[str] = None
    openai_model: str = "gpt-4-turbo-preview"

    # Anthropic
    anthropic_api_key: str = ""
    anthropic_base_url: Optional[str] = None
    anthropic_model: str = "claude-3-opus-20240229"

    # 火山方舟 (Volcengine)
    volcengine_api_key: str = ""
    volcengine_base_url: Optional[str] = None
    volcengine_model: str = "doubao-pro-32k"

    # 阿里云百炼 (Alibaba Cloud)
    aliyun_api_key: str = ""
    aliyun_base_url: Optional[str] = None
    aliyun_model: str = "qwen-max"

    # GLM (智谱 AI)
    glm_api_key: str = ""
    glm_base_url: Optional[str] = None
    glm_model: str = "glm-4"


class Settings(BaseSettings):
    """Application settings."""

    # Application
    app_name: str = "AFSA"
    app_version: str = "0.1.0"
    debug: bool = False
    environment: Literal["development", "staging", "production"] = "development"

    # API
    api_v1_prefix: str = "/api/v1"

    # Database
    database_url: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/afsa"
    database_pool_size: int = 10
    database_max_overflow: int = 20

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # NATS
    nats_url: str = "nats://localhost:4222"

    # LLM Provider
    llm_provider: Literal["openai", "anthropic", "volcengine", "aliyun", "glm"] = "openai"

    # OpenAI
    openai_api_key: str = ""
    openai_base_url: Optional[str] = None
    openai_model: str = "gpt-4-turbo-preview"

    # Anthropic
    anthropic_api_key: str = ""
    anthropic_base_url: Optional[str] = None
    anthropic_model: str = "claude-3-opus-20240229"

    # 火山方舟 (Volcengine)
    volcengine_api_key: str = ""
    volcengine_base_url: Optional[str] = None
    volcengine_model: str = "doubao-pro-32k"

    # 阿里云百炼 (Alibaba Cloud)
    aliyun_api_key: str = ""
    aliyun_base_url: Optional[str] = None
    aliyun_model: str = "qwen-max"

    # GLM (智谱 AI)
    glm_api_key: str = ""
    glm_base_url: Optional[str] = None
    glm_model: str = "glm-4"

    # Agent Framework
    agent_framework: Literal["langgraph", "crewai", "autogen"] = "langgraph"

    # JWT
    jwt_secret_key: str = "your-secret-key-change-in-production"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30

    # Sandbox
    sandbox_pool_size: int = 5
    sandbox_timeout_seconds: int = 60
    sandbox_type: Literal["local", "docker"] = "local"

    # Docker Sandbox
    docker_sandbox_image: str = "python:3.11-slim"
    docker_sandbox_memory_mb: int = 256
    docker_sandbox_cpu_limit: float = 1.0
    docker_sandbox_network_disabled: bool = True
    docker_sandbox_timeout_seconds: int = 60
    docker_sandbox_prewarm_pool: int = 2  # 预热容器数量

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()