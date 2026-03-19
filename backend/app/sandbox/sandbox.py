"""
AFSA Sandbox - 代码沙箱验证器

在隔离环境中执行和验证生成的代码。
支持 Docker、本地进程、Firecracker 等沙箱类型。
"""

import asyncio
import os
import tempfile
import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


# ============= 沙箱结果 =============

class SandboxResult(BaseModel):
    """沙箱执行结果"""
    
    success: bool
    output: str = ""
    error: Optional[str] = None
    exit_code: int = 0
    execution_time: float = 0.0
    memory_usage: Optional[str] = None
    cpu_usage: Optional[float] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    @classmethod
    def ok(cls, output: str, **kwargs) -> "SandboxResult":
        """创建成功结果"""
        return cls(success=True, output=output, **kwargs)
    
    @classmethod
    def error(cls, message: str, **kwargs) -> "SandboxResult":
        """创建错误结果"""
        return cls(success=False, error=message, **kwargs)


# ============= 沙箱配置 =============

class SandboxConfig(BaseModel):
    """沙箱配置"""
    
    type: str = "local"  # local, docker, firecracker
    timeout_seconds: int = 60
    max_memory_mb: int = 256
    cpu_limit: float = 1.0
    network_enabled: bool = False
    work_dir: Optional[str] = None
    
    # Docker 特定配置
    docker_image: str = "python:3.11-slim"
    docker_network_disabled: bool = True
    
    # Firecracker 特定配置
    firecracker_kernel: Optional[str] = None
    firecracker_memory_mb: int = 128


# ============= 沙箱基类 =============

class SandboxInstance(ABC):
    """沙箱实例基类"""
    
    def __init__(self, config: SandboxConfig):
        self.config = config
        self.id = str(uuid.uuid4())
        self.created_at = datetime.utcnow()
        self._running = False
    
    @abstractmethod
    async def execute(self, code: str, timeout: Optional[int] = None) -> SandboxResult:
        """执行代码
        
        Args:
            code: 要执行的代码
            timeout: 超时时间（秒）
            
        Returns:
            SandboxResult: 执行结果
        """
        pass
    
    @abstractmethod
    async def cleanup(self) -> None:
        """清理沙箱资源"""
        pass
    
    async def __aenter__(self) -> "SandboxInstance":
        """异步上下文管理器入口"""
        self._running = True
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """异步上下文管理器出口"""
        await self.cleanup()
        self._running = False


# ============= 本地沙箱 =============

class LocalSandbox(SandboxInstance):
    """本地进程沙箱
    
    使用子进程执行代码，提供基本隔离。
    注意：安全性较低，仅用于开发环境。
    """
    
    def __init__(self, config: Optional[SandboxConfig] = None):
        if config is None:
            config = SandboxConfig(type="local")
        super().__init__(config)
        self._temp_dir: Optional[tempfile.TemporaryDirectory] = None
    
    async def execute(self, code: str, timeout: Optional[int] = None) -> SandboxResult:
        """在本地子进程中执行代码"""
        start_time = datetime.utcnow()
        timeout = timeout or self.config.timeout_seconds
        
        # 创建临时目录
        self._temp_dir = tempfile.TemporaryDirectory()
        work_dir = Path(self._temp_dir.name)
        
        # 写入代码文件
        code_file = work_dir / "sandbox_code.py"
        with open(code_file, 'w', encoding='utf-8') as f:
            f.write(code)
        
        try:
            # 构建命令
            cmd = ["python3", str(code_file)]
            
            # 执行
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(work_dir),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=timeout,
                )
                
                end_time = datetime.utcnow()
                execution_time = (end_time - start_time).total_seconds()
                
                return SandboxResult(
                    success=process.returncode == 0,
                    output=stdout.decode() if stdout else "",
                    error=stderr.decode() if stderr else None,
                    exit_code=process.returncode or 0,
                    execution_time=execution_time,
                )
                
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                
                return SandboxResult.error(
                    f"Execution timeout after {timeout} seconds",
                    exit_code=-1,
                    execution_time=timeout,
                )
        
        except Exception as e:
            return SandboxResult.error(str(e))
        
        finally:
            # 清理临时目录
            if self._temp_dir:
                self._temp_dir.cleanup()
                self._temp_dir = None
    
    async def cleanup(self) -> None:
        """清理资源"""
        if self._temp_dir:
            self._temp_dir.cleanup()
            self._temp_dir = None


