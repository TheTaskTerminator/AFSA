import React from 'react';
import { useTaskStore } from '../../store';
import { Task } from '../../types';
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

const statusIcons = {
  pending: Circle,
  in_progress: Play,
  completed: CheckCircle,
  failed: AlertCircle,
};

const statusColors = {
  pending: 'text-gray-500 bg-gray-100',
  in_progress: 'text-blue-500 bg-blue-100',
  completed: 'text-green-500 bg-green-100',
  failed: 'text-red-500 bg-red-100',
};

const statusLabels = {
  pending: '等待中',
  in_progress: '进行中',
  completed: '已完成',
  failed: '失败',
};

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
          <h3 className="font-medium text-gray-900 truncate">{task.title}</h3>
          <p className="text-sm text-gray-500 mt-1 line-clamp-2">
            {task.description}
          </p>
          
          {/* 进度条 */}
          {task.status === 'in_progress' && (
            <div className="mt-3">
              <div className="flex items-center justify-between text-xs text-gray-500 mb-1">
                <span>进度</span>
                <span>{task.progress}%</span>
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2">
                <div
                  className="bg-indigo-600 h-2 rounded-full transition-all duration-300"
                  style={{ width: `${task.progress}%` }}
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
              {new Date(task.updatedAt).toLocaleString()}
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
