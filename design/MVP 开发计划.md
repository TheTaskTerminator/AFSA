# AFSA MVP 开发计划

**版本**: 1.0  
**创建时间**: 2026-03-19  
**目标**: 2 周内完成 MVP，实现"用户说→界面变"的核心演示

---

## 一、MVP 核心目标

### 用户故事
```
作为一个用户，
我希望通过自然语言描述需求（如"加一个销售数据面板"），
能够看到 AI 团队自动开发并实时展示变更结果，
从而无需编写代码即可定制我的软件。
```

### 核心能力
1. **自然语言需求理解** - PM Agent 对话澄清
2. **代码自动生成** - 基于模板生成 CRUD
3. **沙箱验证** - Docker 沙箱执行验证
4. **实时反馈** - WebSocket 推送进度
5. **框架可插拔** - Agent 框架动态加载

---

## 二、技术架构

### 2.1 系统架构图

```
┌─────────────────────────────────────────────────────────┐
│                      前端 (React)                        │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │  对话界面   │  │  任务进度   │  │  预览区     │     │
│  └─────────────┘  └─────────────┘  └─────────────┘     │
└─────────────────────────────────────────────────────────┘
                            │ WebSocket
┌─────────────────────────────────────────────────────────┐
│                  后端 (FastAPI)                          │
│  ┌─────────────────────────────────────────────────┐   │
│  │              API Gateway                         │   │
│  └─────────────────────────────────────────────────┘   │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │ PM Agent    │  │ Architect   │  │ Dev Agents  │     │
│  │             │  │ Agent       │  │             │     │
│  └─────────────┘  └─────────────┘  └─────────────┘     │
│  ┌─────────────────────────────────────────────────┐   │
│  │           Framework Loader (动态加载)            │   │
│  └─────────────────────────────────────────────────┘   │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │  Config     │  │   Sandbox   │  │   Code      │     │
│  │  System     │  │   Runner    │  │  Generator  │     │
│  └─────────────┘  └─────────────┘  └─────────────┘     │
└─────────────────────────────────────────────────────────┘
                            │
┌─────────────────────────────────────────────────────────┐
│                   基础设施层                              │
│  PostgreSQL  │  Redis  │  NATS  │  Docker Sandbox      │
└─────────────────────────────────────────────────────────┘
```

### 2.2 核心模块依赖关系

```
config_system (配置系统)
    │
    ├─→ framework_loader (框架加载器)
    │       │
    │       ├─→ langgraph_adapter
    │       ├─→ crewai_adapter
    │       └─→ autogen_adapter
    │
    ├─→ llm_loader (LLM 提供商加载器)
    │       │
    │       ├─→ openai_provider
    │       ├─→ anthropic_provider
    │       └─→ glm_provider
    │
    └─→ agent_team (Agent 团队)
            │
            ├─→ pm_agent (PM Agent)
            ├─→ architect_agent (架构 Agent)
            └─→ dev_agents (开发 Agents)
                    │
                    ├─→ code_generator (代码生成器)
                    └─→ sandbox_runner (沙箱执行器)
```

---

## 三、核心功能详细设计

### 3.1 配置系统

#### 设计目标
- 支持 YAML 配置文件
- 支持环境变量覆盖
- 支持配置验证
- 支持热重载

#### 配置文件结构

```yaml
# config.yaml
app:
  name: my-afsa-app
  version: 1.0.0
  debug: true

# Agent 框架配置
agents:
  framework: crewai  # 可选：langgraph, crewai, autogen
  framework_version: "latest"  # 或具体版本号
  auto_install: true  # 启动时自动安装缺失框架
  
  # 可用框架列表
  available_frameworks:
    - name: langgraph
      version: "0.1.0"
      enabled: true
    - name: crewai
      version: "latest"
      enabled: true
    - name: autogen
      version: "0.2.0"
      enabled: false

# LLM 配置
llm:
  default_provider: openai
  
  providers:
    - name: openai
      enabled: true
      auto_install: true
      model: gpt-4-turbo
      api_key: ${OPENAI_API_KEY}
      
    - name: anthropic
      enabled: false
      model: claude-3-opus
      api_key: ${ANTHROPIC_API_KEY}
      
    - name: glm
      enabled: true
      auto_install: true
      model: glm-4
      api_key: ${GLM_API_KEY}

# 沙箱配置
sandbox:
  type: docker  # 可选：local, docker, firecracker
  timeout_seconds: 300
  resource_limits:
    cpu: "1.0"
    memory: "512Mi"
  prewarm_pool: 2

# 数据库配置
database:
  type: postgresql
  url: ${DATABASE_URL}
  pool_size: 10

# 多租户配置
tenant:
  enabled: false
  id: default
```