# ============= Docker 沙箱 =============

class DockerSandbox(SandboxInstance):
    """Docker 容器沙箱
    
    使用 Docker 容器提供强隔离的执行环境。
    """
    
    def __init__(self, config: Optional[SandboxConfig] = None):
        if config is None:
            config = SandboxConfig(type="docker")
        super().__init__(config)
        self._container = None
        self._client = None
    
    def _get_client(self):
        """获取 Docker 客户端"""
        if self._client is None:
            try:
                import docker
                self._client = docker.from_env()
            except ImportError:
                raise RuntimeError("Docker SDK not installed. Run: pip install docker")
            except Exception as e:
                raise RuntimeError(f"Failed to connect to Docker: {e}")
        
        return self._client
    
    async def execute(self, code: str, timeout: Optional[int] = None) -> SandboxResult:
        """在 Docker 容器中执行代码"""
        start_time = datetime.utcnow()
        timeout = timeout or self.config.timeout_seconds
        
        try:
            client = self._get_client()
            
            # 创建临时目录存放代码
            with tempfile.TemporaryDirectory() as temp_dir:
                code_file = Path(temp_dir) / "code.py"
                with open(code_file, 'w', encoding='utf-8') as f:
                    f.write(code)
                
                # 容器配置
                host_config = client.api.create_host_config(
                    mem_limit=self.config.max_memory_mb * 1024 * 1024,
                    nano_cpus=int(self.config.cpu_limit * 1e9),
                    network_mode="none" if self.config.docker_network_disabled else "bridge",
                )
                
                # 创建并运行容器
                container = client.containers.run(
                    self.config.docker_image,
                    command=["python", "/app/code.py"],
                    volumes={temp_dir: {"bind": "/app", "mode": "ro"}},
                    host_config=host_config,
                    detach=True,
                    remove=True,
                )
                
                self._container = container
                
                try:
                    # 等待执行完成
                    result = container.wait(timeout=timeout)
                    logs = container.logs().decode()
                    
                    end_time = datetime.utcnow()
                    execution_time = (end_time - start_time).total_seconds()
                    
                    # 获取资源使用情况
                    stats = container.stats(stream=False)
                    memory_usage = self._parse_memory_stats(stats)
                    
                    return SandboxResult(
                        success=result.get("StatusCode", 0) == 0,
                        output=logs,
                        exit_code=result.get("StatusCode", 0),
                        execution_time=execution_time,
                        memory_usage=memory_usage,
                    )
                
                except Exception as e:
                    container.kill()
                    if "timeout" in str(e).lower():
                        return SandboxResult.error(
                            f"Execution timeout after {timeout} seconds",
                            exit_code=-1,
                            execution_time=timeout,
                        )
                    raise
        
        except Exception as e:
            return SandboxResult.error(str(e))
        
        finally:
            await self.cleanup()
    
    def _parse_memory_stats(self, stats: Dict) -> Optional[str]:
        """解析内存统计"""
        try:
            memory = stats.get("memory_stats", {})
            usage = memory.get("usage", 0)
            if usage:
                return f"{usage / (1024 * 1024):.2f} MB"
        except Exception:
            pass
        return None
    
    async def cleanup(self) -> None:
        """清理容器"""
        if self._container:
            try:
                self._container.remove(force=True)
            except Exception:
                pass
            self._container = None
        
        if self._client:
            self._client.close()
            self._client = None


# ============= 沙箱池 =============

