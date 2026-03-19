import React, { useState, useEffect } from 'react';
import { clsx } from 'clsx';
import {
  MonitorPlay,
  X,
  Play,
  Pause,
  SkipForward,
  RotateCcw,
  ChevronRight,
  CheckCircle,
  Code,
  FileText,
  Eye,
  MessageSquare,
} from 'lucide-react';
import { StepGuide } from './StepGuide';
import { DemoContent } from './DemoContent';
import { DemoModeToggle, DemoControls } from './DemoModeToggle';

interface DemoPageProps {
  onClose?: () => void;
}

const TOTAL_STEPS = 7;

export const DemoPage: React.FC<DemoPageProps> = ({ onClose }) => {
  const [currentStep, setCurrentStep] = useState(1);
  const [isPlaying, setIsPlaying] = useState(false);
  const [showGuide, setShowGuide] = useState(true);

  // 自动播放逻辑
  useEffect(() => {
    if (!isPlaying || currentStep >= TOTAL_STEPS) return;

    const timers = [
      { step: 1, delay: 3000 },
      { step: 2, delay: 4000 },
      { step: 3, delay: 5000 },
      { step: 4, delay: 4000 },
      { step: 5, delay: 6000 },
      { step: 6, delay: 5000 },
      { step: 7, delay: 5000 },
    ];

    const timer = timers[currentStep - 1];
    if (timer) {
      const timeoutId = setTimeout(() => {
        if (currentStep < TOTAL_STEPS) {
          setCurrentStep((prev) => prev + 1);
        } else {
          setIsPlaying(false);
        }
      }, timer.delay);

      return () => clearTimeout(timeoutId);
    }
  }, [isPlaying, currentStep]);

  const handleNext = () => {
    if (currentStep < TOTAL_STEPS) {
      setCurrentStep((prev) => prev + 1);
    }
  };

  const handlePrevious = () => {
    if (currentStep > 1) {
      setCurrentStep((prev) => prev - 1);
    }
  };

  const handleRestart = () => {
    setCurrentStep(1);
    setIsPlaying(false);
  };

  const handleSkip = () => {
    setCurrentStep(TOTAL_STEPS);
    setIsPlaying(false);
  };

  const handlePlayPause = () => {
    setIsPlaying((prev) => !prev);
  };

  const handleStepComplete = () => {
    if (isPlaying && currentStep < TOTAL_STEPS) {
      setTimeout(() => {
        setCurrentStep((prev) => prev + 1);
      }, 1000);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-white">
      {/* 顶部导航栏 */}
      <header className="absolute top-0 left-0 right-0 h-16 bg-white border-b border-gray-200 flex items-center justify-between px-6">
        <div className="flex items-center gap-4">
          <h1 className="text-xl font-bold text-gray-900">AFSA 演示</h1>
          <div className="flex items-center gap-2 text-sm text-gray-500">
            <span className={clsx('px-2 py-1 rounded', currentStep >= 1 && 'bg-indigo-100 text-indigo-700')}>
              <MessageSquare className="w-4 h-4 inline mr-1" />
              对话
            </span>
            <ChevronRight className="w-4 h-4" />
            <span className={clsx('px-2 py-1 rounded', currentStep >= 4 && 'bg-indigo-100 text-indigo-700')}>
              <FileText className="w-4 h-4 inline mr-1" />
              任务
            </span>
            <ChevronRight className="w-4 h-4" />
            <span className={clsx('px-2 py-1 rounded', currentStep >= 5 && 'bg-indigo-100 text-indigo-700')}>
              <Code className="w-4 h-4 inline mr-1" />
              代码
            </span>
            <ChevronRight className="w-4 h-4" />
            <span className={clsx('px-2 py-1 rounded', currentStep >= 6 && 'bg-indigo-100 text-indigo-700')}>
              <Eye className="w-4 h-4 inline mr-1" />
              预览
            </span>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <button
            onClick={() => setShowGuide(!showGuide)}
            className={clsx(
              'px-4 py-2 text-sm rounded-lg transition-colors',
              showGuide
                ? 'bg-indigo-100 text-indigo-700'
                : 'text-gray-600 hover:bg-gray-100'
            )}
          >
            {showGuide ? '隐藏引导' : '显示引导'}
          </button>
          <button
            onClick={onClose}
            className="p-2 text-gray-500 hover:text-gray-900 hover:bg-gray-100 rounded-lg transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>
      </header>

      {/* 主内容区 */}
      <div className="pt-16 pb-24 h-screen flex">
        {/* 左侧对话区 */}
        <div className={clsx('flex-1 flex flex-col', showGuide ? 'max-w-4xl' : 'w-full')}>
          <DemoContent
            currentStep={currentStep}
            onStepComplete={handleStepComplete}
          />
        </div>

        {/* 右侧引导区 */}
        {showGuide && (
          <div className="w-96 border-l border-gray-200 bg-gray-50 p-6 overflow-y-auto">
            <StepGuide
              currentStep={currentStep}
              totalSteps={TOTAL_STEPS}
              onNext={handleNext}
              onRestart={handleRestart}
            />

            {/* 当前步骤详情 */}
            <div className="mt-6 p-4 bg-white rounded-lg border border-gray-200">
              <h3 className="font-medium text-gray-900 mb-2">
                步骤 {currentStep} 说明
              </h3>
              <p className="text-sm text-gray-600">
                {currentStep === 1 && '欢迎页面，准备开始演示'}
                {currentStep === 2 && '用户输入自然语言需求'}
                {currentStep === 3 && 'AI 进行需求澄清对话'}
                {currentStep === 4 && '生成结构化任务卡'}
                {currentStep === 5 && '实时展示代码生成过程'}
                {currentStep === 6 && '展示代码差异和 UI 预览'}
                {currentStep === 7 && '演示完成，展示关键指标'}
              </p>
            </div>
          </div>
        )}
      </div>

      {/* 底部控制栏 */}
      <DemoControls
        currentStep={currentStep}
        totalSteps={TOTAL_STEPS}
        isPlaying={isPlaying}
        onPlayPause={handlePlayPause}
        onNext={handleNext}
        onPrevious={handlePrevious}
        onRestart={handleRestart}
        onSkip={handleSkip}
      />
    </div>
  );
};

export default DemoPage;
