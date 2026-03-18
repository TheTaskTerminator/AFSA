"""
Tests for AFSA core configuration system.
"""

import os
import tempfile
from pathlib import Path

import pytest

from app.core.config import (
    Config,
    AppConfig,
    AgentFrameworkConfig,
    LLMProviderConfig,
    SandboxConfig,
    DatabaseConfig,
    get_default_config,
    validate_config,
)


class TestAgentFrameworkConfig:
    """测试 Agent 框架配置"""
    
    def test_valid_config(self):
        """测试有效配置"""
        config = AgentFrameworkConfig(name="langgraph")
        assert config.name == "langgraph"
        assert config.version == "latest"
        assert config.enabled is True
        assert config.auto_install is True
    
    def test_custom_version(self):
        """测试自定义版本"""
        config = AgentFrameworkConfig(
            name="crewai",
            version="0.50.0",
            enabled=False,
        )
        assert config.name == "crewai"
        assert config.version == "0.50.0"
        assert config.enabled is False
    
    def test_invalid_framework_name(self):
        """测试无效的框架名称"""
        with pytest.raises(ValueError):
            AgentFrameworkConfig(name="invalid_framework")


class TestLLMProviderConfig:
    """测试 LLM 提供商配置"""
    
    def test_valid_config(self):
        """测试有效配置"""
        config = LLMProviderConfig(
            name="openai",
            model="gpt-4",
        )
        assert config.name == "openai"
        assert config.model == "gpt-4"
        assert config.enabled is True
    
    def test_env_var_resolution(self):
        """测试环境变量解析"""
        os.environ["TEST_API_KEY"] = "test_key_123"
        
        config = LLMProviderConfig(
            name="openai",
            model="gpt-4",
            api_key="${TEST_API_KEY}",
        )
        assert config.api_key == "test_key_123"
    
    def test_env_var_not_set(self):
        """测试环境变量未设置"""
        config = LLMProviderConfig(
            name="openai",
            model="gpt-4",
            api_key="${NON_EXISTENT_VAR}",
        )
        assert config.api_key is None


class TestSandboxConfig:
    """测试沙箱配置"""
    
    def test_default_config(self):
        """测试默认配置"""
        config = SandboxConfig()
        assert config.type == "docker"
        assert config.timeout_seconds == 300
        assert config.cpu_limit == 1.0
        assert config.memory_limit == "512Mi"
        assert config.prewarm_pool == 2
    
    def test_custom_config(self):
        """测试自定义配置"""
        config = SandboxConfig(
            type="local",
            timeout_seconds=600,
            cpu_limit=2.0,
            memory_limit="1Gi",
        )
        assert config.type == "local"
        assert config.timeout_seconds == 600


class TestDatabaseConfig:
    """测试数据库配置"""
    
    def test_env_var_resolution(self):
        """测试环境变量解析"""
        os.environ["TEST_DB_URL"] = "postgresql://user:pass@localhost/db"
        
        config = DatabaseConfig(url="${TEST_DB_URL}")
        assert config.url == "postgresql://user:pass@localhost/db"


