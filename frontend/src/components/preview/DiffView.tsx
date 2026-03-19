import React, { useMemo } from 'react';
import { useUIStore } from '../../store';
import { clsx } from 'clsx';
import { GitCompare, ChevronRight, ChevronDown } from 'lucide-react';

interface DiffViewProps {
  className?: string;
}

// 计算简单的 diff（实际项目中可以使用 diff 库）
const computeDiff = (oldStr: string, newStr: string): Array<{
  type: 'unchanged' | 'added' | 'removed';
  value: string;
}> => {
  const oldLines = oldStr.split('\n');
  const newLines = newStr.split('\n');
  const result: Array<{ type: 'unchanged' | 'added' | 'removed'; value: string }> = [];

  // 简单的行级 diff
  const maxLen = Math.max(oldLines.length, newLines.length);
  
  for (let i = 0; i < maxLen; i++) {
    const oldLine = oldLines[i];
    const newLine = newLines[i];
    
    if (oldLine === undefined) {
      result.push({ type: 'added', value: newLine });
    } else if (newLine === undefined) {
      result.push({ type: 'removed', value: oldLine });
    } else if (oldLine === newLine) {
      result.push({ type: 'unchanged', value: oldLine });
    } else {
      result.push({ type: 'removed', value: oldLine });
      result.push({ type: 'added', value: newLine });
    }
  }

  return result;
};

interface DiffSectionProps {
  title: string;
  oldContent: string;
  newContent: string;
  defaultExpanded?: boolean;
}

const DiffSection: React.FC<DiffSectionProps> = ({
  title,
  oldContent,
  newContent,
  defaultExpanded = true,
}) => {
  const [isExpanded, setIsExpanded] = React.useState(defaultExpanded);
  
  const diff = useMemo(
    () => computeDiff(oldContent, newContent),
    [oldContent, newContent]
  );

  const stats = useMemo(() => {
    const additions = diff.filter((d) => d.type === 'added').length;
    const deletions = diff.filter((d) => d.type === 'removed').length;
    return { additions, deletions };
  }, [diff]);

  return (
    <div className="border border-gray-200 rounded-lg overflow-hidden">
      {/* 头部 */}
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="w-full flex items-center justify-between p-4 bg-gray-50 hover:bg-gray-100 transition-colors"
      >
        <div className="flex items-center gap-3">
          {isExpanded ? (
            <ChevronDown className="w-5 h-5 text-gray-500" />
          ) : (
            <ChevronRight className="w-5 h-5 text-gray-500" />
          )}
          <GitCompare className="w-5 h-5 text-indigo-600" />
          <span className="font-medium text-gray-900">{title}</span>
          <span className="text-sm text-gray-500">
            <span className="text-green-600">+{stats.additions}</span>
            {' '}
            <span className="text-red-600">-{stats.deletions}</span>
          </span>
        </div>
      </button>

      {/* 内容 */}
      {isExpanded && (
        <div className="max-h-96 overflow-y-auto bg-white">
          <div className="font-mono text-sm">
            {diff.map((line, index) => (
              <div
                key={index}
                className={clsx(
                  'px-4 py-1',
                  line.type === 'added' && 'bg-green-50 text-green-700',
                  line.type === 'removed' && 'bg-red-50 text-red-700',
                  line.type === 'unchanged' && 'text-gray-700'
                )}
              >
                <span className="text-gray-400 select-none w-6 inline-block text-right mr-4">
                  {index + 1}
                </span>
                <span className="mr-2 select-none">
                  {line.type === 'added' && '+'}
                  {line.type === 'removed' && '-'}
                  {line.type === 'unchanged' && ' '}
                </span>
                {line.value}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export const DiffView: React.FC<DiffViewProps> = ({ className }) => {
  const { codeChanges } = useUIStore();

  if (codeChanges.length === 0) {
    return (
      <div className={clsx('flex items-center justify-center h-full', className)}>
        <div className="text-center text-gray-500">
          <GitCompare className="w-12 h-12 text-gray-300 mx-auto mb-4" />
          <p>暂无差异对比</p>
          <p className="text-sm mt-2">代码变更的差异将在这里显示</p>
        </div>
      </div>
    );
  }

  return (
    <div className={clsx('space-y-4 p-4 overflow-y-auto', className)}>
      <h3 className="text-sm font-medium text-gray-700">差异对比</h3>
      
      {codeChanges.map((change) => (
        <DiffSection
          key={change.id}
          title={change.filePath}
          oldContent={change.oldContent}
          newContent={change.newContent}
        />
      ))}
    </div>
  );
};

export default DiffView;
