import { create } from 'zustand';
import { CodeChange, UIChange } from '../types';

interface UIState {
  // 侧边栏状态
  isSidebarOpen: boolean;
  
  // 预览区状态
  showPreview: boolean;
  previewMode: 'code' | 'ui' | 'diff';
  
  // 代码变更
  codeChanges: CodeChange[];
  selectedChangeId: string | null;
  
  // UI 变更
  uiChanges: UIChange[];
  
  // 布局状态
  isTaskPanelOpen: boolean;
  
  // Actions
  toggleSidebar: () => void;
  setSidebarOpen: (open: boolean) => void;
  togglePreview: () => void;
  setPreviewMode: (mode: 'code' | 'ui' | 'diff') => void;
  addCodeChange: (change: CodeChange) => void;
  setSelectedChange: (id: string | null) => void;
  addUIChange: (change: UIChange) => void;
  toggleTaskPanel: () => void;
  clearChanges: () => void;
}

export const useUIStore = create<UIState>((set) => ({
  isSidebarOpen: true,
  showPreview: false,
  previewMode: 'code',
  codeChanges: [],
  selectedChangeId: null,
  uiChanges: [],
  isTaskPanelOpen: true,
  
  toggleSidebar: () => set((state) => ({ isSidebarOpen: !state.isSidebarOpen })),
  setSidebarOpen: (open) => set({ isSidebarOpen: open }),
  
  togglePreview: () => set((state) => ({ showPreview: !state.showPreview })),
  setPreviewMode: (mode) => set({ previewMode: mode }),
  
  addCodeChange: (change) => set((state) => ({
    codeChanges: [change, ...state.codeChanges]
  })),
  
  setSelectedChange: (id) => set({ selectedChangeId: id }),
  
  addUIChange: (change) => set((state) => ({
    uiChanges: [change, ...state.uiChanges]
  })),
  
  toggleTaskPanel: () => set((state) => ({ isTaskPanelOpen: !state.isTaskPanelOpen })),
  
  clearChanges: () => set({ codeChanges: [], uiChanges: [], selectedChangeId: null }),
}));
