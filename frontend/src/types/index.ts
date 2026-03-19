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

// 任务类型定义
export interface Task {
  id: string;
  title: string;
  description: string;
  status: 'pending' | 'in_progress' | 'completed' | 'failed';
  progress: number;
  createdAt: number;
  updatedAt: number;
  result?: string;
}

// 代码变更类型定义
export interface CodeChange {
  id: string;
  filePath: string;
  oldContent: string;
  newContent: string;
  diff?: string;
}

// UI 变更类型定义
export interface UIChange {
  id: string;
  component: string;
  description: string;
  previewUrl?: string;
}

// WebSocket 消息类型
export interface WSMessage {
  type: 'message' | 'task_update' | 'code_change' | 'ui_change' | 'error';
  payload: any;
}

// API 响应类型
export interface APIResponse<T> {
  success: boolean;
  data?: T;
  error?: string;
}