#### 配置类设计

```python
# app/core/config/config.py

from pydantic import BaseModel, Field
from typing import Optional, List, Literal
import yaml
import os

class AgentFrameworkConfig(BaseModel):
    name: Literal["langgraph", "crewai", "autogen"]
    version: str = "latest"
    enabled: bool = True
    auto_install: bool = True

class LLMProviderConfig(BaseModel):
    name: str
    enabled: bool = True
    auto_install: bool = True
    model: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None

class SandboxConfig(BaseModel):
    type: Literal["local", "docker", "firecracker"] = "docker"
    timeout_seconds: int = 300
    cpu_limit: float = 1.0
    memory_limit: str = "512Mi"
    prewarm_pool: int = 2

class AppConfig(BaseModel):
    name: str = "afsa-app"
    version: str = "1.0.0"
    debug: bool = False

class Config(BaseModel):
    """AFSA 配置根类"""
    app: AppConfig = AppConfig()
    agents: List[AgentFrameworkConfig] = []
    llm: Dict[str, LLMProviderConfig] = {}
    sandbox: SandboxConfig = SandboxConfig()
    database: Dict = {}
    
    @classmethod
    def load_from_yaml(cls, path: str) -> "Config":
        """从 YAML 文件加载配置"""
        with open(path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        
        # 环境变量替换
        data = cls._substitute_env_vars(data)
        
        return cls(**data)
    
    @staticmethod
    def _substitute_env_vars(data: dict) -> dict:
        """替换 ${VAR} 格式的环境变量"""
        import re
        
        def replace(match):
            var_name = match.group(1)
            return os.environ.get(var_name, match.group(0))
        
        def process_value(value):
            if isinstance(value, str):
                return re.sub(r'\$\{(\w+)\}', replace, value)
            elif isinstance(value, dict):
                return {k: process_value(v) for k, v in value.items()}
            elif isinstance(value, list):
                return [process_value(item) for item in value]
            return value
        
        return process_value(data)
```

---

### 3.2 框架加载器

#### 设计目标
- 运行时动态加载 Agent 框架
- 支持 PyPI 安装和 Git 源码
- 支持版本管理
- 支持缓存和增量更新

#### 核心接口

