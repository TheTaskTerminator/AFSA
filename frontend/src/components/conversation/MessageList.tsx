import React, { useEffect, useRef } from 'react';
import { useConversationStore } from '../../store';
import { Message } from '../../types';
import { clsx } from 'clsx';

interface MessageListProps {
  className?: string;
}

const MessageBubble: React.FC<{ message: Message }> = ({ message }) => {
  const isUser = message.role === 'user';
  const isSystem = message.role === 'system';

  return (
    <div
      className={clsx(
        'flex w-full mb-4',
        isUser ? 'justify-end' : 'justify-start'
      )}
    >
      <div
        className={clsx(
          'max-w-[80%] rounded-2xl px-4 py-3',
          isUser
            ? 'bg-indigo-600 text-white'
            : isSystem
            ? 'bg-gray-200 text-gray-700'
            : 'bg-white border border-gray-200 text-gray-900'
        )}
      >
        <div className="text-sm whitespace-pre-wrap">{message.content}</div>
        <div
          className={clsx(
            'text-xs mt-2',
            isUser ? 'text-indigo-200' : 'text-gray-400'
          )}
        >
          {new Date(message.timestamp).toLocaleTimeString()}
          {message.status && (
            <span className="ml-2">
              {message.status === 'sending' && '发送中...'}
              {message.status === 'sent' && '已发送'}
              {message.status === 'error' && '发送失败'}
            </span>
          )}
        </div>
      </div>
    </div>
  );
};

export const MessageList: React.FC<MessageListProps> = ({ className }) => {
  const { messages, isLoading } = useConversationStore();
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  if (isLoading && messages.length === 0) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-gray-500">加载中...</div>
      </div>
    );
  }

  if (messages.length === 0) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center text-gray-500">
          <div className="text-4xl mb-4">💬</div>
          <div>开始新的对话</div>
          <div className="text-sm mt-2">发送消息开始与 AI 助手交流</div>
        </div>
      </div>
    );
  }

  return (
    <div className={clsx('flex-1 overflow-y-auto p-4', className)}>
      {messages.map((message) => (
        <MessageBubble key={message.id} message={message} />
      ))}
      <div ref={messagesEndRef} />
    </div>
  );
};

export default MessageList;
