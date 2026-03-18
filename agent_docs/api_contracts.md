# API 契约文档

## 基础信息

- **Base URL**: `/api/v1`
- **认证方式**: JWT Bearer Token
- **内容类型**: `application/json`

## 任务管理

### 创建任务
```
POST /tasks
```

**请求体**:
```json
{
  "type": "feature",
  "priority": "medium",
  "description": "给订单列表添加筛选功能",
  "structured_requirements": [
    {"field": "status", "type": "select"},
    {"field": "date", "type": "date_range"}
  ],
  "constraints": {
    "target_zone": "mutable",
    "affected_modules": ["ui"]
  }
}
```

**响应**:
```json
{
  "id": "uuid",
  "type": "feature",
  "priority": "medium",
  "status": "pending",
  "description": "给订单列表添加筛选功能",
  "result": null
}
```

### 获取任务列表
```
GET /tasks?status=pending&limit=20&offset=0
```

### 获取任务详情
```
GET /tasks/{task_id}
```

### 取消任务
```
DELETE /tasks/{task_id}
```

## 对话管理

### 创建会话
```
POST /conversations
```

**响应**:
```json
{
  "id": "uuid",
  "status": "active",
  "messages": []
}
```

### 发送消息
```
POST /conversations/{session_id}/messages
```

**请求体**:
```json
{
  "content": "我想给订单列表加个筛选功能"
}
```

**响应**:
```json
{
  "id": "uuid",
  "role": "assistant",
  "content": "我理解您想在订单列表添加筛选功能。请问您希望按哪些字段筛选？"
}
```

### 获取会话
```
GET /conversations/{session_id}
```

### 关闭会话
```
DELETE /conversations/{session_id}
```

## 快照管理

### 获取快照列表
```
GET /snapshots?limit=20&offset=0
```

**响应**:
```json
{
  "items": [
    {
      "id": "sha256_hash",
      "task_id": "uuid",
      "message": "添加订单筛选功能",
      "created_at": "2024-01-15T10:30:00Z"
    }
  ]
}
```

### 获取快照详情
```
GET /snapshots/{snapshot_id}
```

### 恢复快照
```
POST /snapshots/{snapshot_id}/restore
```

## 审计日志

### 获取审计日志
```
GET /audit-logs?start_time=2024-01-01&end_time=2024-01-31&action=task.create&limit=100
```

### 导出审计日志
```
GET /audit-logs/export?start_time=2024-01-01&end_time=2024-01-31
```

## WebSocket

### 连接
```
WS /api/v1/ws?token={jwt_token}
```

### 消息格式

**任务进度**:
```json
{
  "type": "task_progress",
  "payload": {
    "task_id": "uuid",
    "status": "running",
    "progress": 45,
    "message": "Generating code..."
  },
  "timestamp": "2024-01-15T10:30:00Z"
}
```

**对话消息**:
```json
{
  "type": "conversation",
  "payload": {
    "session_id": "uuid",
    "message": {
      "role": "assistant",
      "content": "我理解您的需求..."
    }
  },
  "timestamp": "2024-01-15T10:30:00Z"
}
```

## 错误响应

```json
{
  "detail": "Error message",
  "status_code": 400,
  "timestamp": "2024-01-15T10:30:00Z"
}
```

## 状态码

| 状态码 | 含义 |
|-------|------|
| 200 | 成功 |
| 201 | 创建成功 |
| 204 | 无内容（删除成功） |
| 400 | 请求参数错误 |
| 401 | 未认证 |
| 403 | 无权限 |
| 404 | 资源不存在 |
| 500 | 服务器内部错误 |