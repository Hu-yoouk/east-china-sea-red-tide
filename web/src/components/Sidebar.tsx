import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';

interface NavItem {
  path: string;
  label: string;
  icon: string;
}

const navItems: NavItem[] = [
  { path: '/', label: '项目总览', icon: '📊' },
  { path: '/data-processing', label: '数据处理', icon: '🔬' },
  { path: '/risk-map', label: '风险地图', icon: '🗺️' },
  { path: '/prediction', label: '风险预测', icon: '🎯' },
  { path: '/model-evaluation', label: '模型评估', icon: '📈' },
  { path: '/prediction-comparison', label: '预测对比', icon: '📉' },
  { path: '/future-trend', label: '未来趋势', icon: '🔮' },
  { path: '/feature-importance', label: '特征分析', icon: '💎' },
  { path: '/report', label: '分析报告', icon: '📋' },
  { path: '/correlation', label: '相关分析', icon: '🔗' },
  { path: '/data-import', label: '数据导入', icon: '📥' },
];

const Sidebar: React.FC = () => {
  const navigate = useNavigate();
  const location = useLocation();

  return (
    <aside className="fixed left-0 top-0 h-screen w-60 bg-ocean-950/95 backdrop-blur-md border-r border-ocean-700/40 z-50 flex flex-col">
      {/* Logo */}
      <div className="px-5 py-6 border-b border-ocean-700/40">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-lg bg-gradient-to-br from-cyan-400 to-blue-600 flex items-center justify-center text-xl shadow-lg shadow-cyan-500/30">
            🌊
          </div>
          <div>
            <h1 className="text-sm font-bold text-white leading-tight">海洋赤潮风险</h1>
            <p className="text-xs text-cyan-400">评估模型分析系统</p>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-3 py-4 overflow-y-auto">
        {navItems.map(item => {
          const isActive = location.pathname === item.path;
          return (
            <button
              key={item.path}
              onClick={() => navigate(item.path)}
              className={`w-full flex items-center gap-3 px-4 py-3 mb-1 rounded-lg text-left transition-all duration-200 ${
                isActive
                  ? 'bg-gradient-to-r from-cyan-500/20 to-blue-600/20 text-cyan-300 border border-cyan-500/30 shadow-lg shadow-cyan-500/10'
                  : 'text-gray-400 hover:text-gray-200 hover:bg-ocean-800/40'
              }`}
            >
              <span className="text-lg">{item.icon}</span>
              <span className="text-sm font-medium">{item.label}</span>
              {isActive && (
                <span className="ml-auto w-1.5 h-1.5 rounded-full bg-cyan-400 animate-pulse" />
              )}
            </button>
          );
        })}
      </nav>

      {/* Footer */}
      <div className="px-5 py-4 border-t border-ocean-700/40">
        <div className="text-xs text-gray-500">
          <p>数据要素大赛作品</p>
          <p className="mt-1">原型展示版本 v1.0</p>
        </div>
      </div>
    </aside>
  );
};

export default Sidebar;
