# 测试指南

## 测试策略

采用测试金字塔策略：

```
                    ┌─────────┐
                    │ E2E 测试 │  (~10%)
                    └────┬────┘
                 ┌───────┴───────┐
                 │   集成测试     │  (~20%)
                 └───────┬───────┘
            ┌────────────┴────────────┐
            │       单元测试           │  (~70%)
            └─────────────────────────┘
```

## 覆盖率目标

| 区域 | 覆盖率目标 |
|-----|-----------|
| 核心业务逻辑 | ≥ 90% |
| API 接口 | 100% |
| Agent 工作流 | ≥ 85% |
| 沙箱隔离 | 100% |

## 运行测试

### 单元测试
```bash
cd backend
uv run pytest tests/unit -v
```

### 集成测试
```bash
cd backend
uv run pytest tests/integration -v
```

### E2E 测试
```bash
cd backend
uv run pytest tests/e2e -v
```

### 覆盖率报告
```bash
cd backend
uv run pytest --cov=app --cov-report=html
```

## 测试组织

```
tests/
├── conftest.py          # 测试配置和 fixtures
├── unit/                # 单元测试
│   ├── test_models.py
│   ├── test_agents.py
│   └── test_utils.py
├── integration/         # 集成测试
│   ├── test_api.py
│   ├── test_dispatcher.py
│   └── test_sandbox.py
└── e2e/                 # E2E 测试
    └── test_task_flow.py
```

## 关键测试场景

### 1. 完整任务流程测试
```python
async def test_complete_task_flow():
    # 1. 创建对话会话
    session = await create_conversation()

    # 2. 发送需求消息
    response = await send_message(session.id, "给订单列表添加筛选功能")

    # 3. 验证澄清问题
    assert response.type == "clarification"

    # 4. 回答澄清问题
    response = await send_message(session.id, "按状态和日期筛选")

    # 5. 验证任务卡生成
    task_card = await get_task_card(session.id)
    assert task_card.type == "feature"

    # 6. 执行任务
    result = await execute_task(task_card.id)
    assert result.status == "completed"
```

### 2. 沙箱池测试
```python
async def test_sandbox_pool():
    pool = SandboxPool(pool_size=3)
    await pool.initialize()

    # 获取沙箱
    sandbox = await pool.acquire()
    assert sandbox.status == "busy"

    # 释放沙箱
    await pool.release(sandbox)
    assert sandbox.status == "idle"
```

### 3. 权限测试
```python
async def test_immutable_zone_protection():
    guard = PermissionGuard()
    user = User(role="developer")

    # 尝试写入 Immutable Zone
    with pytest.raises(PermissionDeniedError):
        guard.check(user, ActionType.WRITE, "/immutable/auth/config")

    # 允许读取
    assert guard.check(user, ActionType.READ, "/immutable/auth/config")
```

## Mock 策略

### LLM Mock
```python
@pytest.fixture
def mock_llm():
    """Mock LLM responses for testing."""
    with patch("langchain.chat_models.ChatOpenAI") as mock:
        mock.return_value.invoke.return_value = "Mocked response"
        yield mock
```

### 数据库 Mock
```python
@pytest.fixture
async def mock_db():
    """Use in-memory SQLite for testing."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
```

## CI/CD 集成

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16
        env:
          POSTGRES_PASSWORD: postgres
        ports:
          - 5432:5432
      redis:
        image: redis:7
        ports:
          - 6379:6379

    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        run: curl -LsSf https://astral.sh/uv/install.sh | sh

      - name: Run tests
        run: |
          cd backend
          uv sync
          uv run pytest --cov=app --cov-report=xml

      - name: Upload coverage
        uses: codecov/codecov-action@v3
```