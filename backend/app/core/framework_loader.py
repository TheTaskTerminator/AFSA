"""
AFSA 框架加载器

支持运行时动态加载 Agent 框架和 LLM 提供商。
- PipFrameworkLoader: 从 PyPI 安装和加载
- GitFrameworkLoader: 从 Git 源码安装和加载
"""

import asyncio
import importlib
import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Optional

from app.core.config import AgentFrameworkConfig, LLMProviderConfig


# ============= 异常类 =============

class FrameworkError(Exception):
    """框架加载基础异常"""
    pass


class FrameworkNotFoundError(FrameworkError):
    """框架未找到"""
    pass


class FrameworkInstallError(FrameworkError):
    """框架安装失败"""
    pass


class FrameworkLoadError(FrameworkError):
    """框架加载失败"""
    pass


# ============= 框架加载器基类 =============

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


# ============= PyPI 框架加载器 =============

class PipFrameworkLoader(FrameworkLoader):
    """PyPI 框架加载器
    
    从 PyPI 安装框架到独立目录，支持版本管理和缓存。
    """
    
    # 框架名称到包名的映射
    FRAMEWORK_PACKAGES = {
        "langgraph": "langgraph",
        "crewai": "crewai",
        "autogen": "pyautogen",
    }
    
    # 框架名称到模块名的映射
    FRAMEWORK_MODULES = {
        "langgraph": "langgraph.graph",
        "crewai": "crewai",
        "autogen": "autogen",
    }
    
    def __init__(self, frameworks_dir: Optional[Path] = None):
        """初始化加载器
        
        Args:
            frameworks_dir: 框架安装目录，默认为 ./frameworks
        """
        if frameworks_dir is None:
            frameworks_dir = Path.cwd() / "frameworks"
        
        self.frameworks_dir = frameworks_dir
        self.frameworks_dir.mkdir(parents=True, exist_ok=True)
        
        self._cache: Dict[str, Any] = {}
        self._lock = asyncio.Lock()
    
    async def is_installed(self, name: str) -> bool:
        """检查框架是否已安装
        
        Args:
            name: 框架名称
            
        Returns:
            True 如果已安装
        """
        install_path = self.frameworks_dir / name
        return install_path.exists() and (install_path / ".installed").exists()
    
    async def install(self, name: str, version: str = "latest") -> None:
        """安装框架到独立目录
        
        Args:
            name: 框架名称
            version: 版本号，"latest" 表示最新版本
            
        Raises:
            FrameworkInstallError: 安装失败
        """
        if name not in self.FRAMEWORK_PACKAGES:
            raise FrameworkNotFoundError(f"Unknown framework: {name}")
        
        package_name = self.FRAMEWORK_PACKAGES[name]
        install_path = self.frameworks_dir / name
        
        async with self._lock:
            # 检查是否已安装
            if await self.is_installed(name):
                return
            
            # 构建 pip 命令
            cmd = [
                sys.executable, "-m", "pip", "install",
                "--target", str(install_path),
                "--quiet",
                "--upgrade",
                "--no-cache-dir",
            ]
            
            if version == "latest":
                cmd.append(package_name)
            else:
                cmd.append(f"{package_name}=={version}")
            
            # 执行安装
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                error_msg = stderr.decode() if stderr else "Unknown error"
                raise FrameworkInstallError(
                    f"Failed to install {name} (version={version}): {error_msg}"
                )
            
            # 创建安装标记文件
            (install_path / ".installed").write_text(f"version={version}\n")
    
    async def load(self, name: str, version: str = "latest") -> Any:
        """加载框架
        
        如果框架未安装，会自动安装。
        
        Args:
            name: 框架名称
            version: 版本号
            
        Returns:
            加载的框架模块
            
        Raises:
            FrameworkLoadError: 加载失败
        """
        cache_key = f"{name}@{version}"
        
        # 检查缓存
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        async with self._lock:
            # 检查是否已安装
            if not await self.is_installed(name):
                await self.install(name, version)
            
            # 添加到 sys.path
            install_path = self.frameworks_dir / name
            install_path_str = str(install_path)
            
            if install_path_str not in sys.path:
                sys.path.insert(0, install_path_str)
            
            # 动态导入
            module_name = self.FRAMEWORK_MODULES.get(name, name)
            
            try:
                # 清除可能的缓存
                if module_name in sys.modules:
                    del sys.modules[module_name]
                
                module = importlib.import_module(module_name)
            except ImportError as e:
                raise FrameworkLoadError(
                    f"Failed to import {module_name}: {e}"
                )
            
            self._cache[cache_key] = module
            return module
    
    async def uninstall(self, name: str) -> None:
        """卸载框架
        
        Args:
            name: 框架名称
        """
        install_path = self.frameworks_dir / name
        
        async with self._lock:
            if install_path.exists():
                import shutil
                shutil.rmtree(install_path)
            
            # 清除缓存
            keys_to_remove = [k for k in self._cache if k.startswith(f"{name}@")]
            for key in keys_to_remove:
                del self._cache[key]
    
    async def list_installed(self) -> Dict[str, str]:
        """列出已安装的框架
        
        Returns:
            框架名称到版本的映射
        """
        installed = {}
        
        for framework_dir in self.frameworks_dir.iterdir():
            if framework_dir.is_dir() and (framework_dir / ".installed").exists():
                installed_file = framework_dir / ".installed"
                content = installed_file.read_text()
                
                version = "unknown"
                for line in content.splitlines():
                    if line.startswith("version="):
                        version = line.split("=", 1)[1]
                        break
                
                installed[framework_dir.name] = version
        
        return installed


