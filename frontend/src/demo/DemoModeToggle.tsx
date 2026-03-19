import React, { useState } from 'react';
import { clsx } from 'clsx';
import {
  Play,
  Pause,
  SkipForward,
  RotateCcw,
  MonitorPlay,
  X,
} from 'lucide-react';

interface DemoModeToggleProps {
  isDemoMode: boolean;
  onToggle: (enabled: boolean) => void;
}

export const DemoModeToggle: React.FC<DemoModeToggleProps> = ({
  isDemoMode,
  onToggle,
}) => {
  const [isHovered, setIsHovered] = useState(false);

  return (
    <div
      className={clsx(
        'fixed top-4 right-4 z-50 transition-all duration-300',
        isDemoMode ? 'scale-100' : 'scale-100'
      )}
      onMouseEnter={() => setIsHovered(true)}
      onMouseLeave={() => setIsHovered(false)}
    >
      {isDemoMode ? (
        <div className="flex items-center gap-2 bg-indigo-600 text-white px-4 py-2 rounded-full shadow-lg">
          <MonitorPlay className="w-5 h-5 animate-pulse" />
          <span className="text-sm font-medium">演示模式中</span>
          <button
            onClick={() => onToggle(false)}
            className="ml-2 p-1 hover:bg-indigo-500 rounded-full transition-colors"
            title="退出演示模式"
          >
            <X className="w-4 h-4" />
          </button>
        </div>
      ) : (
        <button
          onClick={() => onToggle(true)}
          className={clsx(
            'inline-flex items-center gap-2 px-6 py-3 rounded-full shadow-lg transition-all duration-300',
            isHovered
              ? 'bg-indigo-700 scale-105'
              : 'bg-indigo-600 hover:bg-indigo-700',
            'text-white font-medium'
          )}
        >
          <MonitorPlay className="w-5 h-5" />
          进入演示模式
        </button>
      )}
    </div>
  );
};

interface DemoControlsProps {
  currentStep: number;
  totalSteps: number;
  isPlaying: boolean;
  onPlayPause: () => void;
  onNext: () => void;
  onPrevious: () => void;
  onRestart: () => void;
  onSkip: () => void;
}

export const DemoControls: React.FC<DemoControlsProps> = ({
  currentStep,
  totalSteps,
  isPlaying,
  onPlayPause,
  onNext,
  onPrevious,
  onRestart,
  onSkip,
}) => {
  return (
    <div className="fixed bottom-6 left-1/2 transform -translate-x-1/2 z-50">
      <div className="flex items-center gap-2 bg-white rounded-full shadow-xl border border-gray-200 px-6 py-3">
        <button
          onClick={onRestart}
          className="p-2 text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-full transition-colors"
          title="重新开始"
        >
          <RotateCcw className="w-5 h-5" />
        </button>

        <button
          onClick={onPrevious}
          disabled={currentStep <= 1}
          className="p-2 text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-full transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
          title="上一步"
        >
          <SkipForward className="w-5 h-5 rotate-180" />
        </button>

        <button
          onClick={onPlayPause}
          className={clsx(
            'p-3 rounded-full transition-colors',
            isPlaying
              ? 'bg-indigo-100 text-indigo-600'
              : 'bg-indigo-600 text-white hover:bg-indigo-700'
          )}
          title={isPlaying ? '暂停' : '播放'}
        >
          {isPlaying ? (
            <Pause className="w-6 h-6" />
          ) : (
            <Play className="w-6 h-6 ml-0.5" />
          )}
        </button>

        <button
          onClick={onNext}
          disabled={currentStep >= totalSteps}
          className="p-2 text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-full transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
          title="下一步"
        >
          <SkipForward className="w-5 h-5" />
        </button>

        <button
          onClick={onSkip}
          className="px-4 py-2 text-sm text-gray-600 hover:text-gray-900 hover:bg-gray-100 rounded-full transition-colors"
        >
          跳过演示
        </button>

        <div className="ml-4 pl-4 border-l border-gray-200">
          <span className="text-sm text-gray-600">
            步骤 <span className="font-medium text-gray-900">{currentStep}</span> / {totalSteps}
          </span>
        </div>
      </div>
    </div>
  );
};

export default DemoModeToggle;
