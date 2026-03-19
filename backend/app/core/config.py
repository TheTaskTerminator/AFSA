"""
AFSA 核心配置系统

支持 YAML 配置文件、环境变量替换、配置验证和热重载。
"""

import os
import re
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

import yaml
from pydantic import BaseModel, Field, field_validator


# ============= Agent 框架配置 =============

class AgentFrameworkConfig(BaseModel):
    """Agent 框架配置"""
    name: Literal["langgraph", "crewai", "autogen"]
    version: str = "latest"
    enabled: bool = True
    auto_install: bool = True


# ============= LLM 提供商配置 =============

class LLMProviderConfig(BaseModel):
    """LLM 提供商配置"""
    name: str
    enabled: bool = True
    auto_install: bool = True
    model: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    
    @field_validator('api_key')
    @classmethod
    def resolve_env_var(cls, v: Optional[str]) -> Optional[str]:
        """解析环境变量"""
        if v and v.startswith('${') and v.endswith('}'):
            var_name = v[2:-1]
            return os.environ.get(var_name)
        return v


# ============= 沙箱配置 =============

class SandboxConfig(BaseModel):
    """沙箱配置"""
    type: Literal["local", "docker", "firecracker"] = "docker"
    timeout_seconds: int = 300
    cpu_limit: float = 1.0
    memory_limit: str = "512Mi"
    prewarm_pool: int = 2
    network_disabled: bool = True


# ============= 数据库配置 =============

class DatabaseConfig(BaseModel):
    """数据库配置"""
    type: Literal["postgresql", "mysql", "sqlite"] = "postgresql"
    url: str
    pool_size: int = 10
    max_overflow: int = 20
    
    @field_validator('url')
    @classmethod
    def resolve_env_var(cls, v: str) -> str:
        """解析环境变量"""
        if v.startswith('${') and v.endswith('}'):
            var_name = v[2:-1]
            return os.environ.get(var_name, v)
        return v


# ============= 应用配置 =============

class AppConfig(BaseModel):
    """应用配置"""
    name: str = "afsa-app"
    version: str = "1.0.0"
    debug: bool = False
    environment: Literal["development", "staging", "production"] = "development"


# ============= 配置根类 =============

