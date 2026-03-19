import { create } from 'zustand';
import { Task } from '../types';

interface TaskState {
  tasks: Task[];
  selectedTaskId: string | null;
  filter: Task['status'] | 'all';
  isLoading: boolean;
  error: string | null;
  
  // Actions
  setTasks: (tasks: Task[]) => void;
  addTask: (task: Task) => void;
  updateTask: (id: string, updates: Partial<Task>) => void;
  deleteTask: (id: string) => void;
  setSelectedTask: (id: string | null) => void;
  setFilter: (filter: Task['status'] | 'all') => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  getFilteredTasks: () => Task[];
}

export const useTaskStore = create<TaskState>((set, get) => ({
  tasks: [],
  selectedTaskId: null,
  filter: 'all',
  isLoading: false,
  error: null,

  setTasks: (tasks) => set({ tasks }),
  
  addTask: (task) => set((state) => ({
    tasks: [task, ...state.tasks]
  })),
  
  updateTask: (id, updates) => set((state) => ({
    tasks: state.tasks.map(t =>
      t.id === id ? { ...t, ...updates, updatedAt: Date.now() } : t
    )
  })),
  
  deleteTask: (id) => set((state) => ({
    tasks: state.tasks.filter(t => t.id !== id),
    selectedTaskId: state.selectedTaskId === id ? null : state.selectedTaskId,
  })),
  
  setSelectedTask: (id) => set({ selectedTaskId: id }),
  
  setFilter: (filter) => set({ filter }),
  
  setLoading: (loading) => set({ isLoading: loading }),
  setError: (error) => set({ error }),
  
  getFilteredTasks: () => {
    const { tasks, filter } = get();
    if (filter === 'all') return tasks;
    return tasks.filter(t => t.status === filter);
  },
}));
