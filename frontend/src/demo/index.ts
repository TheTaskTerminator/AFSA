// AFSA Demo Module
// 演示模式入口文件

export { DemoPage } from './DemoPage';
export { DemoModeToggle, DemoControls } from './DemoModeToggle';
export { StepGuide } from './StepGuide';
export { DemoContent } from './DemoContent';

// 演示数据类型
export interface DemoStep {
  id: number;
  title: string;
  description: string;
  duration: number; // 毫秒
}

export interface DemoTask {
  id: string;
  title: string;
  description: string;
  requirements: DemoRequirement[];
  generatedFiles: DemoGeneratedFile[];
  testResults: DemoTestResults;
}

export interface DemoRequirement {
  type: 'ui' | 'api' | 'model';
  name: string;
  spec: Record<string, unknown>;
  constraints: Record<string, unknown>;
}

export interface DemoGeneratedFile {
  path: string;
  type: string;
  lines: number;
  content: string;
}

export interface DemoTestResults {
  unitTests: { total: number; passed: number; failed: number };
  integrationTests: { total: number; passed: number; failed: number };
  e2eTests: { total: number; passed: number; failed: number };
}

// 预设演示场景
export const DEMO_SCENARIOS = {
  export: {
    id: 'export-button',
    title: '批量导出功能',
    description: '给订单列表添加一个批量导出按钮',
    userInput: '给订单列表添加一个批量导出按钮，支持导出为 Excel 格式',
  },
  dashboard: {
    id: 'sales-dashboard',
    title: '销售数据面板',
    description: '添加一个销售数据面板',
    userInput: '给我添加一个销售数据面板，显示本月销售额和趋势图',
  },
  search: {
    id: 'advanced-search',
    title: '高级搜索',
    description: '添加高级搜索功能',
    userInput: '为用户列表添加高级搜索功能，支持多条件筛选',
  },
};

export default DemoPage;
