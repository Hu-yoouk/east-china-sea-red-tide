import React from 'react';
import { Outlet } from 'react-router-dom';
import Sidebar from './Sidebar';

const Layout: React.FC = () => {
  return (
    <div className="flex min-h-screen">
      <Sidebar />
      <main className="ml-60 flex-1 p-6 min-h-screen">
        <div className="mb-5 rounded-lg border border-amber-500/40 bg-amber-950/30 px-4 py-3 text-sm text-amber-200">
          历史项目展示：本网站的规则评分和历史图表不等于下一月真实模型预测。
          新预测请通过仓库技能运行，并查看生成的预测报告。
        </div>
        <div className="animate-fade-in">
          <Outlet />
        </div>
      </main>
    </div>
  );
};

export default Layout;
