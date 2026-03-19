import React, { useMemo } from 'react';
import { useUIStore } from '../../store';
import { clsx } from 'clsx';
import { FileCode, X } from 'lucide-react';

interface CodePreviewProps {
  className?: string;
}

// 简单的代码高亮函数（实际项目中可以使用 Prism.js 或 highlight.js）
const highlightCode = (code: string, isDiff?: boolean): React.ReactNode => {
  const lines = code.split('\n');
  
  return lines.map((line, index) => {
    let lineClass = 'text-gray-700';
    let prefix = '';
    
    if (isDiff) {
      if (line.startsWith('+')) {
        lineClass = 'text-green-700 bg-green-50';
        prefix = '+';
      } else if (line.startsWith('-')) {
        lineClass = 'text-red-700 bg-red-50';
        prefix = '-';
      } else if (line.startsWith('@@')) {
        lineClass = 'text-blue-600 font-medium';
      }
    }
    
    return (
      <div key={index} className={clsx('px-4 font-mono text-sm', lineClass)}>
        <span className="text-gray-300 select-none w-8 inline-block text-right mr-4">
          {index + 1}
        </span>
        {prefix}
        <span className="ml-1">{line.replace(/^[+\-]/, '')}</span>
      </div>
    );
  });
};

export const CodePreview: React.FC<CodePreviewProps> = ({ className }) => {
  const { codeChanges, selectedChangeId, setSelectedChange } = useUIStore();

  const selectedChange = useMemo(
    () => codeChanges.find((c) => c.id === selectedChangeId),
    [codeChanges, selectedChangeId]
  );

  if (codeChanges.length === 0) {
    return (
      <div className={clsx('flex items-center justify-center h-full', className)}>
        <div className="text-center text-gray-500">
          <FileCode className="w-12 h-12 text-gray-300 mx-auto mb-4" />
          <p>暂无代码变更</p>
          <p className="text-sm mt-2">代码变更将在这里显示</p>
        </div>
      </div>
    );
  }

  return (
    <div className={clsx('flex flex-col h-full', className)}>
      {/* 变更列表 */}
      <div className="p-4 border-b border-gray-200">
        <h3 className="text-sm font-medium text-gray-700 mb-3">代码变更</h3>
        <div className="space-y-2 max-h-48 overflow-y-auto">
          {codeChanges.map((change) => (
            <button
              key={change.id}
              onClick={() => setSelectedChange(change.id)}
              className={clsx(
                'w-full text-left p-3 rounded-lg transition-colors',
                selectedChangeId === change.id
                  ? 'bg-indigo-50 border-indigo-200 border'
                  : 'bg-gray-50 hover:bg-gray-100'
              )}
            >
              <div className="flex items-center gap-2">
                <FileCode className="w-4 h-4 text-indigo-600" />
                <span className="text-sm font-medium text-gray-900 truncate">
                  {change.filePath}
                </span>
              </div>
            </button>
          ))}
        </div>
      </div>

      {/* 代码预览 */}
      {selectedChange ? (
        <div className="flex-1 overflow-y-auto bg-white">
          <div className="p-4 border-b border-gray-200 bg-gray-50">
            <div className="flex items-center justify-between">
              <h4 className="font-medium text-gray-900">{selectedChange.filePath}</h4>
              <button
                onClick={() => setSelectedChange(null)}
                className="p-1 text-gray-400 hover:text-gray-600"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          </div>
          
          {selectedChange.diff ? (
            <div className="py-4">
              {highlightCode(selectedChange.diff, true)}
            </div>
          ) : (
            <div className="py-4">
              <div className="px-4 py-2 bg-gray-100 text-sm text-gray-600">
                新内容：
              </div>
              {highlightCode(selectedChange.newContent)}
            </div>
          )}
        </div>
      ) : (
        <div className="flex-1 flex items-center justify-center text-gray-400">
          选择一个文件查看变更
        </div>
      )}
    </div>
  );
};

export default CodePreview;
