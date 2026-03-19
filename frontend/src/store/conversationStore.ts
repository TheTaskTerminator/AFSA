import { create } from 'zustand';
import { Message, Conversation } from '../types';

interface ConversationState {
  conversations: Conversation[];
  currentConversationId: string | null;
  messages: Message[];
  isLoading: boolean;
  error: string | null;
  
  // Actions
  setConversations: (conversations: Conversation[]) => void;
  setCurrentConversation: (id: string) => void;
  addMessage: (message: Message) => void;
  updateMessageStatus: (messageId: string, status: Message['status']) => void;
  createConversation: (title: string) => void;
  deleteConversation: (id: string) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  clearMessages: () => void;
}

export const useConversationStore = create<ConversationState>((set, get) => ({
  conversations: [],
  currentConversationId: null,
  messages: [],
  isLoading: false,
  error: null,

  setConversations: (conversations) => set({ conversations }),
  
  setCurrentConversation: (id) => {
    const conversation = get().conversations.find(c => c.id === id);
    set({ 
      currentConversationId: id,
      messages: conversation?.messages || [] 
    });
  },
  
  addMessage: (message) => set((state) => ({
    messages: [...state.messages, message],
    conversations: state.conversations.map(c => 
      c.id === state.currentConversationId
        ? { 
            ...c, 
            messages: [...c.messages, message],
            updatedAt: Date.now()
          }
        : c
    )
  })),
  
  updateMessageStatus: (messageId, status) => set((state) => ({
    messages: state.messages.map(m =>
      m.id === messageId ? { ...m, status } : m
    )
  })),
  
  createConversation: (title) => set((state) => {
    const newConversation: Conversation = {
      id: crypto.randomUUID(),
      title,
      messages: [],
      createdAt: Date.now(),
      updatedAt: Date.now(),
    };
    return {
      conversations: [newConversation, ...state.conversations],
      currentConversationId: newConversation.id,
      messages: [],
    };
  }),
  
  deleteConversation: (id) => set((state) => ({
    conversations: state.conversations.filter(c => c.id !== id),
    currentConversationId: state.currentConversationId === id ? null : state.currentConversationId,
    messages: state.currentConversationId === id ? [] : state.messages,
  })),
  
  setLoading: (loading) => set({ isLoading: loading }),
  setError: (error) => set({ error }),
  clearMessages: () => set({ messages: [] }),
}));
