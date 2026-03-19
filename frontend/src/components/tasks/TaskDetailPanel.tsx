import React from 'react';
import { useTaskStore } from '../../store';
import { clsx } from 'clsx';
import {
  X,
  Clock,
  Calendar,
  CheckCircle,
  AlertCircle,
  Play,
  Circle,
  Trash2,
} from 'lucide-react';

interface TaskDetailPanelProps {
  className?: string;
  onClose?: () => void;
}

const statusConfig = {
  pending: {
    icon: Circle,
    label: '等待中',
    color: 'text-gray-500 bg-gray-100',
  },
  in_progress: {
    icon: Play,
    label: '进行中',
    color: 'text-blue-500 bg-blue-100',
  },
  completed: {
    icon: CheckCircle,
    label: '已完成',
    color: 'text-green-500 bg-green-100',
  },
  failed: {
    icon: AlertCircle,
    label: '失败',
    color: 'text-red-500 bg-red-100',
  },
};

export const TaskDetailPanel: React.FC<TaskDetailPanelProps> = ({
  className,
  onClose,
}) => {
  const { selectedTaskId, tasks, deleteTask, setSelectedTask } = useTaskStore();
  
  const task = tasks.find((t) => t.id === selectedTaskId);

  if (!task) {
    return (
      <div className={clsx('p-6 text-center text-gray-500', className)}>
        <Clock className="w-12 h-12 text-gray-300 mx-auto mb-4" />
        <p>请选择一个任务查看详情</p>
      </div>
    );
  }

  const StatusIcon = statusConfig[task.status].icon;

  const handleDelete = () => {
    if (confirm('确定要删除这个任务吗？')) {
      deleteTask(task.id);
      onClose?.();
    }
  };

  return (
    <div className={clsx('flex flex-col h-full', className)}>
      {/* 头部 */}
      <div className="flex items-center justify-between p-4 border-b border-gray-200">
        <h3 className="text-lg font-semibold text-gray-900">任务详情</h3>
        <div className="flex items-center gap-2">
          <button
            onClick={handleDelete}
            className="p-2 text-gray-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
            title="删除任务"
          >
            <Trash2 className="w-5 h-5" />
          </button>
          <button
            onClick={() => {
              setSelectedTask(null);
              onClose?.();
            }}
            className="p-2 text-gray-400 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
      </div>

      {/* 内容 */}
      <div className="flex-1 overflow-y-auto p-4 space-y-6">
        {/* 标题和状态 */}
        <div>
          <h2 className="text-xl font-bold text-gray-900 mb-3">{task.title}</h2>
          <div className="flex items-center gap-3">
            <span
              className={clsx(
                'inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-sm font-medium',
                statusConfig[task.status].color
              )}
            >
              <StatusIcon className="w-4 h-4" />
              {statusConfig[task.status].label}
            </span>
          </div>
        </div>

        {/* 描述 */}
        <div>
          <h4 className="text-sm font-medium text-gray-700 mb-2">描述</h4>
          <p className="text-gray-600 whitespace-pre-wrap">{task.description}</p>
        </div>

        {/* 进度 */}
        {task.status === 'in_progress' && (
          <div>
            <h4 className="text-sm font-medium text-gray-700 mb-2">进度</h4>
            <div className="space-y-2">
              <div className="flex items-center justify-between text-sm text-gray-500">
                <span>完成度</span>
                <span className="font-medium">{task.progress}%</span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-3">
                <div
                  className="bg-indigo-600 h-3 rounded-full transition-all duration-300"
                  style={{ width: `${task.progress}%` }}
                />
              </div>
            </div>
          </div>
        )}

        {/* 结果 */}
        {task.result && (
          <div>
            <h4 className="text-sm font-medium text-gray-700 mb-2">结果</h4>
            <div className="bg-gray-50 rounded-lg p-4">
              <pre className="text-sm text-gray-700 whitespace-pre-wrap overflow-x-auto">
                {task.result}
              </pre>
            </div>
          </div>
        )}

        {/* 时间信息 */}
        <div className="pt-4 border-t border-gray-200 space-y-3">
          <div className="flex items-center gap-3 text-sm text-gray-500">
            <Calendar className="w-4 h-4" />
            <span>创建时间：</span>
            <span>{new Date(task.createdAt).toLocaleString('zh-CN')}</span>
          </div>
          <div className="flex items-center gap-3 text-sm text-gray-500">
            <Clock className="w-4 h-4" />
            <span>更新时间：</span>
            <span>{new Date(task.updatedAt).toLocaleString('zh-CN')}</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default TaskDetailPanel;
