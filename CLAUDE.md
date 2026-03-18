# AFSA - AI-Driven Fluid Software Architecture

## 项目概述

AFSA 是一个创新框架，核心思想是将"需求 → 开发 → 交付"循环内嵌进软件本身。每个软件自带一支 AI 驱动的开发团队，能够根据用户的自然语言指令进行实时个性化改造。

## 目录结构

```
afsa/
├── backend/           # Python + FastAPI 后端服务
├── frontend/          # React + TypeScript 前端应用
├── infra/             # Docker 和基础设施配置
├── design/            # 设计文档
├── discuss/           # 项目讨论记录
└── agent_docs/        # Agent 专用详细文档
```

## 技术栈

### 后端
- **语言**: Python 3.11+
- **框架**: FastAPI
- **Agent 框架**: 可插拔 (LangGraph / CrewAI / AutoGen)
- **数据库**: PostgreSQL + Redis
- **消息队列**: NATS
- **沙箱**: Firecracker

### 前端
- **框架**: React 18 + TypeScript
- **构建工具**: Vite
- **状态管理**: Zustand
- **样式**: Tailwind CSS

## 快速开始

### 环境要求
- Python 3.11+
- Node.js 18+
- Docker & Docker Compose
- uv (Python 包管理)
- pnpm (Node 包管理)

### 启动开发环境

```bash
# 启动基础服务 (PostgreSQL, Redis, NATS)
cd infra/docker && docker-compose up -d postgres redis nats

# 启动后端
cd backend
uv sync
uv run uvicorn app.main:app --reload

# 启动前端 (新终端)
cd frontend
pnpm install
pnpm dev
```

### 访问地址
- 前端: http://localhost:3000
- 后端 API: http://localhost:8000
- API 文档: http://localhost:8000/docs

## 四层架构

| 层级 | 名称 | 核心组件 |
|-----|------|---------|
| L1 | AI Team Layer | PM Agent, Frontend Agent, Backend Agent, Data Agent |
| L2 | Orchestration Layer | Task Dispatcher, Sandbox Runner, Version Control |
| L3 | Business Layer | Mutable Zone, Immutable Kernel |
| L4 | Governance Layer | Permission Guard, Audit Trail |

## Agent 框架配置

通过环境变量切换 Agent 框架：

```bash
# 使用 LangGraph (默认)
AGENT_FRAMEWORK=langgraph

# 使用 CrewAI
AGENT_FRAMEWORK=crewai

# 使用 AutoGen
AGENT_FRAMEWORK=autogen
```

## 开发阶段

- **Phase 0**: 基础设施搭建 (当前)
- **Phase 1**: 数据层 + 治理层
- **Phase 2**: 编排层
- **Phase 3**: AI Team 层
- **Phase 4**: 业务层 + API
- **Phase 5**: 前端 + 集成
- **Phase 6**: 测试 + 优化

## 详细文档

- [数据库 Schema](./agent_docs/database_schema.md)
- [API 契约](./agent_docs/api_contracts.md)
- [测试指南](./agent_docs/testing_guide.md)

## 设计理念

核心创新：将 AI 开发能力内嵌到软件中，实现"用户即开发者"。通过 Mutable/Immutable 双区隔离保障系统稳定性。