import React, { useState } from 'react';
import { useConversationStore } from '../../store';
import { clsx } from 'clsx';
import {
  MessageSquare,
  Plus,
  Trash2,
  Search,
  X,
  Menu,
} from 'lucide-react';

interface ConversationSidebarProps {
  isOpen: boolean;
  onClose: () => void;
  className?: string;
}

export const ConversationSidebar: React.FC<ConversationSidebarProps> = ({
  isOpen,
  onClose,
  className,
}) => {
  const {
    conversations,
    currentConversationId,
    setCurrentConversation,
    deleteConversation,
    createConversation,
  } = useConversationStore();
  
  const [searchQuery, setSearchQuery] = useState('');

  const filteredConversations = conversations.filter((conv) =>
    conv.title.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const handleNewConversation = () => {
    const title = `新对话 ${new Date().toLocaleDateString()}`;
    createConversation(title);
  };

  const handleDeleteConversation = (
    e: React.MouseEvent,
    id: string
  ) => {
    e.stopPropagation();
    if (confirm('确定要删除这个对话吗？')) {
      deleteConversation(id);
    }
  };

  return (
    <>
      {/* 移动端遮罩层 */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/50 z-40 lg:hidden"
          onClick={onClose}
        />
      )}

      {/* 侧边栏 */}
      <aside
        className={clsx(
          'fixed lg:static inset-y-0 left-0 z-50',
          'w-72 bg-white border-r border-gray-200',
          'flex flex-col',
          'transform transition-transform duration-300 ease-in-out',
          isOpen ? 'translate-x-0' : '-translate-x-full lg:translate-x-0',
          'lg:transform-none',
          className
        )}
      >
        {/* 头部 */}
        <div className="p-4 border-b border-gray-200">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-gray-900">对话历史</h2>
            <div className="flex items-center gap-2">
              <button
                onClick={handleNewConversation}
                className="p-2 text-indigo-600 hover:bg-indigo-50 rounded-lg transition-colors"
                title="新建对话"
              >
                <Plus className="w-5 h-5" />
              </button>
              <button
                onClick={onClose}
                className="p-2 text-gray-400 hover:bg-gray-100 rounded-lg lg:hidden"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
          </div>

          {/* 搜索框 */}
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-400" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="搜索对话..."
              className="w-full pl-10 pr-4 py-2 border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
            />
          </div>
        </div>

        {/* 对话列表 */}
        <div className="flex-1 overflow-y-auto p-2">
          {filteredConversations.length === 0 ? (
            <div className="text-center py-8 text-gray-500 text-sm">
              {searchQuery ? '没有找到匹配的对话' : '暂无对话'}
            </div>
          ) : (
            filteredConversations.map((conv) => (
              <div
                key={conv.id}
                onClick={() => {
                  setCurrentConversation(conv.id);
                  if (window.innerWidth < 1024) {
                    onClose();
                  }
                }}
                className={clsx(
                  'group flex items-center gap-3 p-3 rounded-lg cursor-pointer',
                  'transition-colors duration-200',
                  currentConversationId === conv.id
                    ? 'bg-indigo-50 text-indigo-900'
                    : 'hover:bg-gray-100 text-gray-700'
                )}
              >
                <MessageSquare
                  className={clsx(
                    'w-5 h-5 flex-shrink-0',
                    currentConversationId === conv.id
                      ? 'text-indigo-600'
                      : 'text-gray-400'
                  )}
                />
                <div className="flex-1 min-w-0">
                  <div className="text-sm font-medium truncate">
                    {conv.title}
                  </div>
                  <div className="text-xs text-gray-400 truncate">
                    {conv.messages.length} 条消息
                  </div>
                </div>
                <button
                  onClick={(e) => handleDeleteConversation(e, conv.id)}
                  className="opacity-0 group-hover:opacity-100 p-1 text-gray-400 hover:text-red-600 transition-all"
                >
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            ))
          )}
        </div>

        {/* 底部信息 */}
        <div className="p-4 border-t border-gray-200 text-xs text-gray-400 text-center">
          {conversations.length} 个对话
        </div>
      </aside>
    </>
  );
};

export default ConversationSidebar;
