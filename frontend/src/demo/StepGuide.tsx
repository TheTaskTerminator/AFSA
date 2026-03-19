import React, { useState, useEffect } from 'react';
import { clsx } from 'clsx';
import {
  Play,
  CheckCircle,
  ChevronRight,
  RotateCcw,
  Code,
  Eye,
  FileText,
} from 'lucide-react';

interface Step {
  id: number;
  title: string;
  description: string;
  icon: React.ReactNode;
}

interface StepGuideProps {
  currentStep: number;
  totalSteps: number;
  onStepComplete?: () => void;
  onNext?: () => void;
  onRestart?: () => void;
}

const steps: Step[] = [
  {
    id: 1,
    title: '打开演示页面',
    description: '点击"进入演示模式"按钮，切换到演示引导模式',
    icon: <Play className="w-5 h-5" />,
  },
  {
    id: 2,
    title: '输入需求',
    description: '在对话输入框中输入："给订单列表添加一个批量导出按钮"',
    icon: <FileText className="w-5 h-5" />,
  },
  {
    id: 3,
    title: 'AI 需求澄清',
    description: '与 PM Agent 进行多轮对话，确认需求细节',
    icon: <Code className="w-5 h-5" />,
  },
  {
    id: 4,
    title: '查看任务卡',
    description: '查看自动生成的结构化任务卡',
    icon: <FileText className="w-5 h-5" />,
  },
  {
    id: 5,
    title: '代码生成',
    description: '实时查看 AI 生成代码的过程',
    icon: <Code className="w-5 h-5" />,
  },
  {
    id: 6,
    title: '预览效果',
    description: '查看代码差异和 UI 预览',
    icon: <Eye className="w-5 h-5" />,
  },
  {
    id: 7,
    title: '演示完成',
    description: '查看演示总结和关键指标',
    icon: <CheckCircle className="w-5 h-5" />,
  },
];

export const StepGuide: React.FC<StepGuideProps> = ({
  currentStep,
  totalSteps,
  onStepComplete,
  onNext,
  onRestart,
}) => {
  const progress = (currentStep / totalSteps) * 100;

  return (
    <div className="bg-white rounded-lg border border-gray-200 p-6 shadow-sm">
      {/* 进度条 */}
      <div className="mb-6">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-medium text-gray-700">
            演示进度
          </span>
          <span className="text-sm text-gray-500">
            步骤 {currentStep} / {totalSteps}
          </span>
        </div>
        <div className="w-full bg-gray-200 rounded-full h-2">
          <div
            className="bg-indigo-600 h-2 rounded-full transition-all duration-500"
            style={{ width: `${progress}%` }}
          />
        </div>
      </div>

      {/* 步骤列表 */}
      <div className="space-y-3">
        {steps.map((step, index) => {
          const isCompleted = index + 1 < currentStep;
          const isCurrent = index + 1 === currentStep;
          const isUpcoming = index + 1 > currentStep;

          return (
            <div
              key={step.id}
              className={clsx(
                'flex items-start gap-3 p-3 rounded-lg transition-all duration-200',
                isCurrent && 'bg-indigo-50 border border-indigo-200',
                isCompleted && 'bg-green-50',
                isUpcoming && 'opacity-50'
              )}
            >
              <div
                className={clsx(
                  'p-2 rounded-lg',
                  isCompleted && 'bg-green-100 text-green-600',
                  isCurrent && 'bg-indigo-100 text-indigo-600',
                  isUpcoming && 'bg-gray-100 text-gray-400'
                )}
              >
                {isCompleted ? (
                  <CheckCircle className="w-5 h-5" />
                ) : (
                  step.icon
                )}
              </div>

              <div className="flex-1">
                <h3
                  className={clsx(
                    'font-medium text-sm',
                    isCompleted && 'text-green-700',
                    isCurrent && 'text-indigo-700',
                    isUpcoming && 'text-gray-500'
                  )}
                >
                  {step.title}
                </h3>
                <p className="text-xs text-gray-500 mt-1">
                  {step.description}
                </p>
              </div>

              {isCurrent && (
                <ChevronRight className="w-5 h-5 text-indigo-600 animate-pulse" />
              )}
            </div>
          );
        })}
      </div>

      {/* 操作按钮 */}
      <div className="flex items-center justify-between mt-6 pt-6 border-t border-gray-200">
        <button
          onClick={onRestart}
          className="inline-flex items-center gap-2 px-4 py-2 text-sm text-gray-600 hover:text-gray-900 transition-colors"
        >
          <RotateCcw className="w-4 h-4" />
          重新开始
        </button>

        {currentStep < totalSteps ? (
          <button
            onClick={onNext}
            className="inline-flex items-center gap-2 px-6 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors"
          >
            下一步
            <ChevronRight className="w-4 h-4" />
          </button>
        ) : (
          <button
            onClick={onRestart}
            className="inline-flex items-center gap-2 px-6 py-2 bg-green-600 text-white rounded-lg hover:bg-green-700 transition-colors"
          >
            <CheckCircle className="w-4 h-4" />
            演示完成
          </button>
        )}
      </div>
    </div>
  );
};

export default StepGuide;
