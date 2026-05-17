import React, { useState, KeyboardEvent } from 'react';
import { useConversationStore, useTaskStore } from '../../store';
import { apiClient, wsClient } from '../../lib/api';
import { Message } from '../../types';
import { clsx } from 'clsx';
import { Send, Paperclip } from 'lucide-react';

interface MessageInputProps {
  className?: string;
  disabled?: boolean;
}

export const MessageInput: React.FC<MessageInputProps> = ({
  className,
  disabled = false,
}) => {
  const [input, setInput] = useState('');
  const {
    currentConversationId,
    addMessage,
    updateMessageStatus,
    createConversation,
  } = useConversationStore();
  const addTask = useTaskStore((state) => state.addTask);
  const [isSending, setIsSending] = useState(false);

  const sendMessage = async () => {
    if (!input.trim() || isSending || disabled) return;

    const messageContent = input.trim();
    setInput('');
    setIsSending(true);

    // 创建临时消息 ID
    const tempId = crypto.randomUUID();
    let tempMessageAdded = false;
    let conversationId = currentConversationId;

    try {
      // 如果没有当前对话，先创建后端会话，再写入本地会话列表
      if (!conversationId) {
        const title = messageContent.slice(0, 50) + (messageContent.length > 50 ? '...' : '');
        const session = await apiClient.createConversation();
        conversationId = createConversation(title, session.id);
      }

      // 创建临时消息
      const tempMessage: Message = {
        id: tempId,
        role: 'user',
        content: messageContent,
        timestamp: Date.now(),
        status: 'sending',
      };

      addMessage(tempMessage);
      tempMessageAdded = true;

      // Conversation messages are sent via HTTP; backend WebSocket only supports task events.
      const response = await apiClient.sendConversationMessage(conversationId, messageContent);
      updateMessageStatus(tempId, 'sent');
      addMessage(response);

      const taskId = response.metadata?.task_id;
      if (typeof taskId === 'string') {
        const task = await apiClient.getTask(taskId);
        addTask(task);
        wsClient.subscribeTask(taskId);
      }
    } catch (error) {
      console.error('Failed to send message:', error);
      if (tempMessageAdded) {
        updateMessageStatus(tempId, 'error');
      } else {
        setInput(messageContent);
      }
    } finally {
      setIsSending(false);
    }
  };

  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div
      className={clsx(
        'border-t border-gray-200 bg-white p-4',
        className
      )}
    >
      <div className="flex items-end gap-3 max-w-4xl mx-auto">
        <button
          className="p-2 text-gray-400 hover:text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
          title="添加附件"
        >
          <Paperclip className="w-5 h-5" />
        </button>
        
        <div className="flex-1 relative">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="输入消息... (Shift+Enter 换行)"
            disabled={disabled || isSending}
            rows={1}
            className={clsx(
              'w-full resize-none rounded-xl border border-gray-300 px-4 py-3',
              'focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent',
              'disabled:bg-gray-100 disabled:cursor-not-allowed',
              'max-h-32 min-h-[48px]'
            )}
            style={{
              height: 'auto',
              minHeight: '48px',
            }}
            onInput={(e) => {
              const target = e.target as HTMLTextAreaElement;
              target.style.height = 'auto';
              target.style.height = Math.min(target.scrollHeight, 128) + 'px';
            }}
          />
        </div>

        <button
          onClick={sendMessage}
          disabled={!input.trim() || isSending || disabled}
          className={clsx(
            'p-3 rounded-xl transition-all duration-200',
            input.trim() && !isSending && !disabled
              ? 'bg-indigo-600 text-white hover:bg-indigo-700 shadow-md hover:shadow-lg'
              : 'bg-gray-200 text-gray-400 cursor-not-allowed'
          )}
        >
          <Send className="w-5 h-5" />
        </button>
      </div>
      
      <div className="text-xs text-gray-400 mt-2 text-center">
        按 Enter 发送，Shift+Enter 换行
      </div>
    </div>
  );
};

export default MessageInput;
