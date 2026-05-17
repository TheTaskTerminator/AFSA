import React from 'react';
import { useTaskStore } from '../../store';
import { Task, TaskStatus } from '../../types';
import { clsx } from 'clsx';
import {
  CheckCircle,
  Clock,
  AlertCircle,
  Play,
  Circle,
} from 'lucide-react';

interface TaskListProps {
  className?: string;
  onTaskSelect?: (task: Task) => void;
}

const statusIcons: Record<TaskStatus, React.ComponentType<{ className?: string }>> = {
  pending: Circle,
  queued: Clock,
  running: Play,
  verifying: Play,
  completed: CheckCircle,
  failed: AlertCircle,
  cancelled: AlertCircle,
  timeout: AlertCircle,
};

const statusColors: Record<TaskStatus, string> = {
  pending: 'text-gray-500 bg-gray-100',
  queued: 'text-gray-500 bg-gray-100',
  running: 'text-blue-500 bg-blue-100',
  verifying: 'text-indigo-500 bg-indigo-100',
  completed: 'text-green-500 bg-green-100',
  failed: 'text-red-500 bg-red-100',
  cancelled: 'text-yellow-600 bg-yellow-100',
  timeout: 'text-orange-600 bg-orange-100',
};

const statusLabels: Record<TaskStatus, string> = {
  pending: '等待中',
  queued: '队列中',
  running: '运行中',
  verifying: '验证中',
  completed: '已完成',
  failed: '失败',
  cancelled: '已取消',
  timeout: '超时',
};

const isActiveTask = (status: TaskStatus) => status === 'running' || status === 'verifying';
const getTaskTitle = (task: Task) => task.description.split('\n')[0] || task.id;
const getTaskProgress = (task: Task) => {
  if (task.status === 'completed') return 100;
  if (task.status === 'verifying') return 80;
  if (task.status === 'running') return 50;
  return 0;
};
const getTaskTimestamp = (task: Task) =>
  task.completedAt ??
  (task.completed_at ? Date.parse(task.completed_at) : undefined) ??
  task.startedAt ??
  (task.started_at ? Date.parse(task.started_at) : undefined) ??
  task.createdAt ??
  (task.created_at ? Date.parse(task.created_at) : Date.now());

const TaskItem: React.FC<{ task: Task; onSelect: (task: Task) => void }> = ({
  task,
  onSelect,
}) => {
  const Icon = statusIcons[task.status];

  return (
    <div
      onClick={() => onSelect(task)}
      className={clsx(
        'p-4 rounded-lg border cursor-pointer transition-all duration-200',
        'hover:shadow-md hover:border-indigo-300',
        task.status === 'completed' ? 'bg-gray-50' : 'bg-white'
      )}
    >
      <div className="flex items-start gap-3">
        <div
          className={clsx(
            'p-2 rounded-lg',
            statusColors[task.status]
          )}
        >
          <Icon className="w-5 h-5" />
        </div>
        
        <div className="flex-1 min-w-0">
          <h3 className="font-medium text-gray-900 truncate">{getTaskTitle(task)}</h3>
          <p className="text-sm text-gray-500 mt-1 line-clamp-2">
            {task.description}
          </p>
          
          {/* 进度条 */}
          {isActiveTask(task.status) && (
            <div className="mt-3">
              <div className="flex items-center justify-between text-xs text-gray-500 mb-1">
                <span>进度</span>
                <span>{getTaskProgress(task)}%</span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div
                  className="bg-indigo-600 h-2 rounded-full transition-all duration-300"
                  style={{ width: `${getTaskProgress(task)}%` }}
                />
              </div>
            </div>
          )}
          
          {/* 状态标签和时间 */}
          <div className="flex items-center justify-between mt-3">
            <span
              className={clsx(
                'inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium',
                statusColors[task.status]
              )}
            >
              {statusLabels[task.status]}
            </span>
            <span className="text-xs text-gray-400">
              {new Date(getTaskTimestamp(task)).toLocaleString()}
            </span>
          </div>
        </div>
      </div>
    </div>
  );
};

export const TaskList: React.FC<TaskListProps> = ({
  className,
  onTaskSelect,
}) => {
  const { getFilteredTasks, setSelectedTask } = useTaskStore();
  
  const tasks = getFilteredTasks();

  const handleSelectTask = (task: Task) => {
    setSelectedTask(task.id);
    onTaskSelect?.(task);
  };

  if (tasks.length === 0) {
    return (
      <div className={clsx('text-center py-12', className)}>
        <Clock className="w-12 h-12 text-gray-300 mx-auto mb-4" />
        <p className="text-gray-500">暂无任务</p>
      </div>
    );
  }

  return (
    <div className={clsx('space-y-3', className)}>
      {tasks.map((task) => (
        <TaskItem key={task.id} task={task} onSelect={handleSelectTask} />
      ))}
    </div>
  );
};

export default TaskList;