```python
# app/core/framework_loader.py

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, Type
import asyncio
import subprocess
import importlib
import sys
from pathlib import Path

class FrameworkLoader(ABC):
    """框架加载器基类"""
    
    @abstractmethod
    async def load(self, name: str, version: str = "latest") -> Any:
        """加载框架"""
        pass
    
    @abstractmethod
    async def install(self, name: str, version: str) -> None:
        """安装框架"""
        pass
    
    @abstractmethod
    async def is_installed(self, name: str) -> bool:
        """检查框架是否已安装"""
        pass

class PipFrameworkLoader(FrameworkLoader):
    """PyPI 框架加载器"""
    
    def __init__(self, frameworks_dir: Path):
        self.frameworks_dir = frameworks_dir
        self.frameworks_dir.mkdir(parents=True, exist_ok=True)
        self._cache: Dict[str, Any] = {}
    
    async def is_installed(self, name: str) -> bool:
        """检查框架是否已安装"""
        install_path = self.frameworks_dir / name
        return install_path.exists()
    
    async def install(self, name: str, version: str) -> None:
        """安装框架到独立目录"""
        install_path = self.frameworks_dir / name
        
        # 构建 pip 命令
        cmd = [
            sys.executable, "-m", "pip", "install",
            "--target", str(install_path),
            "--quiet",
            "--upgrade",
        ]
        
        if version == "latest":
            cmd.append(name)
        else:
            cmd.append(f"{name}=={version}")
        
        # 执行安装
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            raise FrameworkInstallError(f"Failed to install {name}: {stderr.decode()}")
    
    async def load(self, name: str, version: str = "latest") -> Any:
        """加载框架"""
        cache_key = f"{name}@{version}"
        
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # 检查是否已安装
        if not await self.is_installed(name):
            await self.install(name, version)
        
        # 添加到 sys.path
        install_path = self.frameworks_dir / name
        if str(install_path) not in sys.path:
            sys.path.insert(0, str(install_path))
        
        # 动态导入
        module_name = self._get_module_name(name)
        try:
            module = importlib.import_module(module_name)
        except ImportError as e:
            raise FrameworkLoadError(f"Failed to import {module_name}: {e}")
        
        self._cache[cache_key] = module
        return module
    
    def _get_module_name(self, framework: str) -> str:
        """获取框架模块名"""
        mapping = {
            "langgraph": "langgraph.graph",
            "crewai": "crewai",
            "autogen": "autogen",
        }
        return mapping.get(framework, framework)

class GitFrameworkLoader(FrameworkLoader):
    """Git 源码框架加载器"""
    
    FRAMEWORK_REPOS = {
        "langgraph": "https://github.com/langchain-ai/langgraph.git",
        "crewai": "https://github.com/jeremyjordan/crewai.git",
        "autogen": "https://github.com/microsoft/autogen.git",
    }
    
    def __init__(self, frameworks_dir: Path):
        self.frameworks_dir = frameworks_dir
    
    async def load(self, name: str, ref: str = "main") -> Any:
        """从 Git 克隆并加载"""
        if name not in self.FRAMEWORK_REPOS:
            raise FrameworkNotFoundError(f"Unknown framework: {name}")
        
        repo_url = self.FRAMEWORK_REPOS[name]
        clone_path = self.frameworks_dir / name
        
        # Git clone 或 pull
        if not clone_path.exists():
            await self._clone(repo_url, clone_path)
        else:
            await self._pull(clone_path)
        
        # Checkout 指定分支/标签
        if ref != "main":
            await self._checkout(clone_path, ref)
        
        # 安装依赖
        await self._install_deps(clone_path)
        
        # 导入模块
        sys.path.insert(0, str(clone_path))
        module_name = self._get_module_name(name)
        return importlib.import_module(module_name)
    
    async def _clone(self, url: str, path: Path) -> None:
        """Git clone"""
        cmd = ["git", "clone", "--depth", "1", url, str(path)]
        process = await asyncio.create_subprocess_exec(*cmd)
        await process.communicate()
    
    async def _pull(self, path: Path) -> None:
        """Git pull"""
        cmd = ["git", "pull"]
        process = await asyncio.create_subprocess_exec(*cmd, cwd=path)
        await process.communicate()
    
    async def _checkout(self, path: Path, ref: str) -> None:
        """Git checkout"""
        cmd = ["git", "checkout", ref]
        process = await asyncio.create_subprocess_exec(*cmd, cwd=path)
        await process.communicate()
    
    async def _install_deps(self, path: Path) -> None:
        """安装依赖"""
        requirements = path / "requirements.txt"
        if requirements.exists():
            cmd = [sys.executable, "-m", "pip", "install", "-r", str(requirements)]
            process = await asyncio.create_subprocess_exec(*cmd)
            await process.communicate()
```

---

### 3.3 PM Agent

#### 设计目标
- 自然语言需求理解
- 多轮对话澄清
- 生成结构化任务卡

#### 工作流程

```
用户输入
    │
    ↓
┌─────────────────┐
│  意图识别       │ → 识别需求类型 (feature/bugfix/config)
└─────────────────┘
    │
    ↓
┌─────────────────┐
│  需求澄清对话   │ → 多轮对话，收集缺失信息
└─────────────────┘
    │
    ↓
┌─────────────────┐
│  任务卡生成     │ → 生成结构化 TaskCard
└─────────────────┘
    │
    ↓
输出 TaskCard
```

#### 任务卡结构

