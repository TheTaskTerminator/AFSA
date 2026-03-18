"""PM Agent prompt templates.

This module contains prompt templates for the PM Agent,
including system prompts, clarification questions, and task card generation.
"""

# System prompt for PM Agent
PM_SYSTEM_PROMPT = """你是一位专业的产品经理 Agent，负责理解用户需求、澄清需求细节、并生成结构化的任务卡片。

## 你的职责

1. **需求理解**: 深入理解用户描述的功能需求或问题
2. **澄清对话**: 通过提问澄清模糊的需求点
3. **任务拆分**: 将复杂需求拆分为可执行的子任务
4. **任务卡片生成**: 输出结构化的任务卡片供开发 Agent 执行

## 工作流程

1. 分析用户输入，识别需求类型（新功能/Bug修复/配置变更）
2. 评估需求的完整性，必要时提出澄清问题
3. 当需求足够清晰时，生成任务卡片
4. 将任务分发给相应的开发 Agent

## 输出格式

当需要澄清时，使用 JSON 格式输出：
```json
{
  "type": "clarification",
  "questions": [
    {
      "id": "q1",
      "question": "问题描述",
      "options": ["选项A", "选项B"] // 可选，如果有预设选项
    }
  ]
}
```

当需求清晰时，输出任务卡片：
```json
{
  "type": "task_card",
  "task": {
    "id": "task-xxx",
    "type": "feature|bugfix|config",
    "priority": "high|medium|low",
    "description": "任务描述",
    "structured_requirements": [
      {"id": "req-1", "description": "需求描述", "acceptance_criteria": "验收标准"}
    ],
    "constraints": {
      "timeout_seconds": 300,
      "technology_stack": ["Python", "FastAPI"]
    }
  }
}
```

## 注意事项

- 一次最多提出 3 个澄清问题
- 优先确认关键业务逻辑
- 任务拆分粒度适中，每个任务应在 1-4 小时内可完成
- 确保每个子任务有明确的验收标准
"""

# Clarification question templates
CLARIFICATION_TEMPLATES = {
    "feature": [
        "请描述这个功能的主要使用场景是什么？",
        "这个功能的用户角色是谁？",
        "这个功能是否需要与其他系统或模块交互？",
        "是否有参考的竞品或类似功能？",
        "这个功能的性能要求是什么？",
    ],
    "bugfix": [
        "这个 Bug 的复现步骤是什么？",
        "期望的正确行为是什么？",
        "这个 Bug 影响的范围有多大？",
        "是否有相关的错误日志或截图？",
    ],
    "config": [
        "这个配置变更的原因是什么？",
        "需要修改哪些配置项？",
        "是否需要保留旧配置的兼容性？",
    ],
}

# Task type detection keywords
TASK_TYPE_KEYWORDS = {
    "feature": ["新增", "添加", "实现", "开发", "创建", "增加", "feature", "新功能"],
    "bugfix": ["修复", "bug", "错误", "问题", "异常", "崩溃", "bugfix", "fix"],
    "config": ["配置", "修改配置", "更新配置", "config", "setting", "参数"],
}

# Priority detection keywords
PRIORITY_KEYWORDS = {
    "high": ["紧急", "重要", "立即", "尽快", "critical", "urgent", "high", "阻塞"],
    "low": ["不急", "后续", "优化", "可选", "low", "nice to have"],
}


def get_system_prompt() -> str:
    """Get the system prompt for PM Agent."""
    return PM_SYSTEM_PROMPT


def get_clarification_questions(task_type: str, count: int = 2) -> list[str]:
    """Get clarification question templates for a task type.

    Args:
        task_type: Type of task (feature, bugfix, config)
        count: Number of questions to return

    Returns:
        List of clarification question templates
    """
    templates = CLARIFICATION_TEMPLATES.get(task_type, CLARIFICATION_TEMPLATES["feature"])
    return templates[:count]


def detect_task_type(description: str) -> str:
    """Detect task type from description.

    Args:
        description: Task description

    Returns:
        Detected task type (feature, bugfix, or config)
    """
    description_lower = description.lower()

    for task_type, keywords in TASK_TYPE_KEYWORDS.items():
        for keyword in keywords:
            if keyword.lower() in description_lower:
                return task_type

    return "feature"  # Default to feature


def detect_priority(description: str) -> str:
    """Detect priority from description.

    Args:
        description: Task description

    Returns:
        Detected priority (high, medium, or low)
    """
    description_lower = description.lower()

    for priority, keywords in PRIORITY_KEYWORDS.items():
        for keyword in keywords:
            if keyword.lower() in description_lower:
                return priority

    return "medium"  # Default to medium


# Task card generation prompt
TASK_CARD_GENERATION_PROMPT = """基于以下对话历史，生成一个结构化的任务卡片。

## 对话历史
{conversation_history}

## 要求
1. 提取所有已确认的需求点
2. 为每个需求点设置验收标准
3. 评估任务优先级
4. 设置合理的超时时间

请直接输出 JSON 格式的任务卡片，不要包含其他内容。
"""