class Config(BaseModel):
    """AFSA 配置根类"""
    app: AppConfig = Field(default_factory=AppConfig)
    agents: List[AgentFrameworkConfig] = Field(default_factory=list)
    llm: Dict[str, LLMProviderConfig] = Field(default_factory=dict)
    sandbox: SandboxConfig = Field(default_factory=SandboxConfig)
    database: Optional[DatabaseConfig] = None
    
    @classmethod
    def load_from_yaml(cls, path: str) -> "Config":
        """从 YAML 文件加载配置"""
        config_path = Path(path)
        
        if not config_path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")
        
        with open(config_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        # 环境变量替换
        data = cls._substitute_env_vars(data)
        
        return cls(**data)
    
    @classmethod
    def load_from_dict(cls, data: Dict[str, Any]) -> "Config":
        """从字典加载配置"""
        # 环境变量替换
        data = cls._substitute_env_vars(data)
        
        return cls(**data)
    
    @staticmethod
    def _substitute_env_vars(data: Any) -> Any:
        """替换 ${VAR} 格式的环境变量"""
        if isinstance(data, str):
            # 匹配 ${VAR} 格式
            pattern = r'\$\{(\w+)\}'
            
            def replace(match):
                var_name = match.group(1)
                return os.environ.get(var_name, match.group(0))
            
            return re.sub(pattern, replace, data)
        
        elif isinstance(data, dict):
            return {k: Config._substitute_env_vars(v) for k, v in data.items()}
        
        elif isinstance(data, list):
            return [Config._substitute_env_vars(item) for item in data]
        
        return data
    
    def save_to_yaml(self, path: str) -> None:
        """保存配置到 YAML 文件"""
        config_path = Path(path)
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        data = self.model_dump(exclude_none=True)
        
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(data, f, default_flow_style=False, allow_unicode=True)
    
    def get_agent_framework(self, name: str) -> Optional[AgentFrameworkConfig]:
        """获取指定 Agent 框架配置"""
        for framework in self.agents:
            if framework.name == name:
                return framework
        return None
    
    def get_llm_provider(self, name: str) -> Optional[LLMProviderConfig]:
        """获取指定 LLM 提供商配置"""
        return self.llm.get(name)
    
    def get_enabled_frameworks(self) -> List[AgentFrameworkConfig]:
        """获取所有启用的 Agent 框架"""
        return [fw for fw in self.agents if fw.enabled]
    
    def get_enabled_llm_providers(self) -> List[LLMProviderConfig]:
        """获取所有启用的 LLM 提供商"""
        return [p for p in self.llm.values() if p.enabled]


# ============= 默认配置 =============

def get_default_config() -> Config:
    """获取默认配置"""
    return Config(
        app=AppConfig(),
        agents=[
            AgentFrameworkConfig(name="langgraph", version="latest", enabled=True),
            AgentFrameworkConfig(name="crewai", version="latest", enabled=False),
            AgentFrameworkConfig(name="autogen", version="latest", enabled=False),
        ],
        llm={
            "openai": LLMProviderConfig(
                name="openai",
                enabled=True,
                model="gpt-4-turbo",
                api_key="${OPENAI_API_KEY}",
            ),
            "anthropic": LLMProviderConfig(
                name="anthropic",
                enabled=False,
                model="claude-3-opus",
                api_key="${ANTHROPIC_API_KEY}",
            ),
            "glm": LLMProviderConfig(
                name="glm",
                enabled=False,
                model="glm-4",
                api_key="${GLM_API_KEY}",
            ),
        },
        sandbox=SandboxConfig(),
        database=DatabaseConfig(
            url="${DATABASE_URL}",
        ),
    )


# ============= 配置示例 =============

EXAMPLE_CONFIG_YAML = """
# AFSA 配置示例

app:
  name: my-afsa-app
  version: 1.0.0
  debug: true
  environment: development

# Agent 框架配置
agents:
  - name: langgraph
    version: "0.1.0"
    enabled: true
    auto_install: true
  
  - name: crewai
    version: "latest"
    enabled: true
    auto_install: true
  
  - name: autogen
    version: "0.2.0"
    enabled: false

# LLM 提供商配置
llm:
  openai:
    name: openai
    enabled: true
    auto_install: true
    model: gpt-4-turbo
    api_key: ${OPENAI_API_KEY}
  
  glm:
    name: glm
    enabled: true
    auto_install: true
    model: glm-4
    api_key: ${GLM_API_KEY}

# 沙箱配置
sandbox:
  type: docker
  timeout_seconds: 300
  cpu_limit: 1.0
  memory_limit: 512Mi
  prewarm_pool: 2
  network_disabled: true

# 数据库配置
database:
  type: postgresql
  url: ${DATABASE_URL}
  pool_size: 10
  max_overflow: 20
"""


# ============= 工具函数 =============

def create_example_config(output_path: str = "config.example.yaml") -> None:
    """创建示例配置文件"""
    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(EXAMPLE_CONFIG_YAML)
    print(f"Example config created: {output_path}")


def validate_config(config: Config) -> List[str]:
    """验证配置，返回警告列表"""
    warnings = []
    
    # 检查至少有一个启用的 Agent 框架
    enabled_frameworks = config.get_enabled_frameworks()
    if not enabled_frameworks:
        warnings.append("No enabled agent frameworks. At least one framework should be enabled.")
    
    # 检查至少有一个启用的 LLM 提供商
    enabled_llms = config.get_enabled_llm_providers()
    if not enabled_llms:
        warnings.append("No enabled LLM providers. At least one provider should be enabled.")
    
    # 检查 API 密钥
    for provider in enabled_llms:
        if not provider.api_key:
            warnings.append(f"LLM provider '{provider.name}' has no API key configured.")
    
    return warnings