```python
# app/agents/base.py

from enum import Enum
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from datetime import datetime
import uuid

class TaskType(str, Enum):
    FEATURE = "feature"
    BUGFIX = "bugfix"
    CONFIG = "config"
    REFACTOR = "refactor"

class TaskPriority(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"

class TaskStatus(str, Enum):
    DRAFT = "draft"
    PENDING = "pending"
    APPROVED = "approved"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class RequirementSpec(BaseModel):
    """需求规格"""
    type: str  # model, api, ui, workflow
    name: str
    spec: Dict[str, Any]
    constraints: Dict[str, Any] = {}

class TaskCard(BaseModel):
    """任务卡"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: TaskType
    priority: TaskPriority = TaskPriority.MEDIUM
    description: str
    requirements: List[RequirementSpec] = []
    
    # 约束
    target_zone: str = "mutable"
    timeout_seconds: int = 300
    requires_approval: bool = True
    
    # 生命周期
    status: TaskStatus = TaskStatus.DRAFT
    created_at: datetime = Field(default_factory=datetime.utcnow)
    created_by: str = "user"
    
    # 结果
    result: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    
    # 元数据
    session_id: Optional[str] = None
    protocol_version: str = "1.0"
```

---

### 3.4 代码生成器

#### 设计目标
- 基于模板生成代码
- 支持多种目标框架
- 支持增量更新

#### 模板结构

```
templates/
├── python/
│   ├── fastapi/
│   │   ├── model.py.j2
│   │   ├── api.py.j2
│   │   ├── schema.py.j2
│   │   └── repository.py.j2
│   └── django/
│       ├── models.py.j2
│       └── views.py.j2
├── typescript/
│   ├── react/
│   │   ├── component.tsx.j2
│   │   └── hook.ts.j2
│   └── nestjs/
│       ├── controller.ts.j2
│       └── service.ts.j2
└── config/
    ├── docker-compose.yml.j2
    └── Dockerfile.j2
```

#### 生成器接口

```python
# app/generation/base.py

from abc import ABC, abstractmethod
from typing import List, Dict, Any
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

class GeneratedFile(BaseModel):
    """生成的文件"""
    path: str
    content: str
    overwrite: bool = False

class CodeGenerator(ABC):
    """代码生成器基类"""
    
    def __init__(self, template_dir: Path):
        self.template_dir = template_dir
        self.env = Environment(loader=FileSystemLoader(template_dir))
    
    @abstractmethod
    def generate_model(self, model_def: Dict) -> List[GeneratedFile]:
        """生成模型代码"""
        pass
    
    @abstractmethod
    def generate_api(self, api_def: Dict) -> List[GeneratedFile]:
        """生成 API 代码"""
        pass

class FastAPICodeGenerator(CodeGenerator):
    """FastAPI 代码生成器"""
    
    def generate_model(self, model_def: Dict) -> List[GeneratedFile]:
        """生成 FastAPI 模型代码"""
        template = self.env.get_template("python/fastapi/model.py.j2")
        
        content = template.render(
            model_name=model_def["name"],
            fields=model_def["fields"],
            table_name=model_def.get("table_name"),
        )
        
        return [GeneratedFile(
            path=f"app/models/{model_def['name'].lower()}.py",
            content=content,
        )]
    
    def generate_api(self, api_def: Dict) -> List[GeneratedFile]:
        """生成 FastAPI API 代码"""
        template = self.env.get_template("python/fastapi/api.py.j2")
        
        content = template.render(
            model_name=api_def["model"],
            endpoints=api_def.get("endpoints", []),
        )
        
        return [GeneratedFile(
            path=f"app/api/{api_def['model'].lower()}_router.py",
            content=content,
        )]
```

---

### 3.5 沙箱验证器

#### 设计目标
- Docker 隔离执行
- 资源限制
- 超时控制
- 安全扫描

#### 沙箱接口

