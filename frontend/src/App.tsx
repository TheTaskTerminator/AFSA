import { useEffect, useState } from 'react';
import { useConversationStore, useTaskStore, useUIStore } from './store';
import { wsClient } from './lib/api';
import {
  MessageList,
  MessageInput,
  ConversationSidebar,
} from './components/conversation';
import {
  TaskList,
  TaskFilter,
  TaskDetailPanel,
} from './components/tasks';
import {
  CodePreview,
  UIPreview,
  DiffView,
} from './components/preview';
import {
  Menu,
  MessageSquare,
  CheckSquare,
  Eye,
  PanelLeft,
  PanelRight,
  Maximize2,
  Minimize2,
} from 'lucide-react';
import { clsx } from 'clsx';

function App() {
  const {
    currentConversationId,
    setCurrentConversation,
    conversations,
  } = useConversationStore();
  
  const { isSidebarOpen, toggleSidebar, showPreview, previewMode, setPreviewMode, togglePreview } =
    useUIStore();
  
  const { isTaskPanelOpen, toggleTaskPanel } = useUIStore();
  
  const [activeTab, setActiveTab] = useState<'conversation' | 'tasks' | 'preview'>('conversation');
  const [isMobile, setIsMobile] = useState(false);

  // 检测移动设备
  useEffect(() => {
    const checkMobile = () => {
      setIsMobile(window.innerWidth < 768);
    };
    
    checkMobile();
    window.addEventListener('resize', checkMobile);
    return () => window.removeEventListener('resize', checkMobile);
  }, []);

  // 初始化 WebSocket 连接
  useEffect(() => {
    wsClient.connect().catch(console.error);

    // 监听 WebSocket 消息
    const unsubscribe = wsClient.onMessage((message) => {
      console.log('Received WebSocket message:', message);
      
      // 根据消息类型处理
      switch (message.type) {
        case 'message':
          // 处理新消息
          break;
        case 'task_update':
          // 处理任务更新
          break;
        case 'code_change':
          // 处理代码变更
          break;
        case 'ui_change':
          // 处理 UI 变更
          break;
      }
    });

    return () => {
      unsubscribe();
      wsClient.disconnect();
    };
  }, []);

  // 自动选择第一个对话
  useEffect(() => {
    if (!currentConversationId && conversations.length > 0) {
      setCurrentConversation(conversations[0].id);
    }
  }, [conversations, currentConversationId, setCurrentConversation]);

  return (
    <div className="flex h-screen bg-gray-50">
      {/* 对话历史侧边栏 */}
      <ConversationSidebar
        isOpen={isSidebarOpen}
        onClose={toggleSidebar}
      />

      {/* 主内容区 */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* 顶部导航栏 */}
        <header className="bg-white border-b border-gray-200 px-4 py-3">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <button
                onClick={toggleSidebar}
                className="p-2 text-gray-500 hover:bg-gray-100 rounded-lg lg:hidden"
              >
                <Menu className="w-5 h-5" />
              </button>
              
              <h1 className="text-xl font-bold text-gray-900">AFSA</h1>
              
              {/* 标签切换 */}
              <div className="hidden md:flex items-center gap-1 ml-6">
                <button
                  onClick={() => setActiveTab('conversation')}
                  className={clsx(
                    'inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors',
                    activeTab === 'conversation'
                      ? 'bg-indigo-100 text-indigo-700'
                      : 'text-gray-600 hover:bg-gray-100'
                  )}
                >
                  <MessageSquare className="w-4 h-4" />
                  对话
                </button>
                <button
                  onClick={() => setActiveTab('tasks')}
                  className={clsx(
                    'inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors',
                    activeTab === 'tasks'
                      ? 'bg-indigo-100 text-indigo-700'
                      : 'text-gray-600 hover:bg-gray-100'
                  )}
                >
                  <CheckSquare className="w-4 h-4" />
                  任务
                </button>
                <button
                  onClick={() => setActiveTab('preview')}
                  className={clsx(
                    'inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium transition-colors',
                    activeTab === 'preview'
                      ? 'bg-indigo-100 text-indigo-700'
                      : 'text-gray-600 hover:bg-gray-100'
                  )}
                >
                  <Eye className="w-4 h-4" />
                  预览
                </button>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={toggleTaskPanel}
                className={clsx(
                  'p-2 rounded-lg transition-colors hidden md:block',
                  isTaskPanelOpen
                    ? 'bg-indigo-100 text-indigo-600'
                    : 'text-gray-500 hover:bg-gray-100'
                )}
                title="任务面板"
              >
                <PanelLeft className="w-5 h-5" />
              </button>
              <button
                onClick={togglePreview}
                className={clsx(
                  'p-2 rounded-lg transition-colors hidden md:block',
                  showPreview
                    ? 'bg-indigo-100 text-indigo-600'
                    : 'text-gray-500 hover:bg-gray-100'
                )}
                title="预览区"
              >
                <PanelRight className="w-5 h-5" />
              </button>
            </div>
          </div>
        </header>

        {/* 内容区 */}
        <main className="flex-1 flex overflow-hidden">
          {/* 主内容 */}
          <div className="flex-1 flex flex-col min-w-0">
            {activeTab === 'conversation' && (
              <>
                <MessageList />
                <MessageInput />
              </>
            )}
            
            {activeTab === 'tasks' && (
              <div className="flex-1 overflow-y-auto p-6">
                <div className="max-w-6xl mx-auto space-y-6">
                  <TaskFilter />
                  <TaskList />
                </div>
              </div>
            )}
            
            {activeTab === 'preview' && (
              <div className="flex-1 overflow-y-auto p-6">
                <div className="max-w-6xl mx-auto space-y-4">
                  {/* 预览模式切换 */}
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => setPreviewMode('code')}
                      className={clsx(
                        'px-4 py-2 rounded-lg text-sm font-medium transition-colors',
                        previewMode === 'code'
                          ? 'bg-indigo-100 text-indigo-700'
                          : 'bg-white text-gray-600 hover:bg-gray-100 border border-gray-200'
                      )}
                    >
                      代码
                    </button>
                    <button
                      onClick={() => setPreviewMode('ui')}
                      className={clsx(
                        'px-4 py-2 rounded-lg text-sm font-medium transition-colors',
                        previewMode === 'ui'
                          ? 'bg-indigo-100 text-indigo-700'
                          : 'bg-white text-gray-600 hover:bg-gray-100 border border-gray-200'
                      )}
                    >
                      UI
                    </button>
                    <button
                      onClick={() => setPreviewMode('diff')}
                      className={clsx(
                        'px-4 py-2 rounded-lg text-sm font-medium transition-colors',
                        previewMode === 'diff'
                          ? 'bg-indigo-100 text-indigo-700'
                          : 'bg-white text-gray-600 hover:bg-gray-100 border border-gray-200'
                      )}
                    >
                      差异
                    </button>
                  </div>
                  
                  {/* 预览内容 */}
                  <div className="bg-white rounded-lg border border-gray-200 min-h-[500px]">
                    {previewMode === 'code' && <CodePreview />}
                    {previewMode === 'ui' && <UIPreview />}
                    {previewMode === 'diff' && <DiffView />}
                  </div>
                </div>
              </div>
            )}
          </div>

          {/* 右侧任务面板 */}
          {isTaskPanelOpen && (
            <div className="w-96 border-l border-gray-200 bg-white hidden md:block">
              <TaskDetailPanel />
            </div>
          )}

          {/* 右侧预览面板 */}
          {showPreview && !isTaskPanelOpen && (
            <div className="w-96 border-l border-gray-200 bg-white hidden md:block">
              {previewMode === 'code' && <CodePreview />}
              {previewMode === 'ui' && <UIPreview />}
              {previewMode === 'diff' && <DiffView />}
            </div>
          )}
        </main>
      </div>
    </div>
  );
}

export default App;