class TestConfig:
    """测试配置根类"""
    
    def test_default_config(self):
        """测试默认配置"""
        config = Config()
        assert config.app.name == "afsa-app"
        assert config.app.version == "1.0.0"
    
    def test_load_from_dict(self):
        """测试从字典加载配置"""
        data = {
            "app": {
                "name": "test-app",
                "version": "2.0.0",
                "debug": True,
            },
            "agents": [
                {"name": "langgraph", "enabled": True},
                {"name": "crewai", "enabled": False},
            ],
            "llm": {
                "openai": {
                    "name": "openai",
                    "enabled": True,
                    "model": "gpt-4",
                }
            },
            "sandbox": {
                "type": "docker",
                "timeout_seconds": 300,
            },
        }
        
        config = Config.load_from_dict(data)
        
        assert config.app.name == "test-app"
        assert config.app.version == "2.0.0"
        assert config.app.debug is True
        assert len(config.agents) == 2
        assert "openai" in config.llm
    
    def test_load_from_yaml(self):
        """测试从 YAML 文件加载配置"""
        yaml_content = """
app:
  name: yaml-test-app
  version: 3.0.0
  debug: true

agents:
  - name: langgraph
    version: "0.1.0"
    enabled: true

llm:
  openai:
    name: openai
    enabled: true
    model: gpt-4-turbo

sandbox:
  type: docker
  timeout_seconds: 300
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(yaml_content)
            temp_path = f.name
        
        try:
            config = Config.load_from_yaml(temp_path)
            
            assert config.app.name == "yaml-test-app"
            assert config.app.version == "3.0.0"
            assert len(config.agents) == 1
            assert config.agents[0].name == "langgraph"
        finally:
            os.unlink(temp_path)
    
    def test_env_var_substitution(self):
        """测试环境变量替换"""
        os.environ["TEST_APP_NAME"] = "env-test-app"
        
        data = {
            "app": {
                "name": "${TEST_APP_NAME}",
            },
            "sandbox": {},
        }
        
        config = Config.load_from_dict(data)
        assert config.app.name == "env-test-app"
    
    def test_get_agent_framework(self):
        """测试获取 Agent 框架配置"""
        config = Config(
            agents=[
                AgentFrameworkConfig(name="langgraph", enabled=True),
                AgentFrameworkConfig(name="crewai", enabled=False),
            ],
            sandbox=SandboxConfig(),
        )
        
        framework = config.get_agent_framework("langgraph")
        assert framework is not None
        assert framework.enabled is True
        
        framework = config.get_agent_framework("crewai")
        assert framework is not None
        assert framework.enabled is False
        
        framework = config.get_agent_framework("nonexistent")
        assert framework is None
    
    def test_get_enabled_frameworks(self):
        """测试获取启用的框架"""
        config = Config(
            agents=[
                AgentFrameworkConfig(name="langgraph", enabled=True),
                AgentFrameworkConfig(name="crewai", enabled=False),
                AgentFrameworkConfig(name="autogen", enabled=True),
            ],
            sandbox=SandboxConfig(),
        )
        
        enabled = config.get_enabled_frameworks()
        assert len(enabled) == 2
        assert all(fw.enabled for fw in enabled)
    
    def test_save_to_yaml(self):
        """测试保存配置到 YAML"""
        config = Config(
            app=AppConfig(name="save-test", version="1.0.0"),
            agents=[AgentFrameworkConfig(name="langgraph")],
            llm={
                "openai": LLMProviderConfig(name="openai", model="gpt-4"),
            },
            sandbox=SandboxConfig(),
        )
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            temp_path = f.name
        
        try:
            config.save_to_yaml(temp_path)
            
            # 重新加载验证
            loaded_config = Config.load_from_yaml(temp_path)
            assert loaded_config.app.name == "save-test"
        finally:
            os.unlink(temp_path)


class TestGetDefaultConfig:
    """测试获取默认配置"""
    
    def test_default_config_structure(self):
        """测试默认配置结构"""
        config = get_default_config()
        
        assert config.app is not None
        assert len(config.agents) == 3
        assert len(config.llm) == 3
        assert config.sandbox is not None
    
    def test_default_frameworks(self):
        """测试默认框架配置"""
        config = get_default_config()
        
        framework_names = [fw.name for fw in config.agents]
        assert "langgraph" in framework_names
        assert "crewai" in framework_names
        assert "autogen" in framework_names


class TestValidateConfig:
    """测试配置验证"""
    
    def test_valid_config(self):
        """测试有效配置无警告"""
        config = Config(
            agents=[AgentFrameworkConfig(name="langgraph", enabled=True)],
            llm={
                "openai": LLMProviderConfig(
                    name="openai",
                    enabled=True,
                    model="gpt-4",
                    api_key="test_key",
                ),
            },
            sandbox=SandboxConfig(),
        )
        
        warnings = validate_config(config)
        assert len(warnings) == 0
    
    def test_no_enabled_frameworks(self):
        """测试无启用框架的警告"""
        config = Config(
            agents=[AgentFrameworkConfig(name="langgraph", enabled=False)],
            llm={
                "openai": LLMProviderConfig(name="openai", enabled=True, model="gpt-4", api_key="key"),
            },
            sandbox=SandboxConfig(),
        )
        
        warnings = validate_config(config)
        assert any("No enabled agent frameworks" in w for w in warnings)
    
    def test_no_enabled_llm(self):
        """测试无启用 LLM 的警告"""
        config = Config(
            agents=[AgentFrameworkConfig(name="langgraph", enabled=True)],
            llm={
                "openai": LLMProviderConfig(name="openai", enabled=False, model="gpt-4"),
            },
            sandbox=SandboxConfig(),
        )
        
        warnings = validate_config(config)
        assert any("No enabled LLM providers" in w for w in warnings)
    
    def test_missing_api_key(self):
        """测试缺少 API 密钥的警告"""
        config = Config(
            agents=[AgentFrameworkConfig(name="langgraph", enabled=True)],
            llm={
                "openai": LLMProviderConfig(name="openai", enabled=True, model="gpt-4"),
            },
            sandbox=SandboxConfig(),
        )
        
        warnings = validate_config(config)
        assert any("no API key configured" in w for w in warnings)


class TestCreateExampleConfig:
    """测试创建示例配置"""
    
    def test_create_example(self):
        """测试创建示例配置文件"""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / "config.example.yaml"
            create_example_config(str(output_path))
            
            assert output_path.exists()
            
            # 验证可以加载
            config = Config.load_from_yaml(str(output_path))
            assert config.app is not None
