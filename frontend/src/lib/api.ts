import type { Message, Task, WSMessage } from '../types';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '/api/v1';
const WS_URL =
  import.meta.env.VITE_WS_URL ??
  `${window.location.protocol === 'https:' ? 'wss' : 'ws'}://${window.location.host}/api/v1/ws`;

type ClientWSMessage =
  | { type: 'subscribe_task'; data: { task_id: string } }
  | { type: 'unsubscribe_task'; data: { task_id: string } }
  | { type: 'subscribe_all'; data?: Record<string, never> }
  | { type: 'ping'; data?: Record<string, never> };

type MessageHandler = (message: WSMessage) => void;

type BackendMessage = {
  id: string;
  role: Message['role'];
  content: string;
  created_at?: string;
  metadata?: Record<string, any>;
};

function toTimestamp(value?: string): number {
  return value ? new Date(value).getTime() : Date.now();
}

function mapMessage(message: BackendMessage): Message {
  return {
    id: message.id,
    role: message.role,
    content: message.content,
    timestamp: toTimestamp(message.created_at),
    metadata: message.metadata,
    status: 'sent',
  };
}

class WSClient {
  private socket: WebSocket | null = null;
  private handlers = new Set<MessageHandler>();

  async connect(): Promise<void> {
    if (this.socket?.readyState === WebSocket.OPEN) return;

    await new Promise<void>((resolve, reject) => {
      const socket = new WebSocket(WS_URL);
      this.socket = socket;

      socket.onopen = () => {
        resolve();
      };
      socket.onerror = () => reject(new Error('WebSocket connection failed'));
      socket.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data) as WSMessage;
          this.handlers.forEach((handler) => handler(message));
        } catch (error) {
          console.error('Failed to parse WebSocket message:', error);
        }
      };
      socket.onclose = () => {
        if (this.socket === socket) this.socket = null;
      };
    });
  }

  disconnect(): void {
    this.socket?.close();
    this.socket = null;
  }

  isConnected(): boolean {
    return this.socket?.readyState === WebSocket.OPEN;
  }

  send(message: ClientWSMessage): void {
    if (!this.isConnected()) return;
    this.socket?.send(JSON.stringify({ data: {}, ...message }));
  }

  onMessage(handler: MessageHandler): () => void {
    this.handlers.add(handler);
    return () => this.handlers.delete(handler);
  }

  subscribeTask(taskId: string): void {
    this.send({ type: 'subscribe_task', data: { task_id: taskId } });
  }

  unsubscribeTask(taskId: string): void {
    this.send({ type: 'unsubscribe_task', data: { task_id: taskId } });
  }

  ping(): void {
    this.send({ type: 'ping', data: {} });
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json', ...init?.headers },
    ...init,
  });

  if (!response.ok) {
    const body = await response.text();
    throw new Error(body || `Request failed: ${response.status}`);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return response.json() as Promise<T>;
}

export const apiClient = {
  createConversation: () => request<{ id: string }>('/conversations', { method: 'POST', body: '{}' }),
  sendConversationMessage: async (sessionId: string, content: string) => {
    const message = await request<BackendMessage>(`/conversations/${encodeURIComponent(sessionId)}/messages`, {
      method: 'POST',
      body: JSON.stringify({ content }),
    });
    return mapMessage(message);
  },
  getTask: (taskId: string) => request<Task>(`/tasks/${encodeURIComponent(taskId)}`),
  listTasks: () => request<Task[]>('/tasks'),
};

export const wsClient = new WSClient();