class SandboxPool:
    """沙箱池
    
    预创建沙箱实例，提高执行效率。
    """
    
    def __init__(
        self,
        sandbox_type: str = "local",
        pool_size: int = 2,
        config: Optional[SandboxConfig] = None,
    ):
        self.sandbox_type = sandbox_type
        self.pool_size = pool_size
        self.config = config or SandboxConfig(type=sandbox_type)
        self._pool: List[SandboxInstance] = []
        self._available: asyncio.Queue = asyncio.Queue()
        self._initialized = False
    
    async def initialize(self) -> None:
        """初始化沙箱池"""
        if self._initialized:
            return
        
        for _ in range(self.pool_size):
            sandbox = self._create_sandbox()
            self._pool.append(sandbox)
            await self._available.put(sandbox)
        
        self._initialized = True
    
    def _create_sandbox(self) -> SandboxInstance:
        """创建沙箱实例"""
        if self.sandbox_type == "local":
            return LocalSandbox(self.config)
        elif self.sandbox_type == "docker":
            return DockerSandbox(self.config)
        else:
            raise ValueError(f"Unknown sandbox type: {self.sandbox_type}")
    
    async def acquire(self) -> SandboxInstance:
        """获取沙箱实例"""
        if not self._initialized:
            await self.initialize()
        
        try:
            sandbox = await asyncio.wait_for(self._available.get(), timeout=10)
            return sandbox
        except asyncio.TimeoutError:
            # 超时则创建新实例
            return self._create_sandbox()
    
    async def release(self, sandbox: SandboxInstance) -> None:
        """释放沙箱实例"""
        await sandbox.cleanup()
        await self._available.put(sandbox)
    
    async def execute(self, code: str, timeout: Optional[int] = None) -> SandboxResult:
        """从池中获取沙箱并执行代码"""
        sandbox = await self.acquire()
        
        try:
            result = await sandbox.execute(code, timeout)
            return result
        finally:
            await self.release(sandbox)
    
    async def close(self) -> None:
        """关闭沙箱池"""
        while not self._available.empty():
            sandbox = await self._available.get()
            await sandbox.cleanup()
        
        self._pool.clear()
        self._initialized = False


# ============= 代码验证器 =============

class CodeValidator:
    """代码验证器
    
    在沙箱执行前进行安全检查。
    """
    
    # 危险函数列表
    DANGEROUS_FUNCTIONS = [
        "eval", "exec", "compile", "__import__",
        "open", "file", "input",
        "os.system", "os.popen", "os.spawn",
        "subprocess.call", "subprocess.run", "subprocess.Popen",
    ]
    
    # 危险模式
    DANGEROUS_PATTERNS = [
        r"os\.", r"subprocess\.", r"socket\.",
        r"urllib\.", r"requests\.", r"http\.",
        r"__builtins__", r"globals\(\)", r"locals\(\)",
    ]
    
    @classmethod
    def validate(cls, code: str) -> tuple[bool, List[str]]:
        """验证代码安全性
        
        Args:
            code: 要验证的代码
            
        Returns:
            (是否安全，警告列表)
        """
        warnings = []
        
        # 检查危险函数
        for func in cls.DANGEROUS_FUNCTIONS:
            if func in code:
                warnings.append(f"Dangerous function detected: {func}")
        
        # 检查危险模式
        import re
        for pattern in cls.DANGEROUS_PATTERNS:
            if re.search(pattern, code):
                warnings.append(f"Dangerous pattern detected: {pattern}")
        
        is_safe = len(warnings) == 0
        return is_safe, warnings
    
    @classmethod
    def validate_with_exception(cls, code: str) -> None:
        """验证代码，不安全则抛出异常"""
        is_safe, warnings = cls.validate(code)
        
        if not is_safe:
            raise SecurityError(
                f"Code validation failed: {'; '.join(warnings)}"
            )


class SecurityError(Exception):
    """安全异常"""
    pass


# ============= 工厂函数 =============

def create_sandbox(
    sandbox_type: str = "local",
    config: Optional[SandboxConfig] = None,
) -> SandboxInstance:
    """创建沙箱实例
    
    Args:
        sandbox_type: 沙箱类型 (local, docker)
        config: 沙箱配置
        
    Returns:
        沙箱实例
    """
    if sandbox_type == "local":
        return LocalSandbox(config)
    elif sandbox_type == "docker":
        return DockerSandbox(config)
    else:
        raise ValueError(f"Unknown sandbox type: {sandbox_type}")


def create_sandbox_pool(
    sandbox_type: str = "local",
    pool_size: int = 2,
    config: Optional[SandboxConfig] = None,
) -> SandboxPool:
    """创建沙箱池
    
    Args:
        sandbox_type: 沙箱类型
        pool_size: 池大小
        config: 沙箱配置
        
    Returns:
        沙箱池实例
    """
    return SandboxPool(sandbox_type, pool_size, config)
