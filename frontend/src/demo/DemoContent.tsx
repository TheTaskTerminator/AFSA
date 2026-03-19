import React, { useState, useEffect } from 'react';
import { clsx } from 'clsx';
import {
  MessageSquare,
  Send,
  Bot,
  User,
  Sparkles,
  CheckCircle,
  Clock,
  Code,
  FileText,
  Play,
} from 'lucide-react';

interface DemoMessage {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: string;
  agent?: string;
  type?: 'text' | 'code_generation' | 'test_result' | 'task_created' | 'task_completed';
}

interface DemoContentProps {
  currentStep: number;
  onStepComplete: () => void;
}

const demoMessages: Record<number, DemoMessage[]> = {
  1: [
    {
      id: 'step1-1',
      role: 'system',
      content: '👋 欢迎使用 AFSA 演示！\n\n我将引导您体验"用户说→界面变"的核心功能。\n\n请点击下方输入框，开始演示。',
      timestamp: new Date().toISOString(),
    },
  ],
  2: [
    {
      id: 'step2-1',
      role: 'user',
      content: '给订单列表添加一个批量导出按钮，支持导出为 Excel 格式',
      timestamp: new Date().toISOString(),
    },
    {
      id: 'step2-2',
      role: 'assistant',
      content: '正在分析您的需求...',
      timestamp: new Date().toISOString(),
      agent: 'pm-agent',
    },
  ],
  3: [
    {
      id: 'step3-1',
      role: 'assistant',
      content: '🤖 PM Agent: 我理解您想为订单列表添加批量导出功能。\n\n为了更准确地实现您的需求，我想确认几个细节：\n\n1. 导出范围：导出当前页数据还是全部订单？\n2. 导出字段：需要包含哪些字段？（订单号、客户名、金额、状态、创建时间）\n3. 权限控制：是否需要限制特定角色才能使用导出功能？\n\n您可以直接回答，或说"使用默认设置"继续。',
      timestamp: new Date().toISOString(),
      agent: 'pm-agent',
    },
    {
      id: 'step3-2',
      role: 'user',
      content: '使用默认设置',
      timestamp: new Date().toISOString(),
    },
  ],
  4: [
    {
      id: 'step4-1',
      role: 'assistant',
      content: '好的，我将使用以下默认设置：\n\n✓ 导出范围：当前筛选条件下的全部订单\n✓ 导出字段：订单号、客户名、金额、状态、创建时间\n✓ 权限控制：登录用户均可使用\n\n正在生成任务卡...',
      timestamp: new Date().toISOString(),
      agent: 'pm-agent',
    },
    {
      id: 'step4-2',
      role: 'system',
      content: '✅ 任务卡 #TASK-DEMO-001 已创建',
      timestamp: new Date().toISOString(),
      type: 'task_created',
    },
  ],
  5: [
    {
      id: 'step5-1',
      role: 'assistant',
      content: '🔨 正在生成代码...\n\n[✓] 生成后端 API: orders/export.py (120 行)\n[✓] 生成前端组件：OrderExportButton.tsx (45 行)\n[✓] 生成类型定义：types/order.ts (15 行)\n[✓] 更新路由配置：routes.ts',
      timestamp: new Date().toISOString(),
      agent: 'dev-agent',
      type: 'code_generation',
    },
  ],
  6: [
    {
      id: 'step6-1',
      role: 'assistant',
      content: '🧪 正在沙箱验证...\n\n[✓] 代码语法检查通过\n[✓] 单元测试通过 (8/8)\n[✓] API 集成测试通过\n\n✅ 代码生成完成！准备部署预览...',
      timestamp: new Date().toISOString(),
      agent: 'test-agent',
      type: 'test_result',
    },
  ],
  7: [
    {
      id: 'step7-1',
      role: 'system',
      content: '🎉 演示完成！\n\n本次演示展示了 AFSA 的核心能力：\n\n✓ 自然语言需求理解\n✓ 智能对话澄清\n✓ 自动任务卡生成\n✓ 代码自动生成\n✓ 沙箱验证\n✓ 实时预览\n\n从需求到代码，仅需 3 分钟！\n\n关键指标：\n• 生成文件：4 个\n• 代码行数：220 行\n• 通过测试：12 个\n• 总耗时：180 秒',
      timestamp: new Date().toISOString(),
      type: 'task_completed',
    },
  ],
};

