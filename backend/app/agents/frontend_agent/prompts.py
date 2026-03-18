"""Frontend Agent prompt templates.

This module contains prompt templates for the Frontend Agent,
including system prompts, code generation templates, and component patterns.
"""

# System prompt for Frontend Agent
FRONTEND_SYSTEM_PROMPT = """你是一位专业的前端开发 Agent，负责根据需求生成高质量的 React + TypeScript 代码。

## 你的职责

1. **UI 组件开发**: 根据需求描述生成 React 组件代码
2. **状态管理**: 使用 Zustand 进行状态管理
3. **样式实现**: 使用 Tailwind CSS 和 shadcn/ui 组件库
4. **代码质量**: 确保类型安全、可维护性和性能

## 技术栈

- **框架**: React 18 + TypeScript
- **状态管理**: Zustand
- **样式**: Tailwind CSS + shadcn/ui
- **构建工具**: Vite
- **API 通信**: 原生 fetch + WebSocket

## 代码规范

1. 使用函数组件和 Hooks
2. 所有组件都要有明确的 TypeScript 类型
3. 使用 Tailwind CSS 类名进行样式
4. 遵循 Airbnb 代码风格
5. 组件拆分合理，单一职责

## 输出格式

当生成代码时，使用 JSON 格式输出：

```json
{
  "type": "code_generation",
  "files": [
    {
      "path": "src/components/Button.tsx",
      "content": "// 代码内容",
      "description": "组件说明"
    }
  ],
  "dependencies": ["依赖包名"],
  "preview_url": "可选的预览地址"
}
```

当需要澄清时：
```json
{
  "type": "clarification",
  "questions": [
    {
      "id": "q1",
      "question": "问题描述",
      "options": ["选项A", "选项B"]
    }
  ]
}
```

## 注意事项

- 优先使用 shadcn/ui 现有组件
- 确保响应式设计
- 考虑无障碍访问 (a11y)
- 添加必要的错误处理和加载状态
"""

# Component templates for common patterns
COMPONENT_TEMPLATES = {
    "page": """import {{  }} from 'react'
import {{  }} from 'zustand'

interface {name}Props {{
  // Props 定义
}}

export function {name}({{ }}: {name}Props) {{
  return (
    <div className="container mx-auto p-4">
      {/* 页面内容 */}
    </div>
  )
}}
""",
    "form": """import {{ useState }} from 'react'
import {{ Button }} from '@/components/ui/button'
import {{ Input }} from '@/components/ui/input'
import {{ Label }} from '@/components/ui/label'

interface {name}Props {{
  onSubmit: (data: Record<string, unknown>) => void
}}

export function {name}({{ onSubmit }}: {name}Props) {{
  const [formData, setFormData] = useState({{}})

  const handleSubmit = (e: React.FormEvent) => {{
    e.preventDefault()
    onSubmit(formData)
  }}

  return (
    <form onSubmit={{handleSubmit}} className="space-y-4">
      {/* 表单字段 */}
      <Button type="submit">提交</Button>
    </form>
  )
}}
""",
    "list": """import {{  }} from 'react'

interface Item {{
  id: string
  // 其他字段
}}

interface {name}Props {{
  items: Item[]
  onItemClick?: (item: Item) => void
}}

export function {name}({{ items, onItemClick }}: {name}Props) {{
  return (
    <ul className="divide-y">
      {{items.map((item) => (
        <li
          key={{item.id}}
          onClick={{() => onItemClick?.(item)}}
          className="p-4 hover:bg-gray-50 cursor-pointer"
        >
          {{/* 列表项内容 */}}
        </li>
      ))}}
    </ul>
  )
}}
""",
    "card": """import {{ Card, CardHeader, CardTitle, CardContent, CardFooter }} from '@/components/ui/card'

interface {name}Props {{
  title: string
  children: React.ReactNode
  footer?: React.ReactNode
}}

export function {name}({{ title, children, footer }}: {name}Props) {{
  return (
    <Card>
      <CardHeader>
        <CardTitle>{{title}}</CardTitle>
      </CardHeader>
      <CardContent>{{children}}</CardContent>
      {{footer && <CardFooter>{{footer}}</CardFooter>}}
    </Card>
  )
}}
""",
    "store": """import {{ create }} from 'zustand'
import {{ devtools }} from 'zustand/middleware'

interface {name}State {{
  // State
  data: unknown
  loading: boolean
  error: string | null

  // Actions
  setData: (data: unknown) => void
  setLoading: (loading: boolean) => void
  setError: (error: string | null) => void
  reset: () => void
}}

const initialState = {{
  data: null,
  loading: false,
  error: null,
}}

export const use{name}Store = create<{name}State>()(
  devtools(
    (set) => ({{
      ...initialState,
      setData: (data) => set({{ data }}),
      setLoading: (loading) => set({{ loading }}),
      setError: (error) => set({{ error }}),
      reset: () => set(initialState),
    }}),
    {{ name: '{name_lower}-store' }}
  )
)
""",
}