# ============= Git 框架加载器 =============

class GitFrameworkLoader(FrameworkLoader):
    """Git 源码框架加载器
    
    从 Git 仓库克隆框架源码并安装。
    """
    
    # 框架名称到 Git 仓库的映射
    FRAMEWORK_REPOS = {
        "langgraph": "https://github.com/langchain-ai/langgraph.git",
        "crewai": "https://github.com/jeremyjordan/crewai.git",
        "autogen": "https://github.com/microsoft/autogen.git",
    }
    
    def __init__(self, frameworks_dir: Optional[Path] = None):
        """初始化加载器
        
        Args:
            frameworks_dir: 框架安装目录
        """
        if frameworks_dir is None:
            frameworks_dir = Path.cwd() / "frameworks"
        
        self.frameworks_dir = frameworks_dir
        self.frameworks_dir.mkdir(parents=True, exist_ok=True)
        
        self._cache: Dict[str, Any] = {}
        self._lock = asyncio.Lock()
    
    async def is_installed(self, name: str) -> bool:
        """检查框架是否已安装"""
        install_path = self.frameworks_dir / name
        return install_path.exists() and (install_path / ".git").exists()
    
    async def install(self, name: str, ref: str = "main") -> None:
        """从 Git 克隆框架
        
        Args:
            name: 框架名称
            ref: Git 分支/标签/commit
            
        Raises:
            FrameworkNotFoundError: 框架不存在
            FrameworkInstallError: 安装失败
        """
        if name not in self.FRAMEWORK_REPOS:
            raise FrameworkNotFoundError(f"Unknown framework: {name}")
        
        repo_url = self.FRAMEWORK_REPOS[name]
        clone_path = self.frameworks_dir / name
        
        async with self._lock:
            if clone_path.exists():
                # Pull 最新代码
                await self._pull(clone_path)
            else:
                # Clone 仓库
                await self._clone(repo_url, clone_path)
            
            # Checkout 指定 ref
            if ref != "main":
                await self._checkout(clone_path, ref)
            
            # 安装依赖
            await self._install_deps(clone_path)
            
            # 创建安装标记
            (clone_path / ".installed").write_text(f"ref={ref}\nsource=git\n")
    
    async def _clone(self, url: str, path: Path) -> None:
        """Git clone"""
        cmd = ["git", "clone", "--depth", "1", url, str(path)]
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            raise FrameworkInstallError(f"Git clone failed: {stderr.decode()}")
    
    async def _pull(self, path: Path) -> None:
        """Git pull"""
        cmd = ["git", "pull"]
        process = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            raise FrameworkInstallError(f"Git pull failed: {stderr.decode()}")
    
    async def _checkout(self, path: Path, ref: str) -> None:
        """Git checkout"""
        cmd = ["git", "fetch", "--tags"]
        process = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        await process.communicate()
        
        cmd = ["git", "checkout", ref]
        process = await asyncio.create_subprocess_exec(
            *cmd,
            cwd=path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        
        if process.returncode != 0:
            raise FrameworkInstallError(f"Git checkout failed: {stderr.decode()}")
    
    async def _install_deps(self, path: Path) -> None:
        """安装依赖"""
        requirements_files = [
            path / "requirements.txt",
            path / "pyproject.toml",
        ]
        
        for req_file in requirements_files:
            if req_file.exists():
                cmd = [
                    sys.executable, "-m", "pip", "install",
                    "-r", str(req_file),
                    "--quiet",
                ]
                process = await asyncio.create_subprocess_exec(*cmd)
                await process.communicate()
    
    async def load(self, name: str, ref: str = "main") -> Any:
        """加载框架"""
        cache_key = f"{name}@{ref}"
        
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        async with self._lock:
            if not await self.is_installed(name):
                await self.install(name, ref)
            
            # 添加到 sys.path
            clone_path = self.frameworks_dir / name
            if str(clone_path) not in sys.path:
                sys.path.insert(0, str(clone_path))
            
            # 动态导入
            module_name = f"{name}"
            
            try:
                if module_name in sys.modules:
                    del sys.modules[module_name]
                
                module = importlib.import_module(module_name)
            except ImportError as e:
                raise FrameworkLoadError(f"Failed to import {module_name}: {e}")
            
            self._cache[cache_key] = module
            return module


# ============= LLM 提供商加载器 =============

class LLMProviderLoader:
    """LLM 提供商加载器
    
    动态加载 LLM 提供商 SDK。
    """
    
    # 提供商到包名的映射
    PROVIDER_PACKAGES = {
        "openai": "langchain-openai",
        "anthropic": "langchain-anthropic",
        "glm": "zhipuai",
        "volcengine": "volcengine-python-sdk",
        "aliyun": "dashscope",
    }
    
    # 提供商到模块名的映射
    PROVIDER_MODULES = {
        "openai": "langchain_openai",
        "anthropic": "langchain_anthropic",
        "glm": "zhipuai",
        "volcengine": "volcengine",
        "aliyun": "dashscope",
    }
    
    def __init__(self, providers_dir: Optional[Path] = None):
        """初始化加载器
        
        Args:
            providers_dir: 提供商 SDK 安装目录
        """
        if providers_dir is None:
            providers_dir = Path.cwd() / "llm_providers"
        
        self.providers_dir = providers_dir
        self.providers_dir.mkdir(parents=True, exist_ok=True)
        
        self._cache: Dict[str, Any] = {}
        self._lock = asyncio.Lock()
    
    async def is_installed(self, name: str) -> bool:
        """检查提供商是否已安装"""
        install_path = self.providers_dir / name
        return install_path.exists() and (install_path / ".installed").exists()
    
    async def install(self, name: str) -> None:
        """安装提供商 SDK"""
        if name not in self.PROVIDER_PACKAGES:
            raise FrameworkNotFoundError(f"Unknown LLM provider: {name}")
        
        package_name = self.PROVIDER_PACKAGES[name]
        install_path = self.providers_dir / name
        
        async with self._lock:
            if await self.is_installed(name):
                return
            
            cmd = [
                sys.executable, "-m", "pip", "install",
                "--target", str(install_path),
                "--quiet",
                "--upgrade",
                package_name,
            ]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                raise FrameworkInstallError(
                    f"Failed to install {name}: {stderr.decode()}"
                )
            
            (install_path / ".installed").write_text(f"package={package_name}\n")
    
    async def load(self, name: str) -> Any:
        """加载提供商 SDK"""
        if name in self._cache:
            return self._cache[name]
        
        async with self._lock:
            if not await self.is_installed(name):
                await self.install(name)
            
            # 添加到 sys.path
            install_path = self.providers_dir / name
            if str(install_path) not in sys.path:
                sys.path.insert(0, str(install_path))
            
            # 动态导入
            module_name = self.PROVIDER_MODULES.get(name, name)
            
            try:
                if module_name in sys.modules:
                    del sys.modules[module_name]
                
                module = importlib.import_module(module_name)
            except ImportError as e:
                raise FrameworkLoadError(f"Failed to import {module_name}: {e}")
            
            self._cache[name] = module
            return module


# ============= 工厂函数 =============

def get_framework_loader(loader_type: str = "pip", frameworks_dir: Optional[Path] = None) -> FrameworkLoader:
    """获取框架加载器实例
    
    Args:
        loader_type: 加载器类型 ("pip" 或 "git")
        frameworks_dir: 框架安装目录
        
    Returns:
        框架加载器实例
    """
    if loader_type == "pip":
        return PipFrameworkLoader(frameworks_dir)
    elif loader_type == "git":
        return GitFrameworkLoader(frameworks_dir)
    else:
        raise ValueError(f"Unknown loader type: {loader_type}")


def get_llm_provider_loader(providers_dir: Optional[Path] = None) -> LLMProviderLoader:
    """获取 LLM 提供商加载器实例
    
    Args:
        providers_dir: 提供商安装目录
        
    Returns:
        LLM 提供商加载器实例
    """
    return LLMProviderLoader(providers_dir)