```python
# app/sandbox/base.py

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import asyncio

class SandboxResult(BaseModel):
    """沙箱执行结果"""
    success: bool
    output: str
    error: Optional[str] = None
    exit_code: int = 0
    execution_time: float = 0.0

class SandboxInstance(ABC):
    """沙箱实例基类"""
    
    @abstractmethod
    async def execute(self, code: str, timeout: int = 60) -> SandboxResult:
        """执行代码"""
        pass
    
    @abstractmethod
    async def cleanup(self) -> None:
        """清理沙箱"""
        pass

class DockerSandbox(SandboxInstance):
    """Docker 沙箱"""
    
    def __init__(self, config: SandboxConfig):
        self.config = config
        self.container = None
    
    async def execute(self, code: str, timeout: int = 60) -> SandboxResult:
        """在 Docker 容器中执行代码"""
        import docker
        
        client = docker.from_env()
        
        # 创建容器
        self.container = client.containers.run(
            self.config.image,
            command=["python", "-c", code],
            detach=True,
            mem_limit=self.config.memory_limit,
            nano_cpus=int(self.config.cpu_limit * 1e9),
            network_disabled=self.config.network_disabled,
        )
        
        # 等待执行完成
        try:
            result = self.container.wait(timeout=timeout)
            logs = self.container.logs().decode()
            
            return SandboxResult(
                success=result["StatusCode"] == 0,
                output=logs,
                exit_code=result["StatusCode"],
            )
        except asyncio.TimeoutError:
            self.container.kill()
            return SandboxResult(
                success=False,
                output="",
                error="Execution timeout",
            )
        finally:
            await self.cleanup()
    
    async def cleanup(self) -> None:
        """清理容器"""
        if self.container:
            self.container.remove(force=True)
```

---

## 四、开发任务分解

### Iteration 1 (Day 1-3): 基础设施

| 任务 | 负责人 | 预计时间 | 状态 |
|------|--------|---------|------|
| 配置系统实现 | 后端工程师 | 1 天 | 待开始 |
| 框架加载器实现 | 后端工程师 | 1 天 | 待开始 |
| LLM 加载器实现 | AI 工程师 | 0.5 天 | 待开始 |
| 项目脚手架 | 后端工程师 | 0.5 天 | 待开始 |
| 测试框架搭建 | 测试工程师 | 0.5 天 | 待开始 |

### Iteration 2 (Day 4-7): 核心 Agent

| 任务 | 负责人 | 预计时间 | 状态 |
|------|--------|---------|------|
| PM Agent 实现 | AI 工程师 | 2 天 | 待开始 |
| 代码生成器实现 | 后端工程师 | 1.5 天 | 待开始 |
| 沙箱验证器实现 | 后端工程师 | 1.5 天 | 待开始 |
| CLI 工具实现 | 后端工程师 | 1 天 | 待开始 |

### Iteration 3 (Day 8-10): 前端界面

| 任务 | 负责人 | 预计时间 | 状态 |
|------|--------|---------|------|
| 对话界面实现 | 前端工程师 | 2 天 | 待开始 |
| 任务管理界面 | 前端工程师 | 1 天 | 待开始 |
| WebSocket 集成 | 全栈工程师 | 1 天 | 待开始 |

### Iteration 4 (Day 11-14): 集成测试

| 任务 | 负责人 | 预计时间 | 状态 |
|------|--------|---------|------|
| 端到端测试 | 测试工程师 | 2 天 | 待开始 |
| 性能优化 | 全栈工程师 | 1 天 | 待开始 |
| 文档编写 | 技术文档 | 1 天 | 待开始 |

---

## 五、测试策略

### 5.1 测试金字塔

```
           ┌─────────────┐
           │   E2E 测试    │  10%
           └─────────────┘
      ┌─────────────────────┐
      │     集成测试        │  30%
      └─────────────────────┘
 ┌─────────────────────────────┐
 │       单元测试              │  60%
 └─────────────────────────────┘
```

### 5.2 测试覆盖率目标

| 模块 | 覆盖率目标 |
|------|-----------|
| 核心业务逻辑 | ≥ 90% |
| API 接口 | 100% |
| UI 组件 | ≥ 80% |
| 配置规则 | 100% |

---

## 六、质量标准

### 6.1 代码质量

- [ ] 所有代码通过 mypy 类型检查
- [ ] 所有代码通过 ruff lint 检查
- [ ] 所有公共函数有 docstring
- [ ] 所有配置项有默认值

### 6.2 性能要求

- [ ] API 响应时间 < 200ms (P95)
- [ ] 代码生成时间 < 30s
- [ ] 沙箱启动时间 < 5s
- [ ] WebSocket 延迟 < 100ms

### 6.3 安全要求

- [ ] 所有用户输入验证
- [ ] 沙箱网络隔离
- [ ] API 密钥加密存储
- [ ] 审计日志完整记录

---

**文档版本**: 1.0  
**最后更新**: 2026-03-19  
**下次评审**: 完成 Iteration 1 后