# API hook template
API_HOOK_TEMPLATE = """import {{ useState, useEffect }} from 'react'

interface Use{name}Options {{
  enabled?: boolean
}}

interface Use{name}Return<T> {{
  data: T | null
  loading: boolean
  error: Error | null
  refetch: () => void
}}

export function use{name}<T>(
  url: string,
  options?: Use{name}Options
): Use{name}Return<T> {{
  const [data, setData] = useState<T | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<Error | null>(null)

  const fetchData = async () => {{
    try {{
      setLoading(true)
      const response = await fetch(url)
      if (!response.ok) throw new Error('Request failed')
      const json = await response.json()
      setData(json)
    }} catch (e) {{
      setError(e instanceof Error ? e : new Error('Unknown error'))
    }} finally {{
      setLoading(false)
    }}
  }}

  useEffect(() => {{
    if (options?.enabled !== false) {{
      fetchData()
    }}
  }}, [url, options?.enabled])

  return {{ data, loading, error, refetch: fetchData }}
}}
"""

# WebSocket hook template
WEBSOCKET_HOOK_TEMPLATE = """import {{ useEffect, useRef, useState }} from 'react'

interface UseWebSocketOptions {{
  onMessage?: (data: unknown) => void
  onOpen?: () => void
  onClose?: () => void
  onError?: (error: Event) => void
  reconnect?: boolean
  reconnectInterval?: number
}}

export function useWebSocket(url: string, options: UseWebSocketOptions = {{}}) {{
  const [readyState, setReadyState] = useState<WebSocket['readyState']>(WebSocket.CLOSED)
  const wsRef = useRef<WebSocket | null>(null)

  useEffect(() => {{
    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.onopen = () => {{
      setReadyState(WebSocket.OPEN)
      options.onOpen?.()
    }}

    ws.onclose = () => {{
      setReadyState(WebSocket.CLOSED)
      options.onClose?.()
    }}

    ws.onerror = (error) => {{
      options.onError?.(error)
    }}

    ws.onmessage = (event) => {{
      try {{
        const data = JSON.parse(event.data)
        options.onMessage?.(data)
      }} catch {{
        options.onMessage?.(event.data)
      }}
    }}

    return () => ws.close()
  }}, [url])

  const send = (data: unknown) => {{
    if (wsRef.current?.readyState === WebSocket.OPEN) {{
      wsRef.current.send(JSON.stringify(data))
    }}
  }}

  return {{ readyState, send }}
}}
"""


def get_system_prompt() -> str:
    """Get the system prompt for Frontend Agent."""
    return FRONTEND_SYSTEM_PROMPT


def get_component_template(template_type: str, name: str) -> str:
    """Get a component template by type.

    Args:
        template_type: Type of template (page, form, list, card, store)
        name: Component name

    Returns:
        Template string with placeholders filled
    """
    template = COMPONENT_TEMPLATES.get(template_type, COMPONENT_TEMPLATES["page"])
    return template.format(name=name, name_lower=name.lower())


def detect_component_type(description: str) -> str:
    """Detect component type from description.

    Args:
        description: Component description

    Returns:
        Detected component type
    """
    keywords_map = {
        "form": ["表单", "登录", "注册", "提交", "输入", "form", "login", "register"],
        "list": ["列表", "表格", "数据展示", "list", "table", "grid"],
        "card": ["卡片", "面板", "信息展示", "card", "panel", "info"],
        "page": ["页面", "视图", "screen", "page", "view"],
    }

    description_lower = description.lower()
    for comp_type, keywords in keywords_map.items():
        for keyword in keywords:
            if keyword in description_lower:
                return comp_type

    return "page"  # Default


def extract_component_name(description: str) -> str:
    """Extract or generate component name from description.

    Args:
        description: Component description

    Returns:
        Component name in PascalCase
    """
    # Try to extract key nouns from description
    import re

    # Remove common Chinese particles and articles
    cleaned = re.sub(r"[的吗了呢]", "", description)

    # Find English words
    english_words = re.findall(r"[A-Za-z]+", cleaned)

    if english_words:
        return "".join(word.capitalize() for word in english_words[:3])

    # Generate from Chinese description
    # Take first 2-4 meaningful characters
    chinese_chars = re.findall(r"[\u4e00-\u9fff]+", cleaned)
    if chinese_chars:
        # Simple transliteration for common UI terms
        return f"Component{abs(hash(description)) % 1000}"

    return "GeneratedComponent"


# Code generation prompt
CODE_GENERATION_PROMPT = """基于以下需求，生成 React + TypeScript 前端代码。

## 需求描述
{description}

## 技术要求
- 框架: React 18 + TypeScript
- 状态管理: Zustand
- 样式: Tailwind CSS + shadcn/ui
- 构建工具: Vite

## 约束条件
{constraints}

## 需要生成的文件
{required_files}

请输出完整的代码，包括：
1. 组件代码
2. 类型定义
3. 样式类名
4. 必要的 hooks
"""