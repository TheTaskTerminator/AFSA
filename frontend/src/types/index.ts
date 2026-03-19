// ==================== Core Types ====================

// 消息类型定义
export interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: number;
  status?: 'sending' | 'sent' | 'error';
}

// 对话类型定义
export interface Conversation {
  id: string;
  title: string;
  messages: Message[];
  createdAt: number;
  updatedAt: number;
}

// ==================== Task Types ====================

export type TaskType = 'feature' | 'bugfix' | 'refactor' | 'test' | 'doc';
export type TaskPriority = 'low' | 'medium' | 'high';
export type TaskStatus = 'pending' | 'queued' | 'running' | 'verifying' | 'completed' | 'failed' | 'cancelled';

export interface StructuredRequirement {
  field: string;
  type: string;
  options?: string[];
  default?: any;
}

export interface TaskConstraints {
  target_zone: string;
  affected_modules: string[];
  timeout_seconds: number;
}

export interface TaskResult {
  success: boolean;
  output?: string;
  files_changed: string[];
  snapshot_id?: string;
  metrics?: Record<string, any>;
}

export interface Task {
  id: string;
  type: TaskType;
  priority: TaskPriority;
  status: TaskStatus;
  description: string;
  structured_requirements?: StructuredRequirement[];
  constraints?: TaskConstraints;
  result?: TaskResult;
  error_message?: string;
  user_id?: string;
  session_id?: string;
  createdAt: number;
  startedAt?: number;
  completedAt?: number;
  timeout_seconds: number;
}

// Task create/update schemas
export interface TaskCreate {
  type: TaskType;
  priority?: TaskPriority;
  description: string;
  structured_requirements?: StructuredRequirement[];
  constraints?: TaskConstraints;
  session_id?: string;
}

export interface TaskUpdate {
  priority?: TaskPriority;
  status?: TaskStatus;
  result?: TaskResult;
  error_message?: string;
}

// ==================== Snapshot Types ====================

export interface Snapshot {
  id: string;
  task_id?: string;
  parent_id?: string;
  tree_hash: string;
  message?: string;
  metadata?: Record<string, any>;
  createdAt: number;
}

// ==================== Audit Log Types ====================

export interface AuditLog {
  id: string;
  timestamp: number;
  action: string;
  resource: string;
  resource_id?: string;
  actor_user_id?: string;
  actor_username?: string;
  actor_role?: string;
  actor_ip_address?: string;
  changes?: Record<string, any>;
  result: 'success' | 'failure';
  error_message?: string;
  context?: Record<string, any>;
  snapshot_id?: string;
}

// ==================== WebSocket Types ====================

export enum WSMessageType {
  // Client -> Server
  SUBSCRIBE_TASK = 'subscribe_task',
  UNSUBSCRIBE_TASK = 'unsubscribe_task',
  SUBSCRIBE_ALL = 'subscribe_all',
  PING = 'ping',

  // Server -> Client
  TASK_PROGRESS = 'task_progress',
  TASK_STATUS = 'task_status',
  TASK_CREATED = 'task_created',
  TASK_COMPLETED = 'task_completed',
  TASK_FAILED = 'task_failed',
  PONG = 'pong',
  ERROR = 'error',
}

export interface WSMessage {
  type: WSMessageType;
  data: Record<string, any>;
  timestamp?: string;
}

// WebSocket message payloads
export interface TaskProgressData {
  task_id: string;
  progress_percent: number;
  message: string;
  status?: TaskStatus;
}

export interface TaskStatusData {
  task_id?: string;
  status: TaskStatus | 'subscribed' | 'subscribed_all';
  message: string;
}

export interface TaskCreatedData {
  task_id: string;
  [key: string]: any;
}

export interface TaskCompletedData {
  task_id: string;
  result?: TaskResult;
}

export interface TaskFailedData {
  task_id: string;
  error: string;
}

export interface WSErrorData {
  error: string;
}

// ==================== API Response Types ====================

export interface APIResponse<T> {
  success: boolean;
  data?: T;
  error?: string;
}

export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

// ==================== Query Parameters ====================

export interface TaskQueryParams {
  status?: TaskStatus;
  priority?: TaskPriority;
  user_id?: string;
  session_id?: string;
  limit?: number;
  offset?: number;
}

export interface AuditLogQueryParams {
  start_time?: string;
  end_time?: string;
  action?: string;
  limit?: number;
}
