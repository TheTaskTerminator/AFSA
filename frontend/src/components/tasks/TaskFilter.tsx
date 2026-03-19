import React from 'react';
import { useTaskStore } from '../../store';
import { Task } from '../../types';
import { clsx } from 'clsx';
import {
  Circle,
  Play,
  CheckCircle,
  AlertCircle,
  ListFilter,
} from 'lucide-react';

interface TaskFilterProps {
  className?: string;
}

const filterOptions: Array<{
  value: Task['status'] | 'all';
  label: string;
  icon: React.ComponentType<{ className?: string }>;
  color: string;
}> = [
  { value: 'all', label: '全部', icon: ListFilter, color: 'text-gray-600' },
  { value: 'pending', label: '等待中', icon: Circle, color: 'text-gray-500' },
  { value: 'in_progress', label: '进行中', icon: Play, color: 'text-blue-500' },
  { value: 'completed', label: '已完成', icon: CheckCircle, color: 'text-green-500' },
  { value: 'failed', label: '失败', icon: AlertCircle, color: 'text-red-500' },
];

export const TaskFilter: React.FC<TaskFilterProps> = ({ className }) => {
  const { filter, setFilter } = useTaskStore();

  return (
    <div className={clsx('flex items-center gap-2', className)}>
      <span className="text-sm text-gray-500 mr-2">筛选:</span>
      {filterOptions.map((option) => {
        const Icon = option.icon;
        const isActive = filter === option.value;
        
        return (
          <button
            key={option.value}
            onClick={() => setFilter(option.value)}
            className={clsx(
              'inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium',
              'transition-all duration-200',
              isActive
                ? 'bg-indigo-100 text-indigo-700 ring-2 ring-indigo-500'
                : 'bg-white text-gray-600 hover:bg-gray-50 border border-gray-200'
            )}
          >
            <Icon className={clsx('w-4 h-4', option.color)} />
            {option.label}
          </button>
        );
      })}
    </div>
  );
};

export default TaskFilter;