export const DemoContent: React.FC<DemoContentProps> = ({
  currentStep,
  onStepComplete,
}) => {
  const [messages, setMessages] = useState<DemoMessage[]>([]);
  const [isTyping, setIsTyping] = useState(false);
  const [messageIndex, setMessageIndex] = useState(0);

  useEffect(() => {
    const stepMessages = demoMessages[currentStep] || [];
    setMessages([]);
    setMessageIndex(0);

    if (stepMessages.length > 0) {
      displayMessagesSequentially(stepMessages);
    }
  }, [currentStep]);

  const displayMessagesSequentially = async (msgs: DemoMessage[]) => {
    for (let i = 0; i < msgs.length; i++) {
      setIsTyping(true);
      await new Promise((resolve) => setTimeout(resolve, 800 + Math.random() * 500));
      setIsTyping(false);
      setMessages((prev) => [...prev, msgs[i]]);
      setMessageIndex(i + 1);
    }

    // 自动完成步骤
    setTimeout(() => {
      onStepComplete();
    }, 1500);
  };

  return (
    <div className="flex-1 flex flex-col min-w-0 bg-gray-50">
      {/* 消息列表 */}
      <div className="flex-1 overflow-y-auto p-6">
        <div className="max-w-3xl mx-auto space-y-4">
          {messages.map((message) => (
            <DemoMessageBubble key={message.id} message={message} />
          ))}

          {isTyping && (
            <div className="flex items-center gap-2 text-gray-500">
              <div className="flex gap-1">
                <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" />
                <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce delay-100" />
                <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce delay-200" />
              </div>
              <span className="text-sm">AI 正在思考...</span>
            </div>
          )}
        </div>
      </div>

      {/* 输入框（演示用，只读） */}
      <div className="border-t border-gray-200 bg-white p-4">
        <div className="max-w-3xl mx-auto">
          <div className="flex items-center gap-3 bg-gray-100 rounded-lg px-4 py-3">
            <input
              type="text"
              value={currentStep === 2 ? '给订单列表添加一个批量导出按钮，支持导出为 Excel 格式' : ''}
              readOnly
              className="flex-1 bg-transparent outline-none text-gray-700"
              placeholder={currentStep === 1 ? '点击"下一步"开始演示...' : ''}
            />
            <button
              className="p-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors"
              disabled
            >
              <Send className="w-5 h-5" />
            </button>
          </div>
          <p className="text-xs text-gray-500 mt-2 text-center">
            💡 演示模式下，消息将自动展示
          </p>
        </div>
      </div>
    </div>
  );
};

const DemoMessageBubble: React.FC<{ message: DemoMessage }> = ({ message }) => {
  const isUser = message.role === 'user';
  const isSystem = message.role === 'system';
  const isAssistant = message.role === 'assistant';

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
            ? 'bg-green-100 text-green-800 border border-green-200'
            : 'bg-white border border-gray-200 text-gray-900'
        )}
      >
        {/* Agent 标识 */}
        {isAssistant && message.agent && (
          <div className="flex items-center gap-2 mb-2 text-xs text-gray-500">
            <Bot className="w-4 h-4" />
            <span className="font-medium">{message.agent}</span>
          </div>
        )}

        {/* 系统消息图标 */}
        {isSystem && (
          <div className="flex items-center gap-2 mb-2">
            {message.type === 'task_created' && (
              <FileText className="w-4 h-4 text-green-600" />
            )}
            {message.type === 'task_completed' && (
              <CheckCircle className="w-4 h-4 text-green-600" />
            )}
          </div>
        )}

        {/* 消息内容 */}
        <div className="text-sm whitespace-pre-wrap">{message.content}</div>

        {/* 时间戳 */}
        <div
          className={clsx(
            'text-xs mt-2',
            isUser ? 'text-indigo-200' : 'text-gray-400'
          )}
        >
          {new Date(message.timestamp).toLocaleTimeString()}
        </div>
      </div>
    </div>
  );
};

export default DemoContent;
