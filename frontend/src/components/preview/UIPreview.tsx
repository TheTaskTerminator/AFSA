import React from 'react';
import { useUIStore } from '../../store';
import { clsx } from 'clsx';
import { Layout, Eye, ExternalLink } from 'lucide-react';

interface UIPreviewProps {
  className?: string;
}

export const UIPreview: React.FC<UIPreviewProps> = ({ className }) => {
  const { uiChanges } = useUIStore();

  if (uiChanges.length === 0) {
    return (
      <div className={clsx('flex items-center justify-center h-full', className)}>
        <div className="text-center text-gray-500">
          <Layout className="w-12 h-12 text-gray-300 mx-auto mb-4" />
          <p>暂无 UI 变更</p>
          <p className="text-sm mt-2">UI 变更预览将在这里显示</p>
        </div>
      </div>
    );
  }

  return (
    <div className={clsx('space-y-4 p-4', className)}>
      <h3 className="text-sm font-medium text-gray-700">UI 变更列表</h3>
      
      <div className="space-y-4">
        {uiChanges.map((change) => (
          <div
            key={change.id}
            className="bg-white border border-gray-200 rounded-lg overflow-hidden"
          >
            {/* 变更头部 */}
            <div className="p-4 bg-gray-50 border-b border-gray-200">
              <div className="flex items-center gap-2 mb-2">
                <Layout className="w-5 h-5 text-indigo-600" />
                <h4 className="font-medium text-gray-900">{change.component}</h4>
              </div>
              <p className="text-sm text-gray-600">{change.description}</p>
            </div>
            
            {/* 预览区域 */}
            <div className="p-4">
              {change.previewUrl ? (
                <div className="relative aspect-video bg-gray-100 rounded-lg overflow-hidden">
                  <img
                    src={change.previewUrl}
                    alt={`${change.component} preview`}
                    className="w-full h-full object-cover"
                  />
                  <a
                    href={change.previewUrl}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="absolute top-2 right-2 p-2 bg-white/90 rounded-lg shadow-sm hover:bg-white transition-colors"
                  >
                    <ExternalLink className="w-4 h-4 text-gray-600" />
                  </a>
                </div>
              ) : (
                <div className="aspect-video bg-gray-100 rounded-lg flex items-center justify-center">
                  <div className="text-center text-gray-400">
                    <Eye className="w-8 h-8 mx-auto mb-2" />
                    <span className="text-sm">预览图加载中</span>
                  </div>
                </div>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default UIPreview;
