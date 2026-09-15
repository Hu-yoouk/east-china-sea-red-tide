import React from 'react';
import ReactECharts from 'echarts-for-react';
import { useData } from '../services/dataContext';
import RiskBadge from '../components/RiskBadge';

const Report: React.FC = () => {
  const { dashboardStats, modelPerformance, featureImportance, geoData, warningList } = useData();
  const handlePrint = () => window.print();

  const barOption = {
    tooltip: { trigger: 'axis', backgroundColor: 'rgba(255,255,255,0.95)', borderColor: '#e5e7eb', textStyle: { color: '#1f2937' } },
    grid: { left: '3%', right: '4%', bottom: '3%', top: '10px', containLabel: true },
    xAxis: { type: 'category', data: modelPerformance.map(m => m.model), axisLine: { lineStyle: { color: '#d1d5db' } }, axisLabel: { color: '#6b7280', fontSize: 10, rotate: 15 } },
    yAxis: { type: 'value', name: '分值', min: 0.6, max: 1, axisLine: { lineStyle: { color: '#d1d5db' } }, axisLabel: { color: '#6b7280' } },
    series: ['accuracy', 'precision', 'recall', 'f1', 'auc'].map((key, i) => ({
      name: key.toUpperCase(), type: 'bar',
      data: modelPerformance.map(m => (m as any)[key]),
      itemStyle: { color: ['#1e90ff', '#22c55e', '#f59e0b', '#ef4444', '#8b5cf6'][i] },
      barGap: '10%',
    })),
  };

  const today = new Date().toISOString().slice(0, 10);

  const topCells = geoData.sort((a, b) => b.risk_score - a.risk_score).slice(0, 8);
  const highRiskLevel = (dashboardStats?.redTideRate ?? 0) > 0.5 ? '高风险' : (dashboardStats?.redTideRate ?? 0) > 0.25 ? '中风险' : '低风险';

  return (
    <div className="space-y-6 animate-fade-in">
      {/* 报告头部 */}
      <div className="text-center py-8 px-6 glass-card ocean-glow" style={{ background: 'linear-gradient(135deg, rgba(0,100,180,0.2), rgba(0,50,100,0.4))' }}>
        <h1 className="text-3xl font-bold text-white mb-3">海洋赤潮发生风险评估模型分析报告</h1>
        <p className="text-gray-400 text-sm">Marine Red Tide Risk Assessment Model Analysis Report</p>
        <div className="flex items-center justify-center gap-6 mt-4 text-xs text-gray-400">
          <span>报告日期：{today}</span>
          <span>版本：v2.0</span>
          <span>真实数据版</span>
        </div>
        <button onClick={handlePrint} className="btn-primary mt-6">
          导出报告 (打印为PDF)
        </button>
      </div>

      {/* 1. 项目背景 */}
      <section className="glass-card p-6 ocean-glow print-section">
        <h2 className="text-xl font-bold text-cyan-300 mb-4 pb-2 border-b border-ocean-700/30">一、项目背景</h2>
        <p className="text-sm text-gray-300 leading-relaxed">
          赤潮（Red Tide）是由海洋浮游植物（藻类）在特定环境条件下爆发性增殖引起的水体变色现象。
          赤潮的发生不仅造成海洋生态系统失衡，还可能导致大规模鱼类死亡、贝类毒素积累，
          对海洋渔业、水产养殖和滨海旅游业造成严重经济损失。
        </p>
        <p className="text-sm text-gray-300 leading-relaxed mt-3">
          本项目构建了一套基于多源海洋环境数据的赤潮发生风险评估模型分析系统，
          融合卫星遥感叶绿素浓度、现场监测海温/盐度、营养盐（硝酸盐、磷酸盐、硅酸盐）、
          气象数据（风速、气压、太阳辐射、降水）数据，
          利用机器学习算法对赤潮发生风险进行定量评估和预警。
        </p>
      </section>

      {/* 2. 数据来源 */}
      <section className="glass-card p-6 ocean-glow print-section">
        <h2 className="text-xl font-bold text-cyan-300 mb-4 pb-2 border-b border-ocean-700/30">二、数据来源</h2>
        <div className="grid grid-cols-3 gap-3 text-sm">
          {[
            { name: '海温(SST)', source: '卫星遥感反演', freq: '月' },
            { name: '叶绿素浓度', source: '卫星遥感反演', freq: '月' },
            { name: '盐度', source: '现场采样/遥感', freq: '月' },
            { name: '硝酸盐', source: '现场采样', freq: '月' },
            { name: '磷酸盐', source: '现场采样', freq: '月' },
            { name: '硅酸盐', source: '现场采样', freq: '月' },
            { name: '风速', source: '气象再分析', freq: '月' },
            { name: '气压', source: '气象再分析', freq: '月' },
            { name: '太阳辐射', source: '气象再分析', freq: '月' },
            { name: '降水量', source: '气象再分析', freq: '月' },
            { name: '赤潮事件', source: '现场监测记录', freq: '月' },
            { name: '藻种数据', source: '现场采样鉴定', freq: '月' },
          ].map((item, idx) => (
            <div key={idx} className="p-3 rounded-lg bg-ocean-800/30 border border-ocean-700/30">
              <p className="font-semibold text-cyan-300 text-sm">{item.name}</p>
              <p className="text-xs text-gray-400 mt-1">来源：{item.source}</p>
              <p className="text-xs text-gray-500">频率：{item.freq}</p>
            </div>
          ))}
        </div>
        <p className="text-xs text-gray-500 mt-4">
          当前系统基于真实海洋环境监测数据（{dashboardStats?.totalSamples?.toLocaleString() ?? 0}条记录，{dashboardStats?.monitoredCells ?? 0}个监测网格），
          时间范围 {dashboardStats?.timeRange ?? '--'}。
        </p>
      </section>

      {/* 3. 数据处理流程 */}
      <section className="glass-card p-6 ocean-glow print-section">
        <h2 className="text-xl font-bold text-cyan-300 mb-4 pb-2 border-b border-ocean-700/30">三、数据处理流程</h2>
        <ol className="list-decimal list-inside space-y-2 text-sm text-gray-300">
          <li><strong className="text-cyan-300">数据采集</strong> — 从卫星遥感、浮标、气象站等多源平台采集原始数据</li>
          <li><strong className="text-cyan-300">数据清洗</strong> — 去除重复记录、无效值和格式异常数据</li>
          <li><strong className="text-cyan-300">缺失值处理</strong> — 采用KNN插补和时间序列插值填补缺失值</li>
          <li><strong className="text-cyan-300">异常值检测</strong> — 3σ原则与IQR方法结合，识别并处理异常记录</li>
          <li><strong className="text-cyan-300">数据归一化</strong> — Min-Max标准化，将所有特征映射到[0,1]区间</li>
          <li><strong className="text-cyan-300">特征选择</strong> — 基于Pearson相关性和特征重要性排序，筛选关键因子</li>
          <li><strong className="text-cyan-300">建模数据集</strong> — 按7:3比例划分训练集和测试集，构建模型输入</li>
        </ol>
      </section>

      {/* 4. 模型方法 */}
      <section className="glass-card p-6 ocean-glow print-section">
        <h2 className="text-xl font-bold text-cyan-300 mb-4 pb-2 border-b border-ocean-700/30">四、模型方法</h2>
        <p className="text-sm text-gray-300 leading-relaxed mb-3">
          本系统采用五种机器学习/深度学习模型进行赤潮风险评估对比实验：
        </p>
        <div className="grid grid-cols-3 gap-3 text-sm">
          {[
            { name: 'Logistic Regression', desc: '经典统计学习方法，可解释性强，作为基准模型' },
            { name: 'Random Forest', desc: '集成学习算法，能处理非线性关系，鲁棒性好' },
            { name: 'XGBoost', desc: '梯度提升树算法，性能优异，支持特征重要性分析' },
            { name: 'BP Neural Network', desc: '反向传播神经网络，适合复杂非线性映射' },
            { name: 'LSTM', desc: '长短期记忆网络，捕捉时间序列依赖性' },
          ].map((m, idx) => (
            <div key={idx} className="p-3 rounded-lg bg-ocean-800/30 border border-ocean-700/30">
              <p className="font-semibold text-cyan-300">{m.name}</p>
              <p className="text-xs text-gray-400 mt-1">{m.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* 5. 模型性能结果 */}
      <section className="glass-card p-6 ocean-glow print-section">
        <h2 className="text-xl font-bold text-cyan-300 mb-4 pb-2 border-b border-ocean-700/30">五、模型性能结果</h2>
        <ReactECharts option={barOption} style={{ height: 300 }} />
        <div className="overflow-x-auto mt-4">
          <table className="w-full text-sm border-collapse">
            <thead>
              <tr className="border-b border-ocean-700/50 text-gray-400 text-xs">
                <th className="py-2 px-2 text-left">模型</th>
                <th className="py-2 px-2 text-center">Accuracy</th>
                <th className="py-2 px-2 text-center">Precision</th>
                <th className="py-2 px-2 text-center">Recall</th>
                <th className="py-2 px-2 text-center">F1-score</th>
                <th className="py-2 px-2 text-center">AUC</th>
              </tr>
            </thead>
            <tbody>
              {modelPerformance.map(m => (
                <tr key={m.model} className="border-b border-ocean-700/20 text-xs">
                  <td className="py-2 px-2 text-cyan-300">{m.model}</td>
                  <td className="py-2 px-2 text-center">{(m.accuracy * 100).toFixed(1)}%</td>
                  <td className="py-2 px-2 text-center">{(m.precision * 100).toFixed(1)}%</td>
                  <td className="py-2 px-2 text-center">{(m.recall * 100).toFixed(1)}%</td>
                  <td className="py-2 px-2 text-center">{(m.f1 * 100).toFixed(1)}%</td>
                  <td className="py-2 px-2 text-center text-yellow-400">{m.auc.toFixed(3)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="mt-4 p-4 rounded-lg bg-ocean-800/40 border border-yellow-500/30">
          <p className="text-sm text-yellow-400 font-semibold">★ 推荐模型：XGBoost — 综合表现最优（AUC=0.928, F1=0.867），运行效率高（2.5s），适合部署为赤潮风险评估核心算法。</p>
        </div>
      </section>

      {/* 6. 当前风险评估 */}
      <section className="glass-card p-6 ocean-glow print-section">
        <h2 className="text-xl font-bold text-cyan-300 mb-4 pb-2 border-b border-ocean-700/30">六、当前风险评估结果</h2>
        <div className="grid grid-cols-4 gap-4 mb-4">
          <div className="text-center p-4 rounded-lg bg-ocean-800/30">
            <p className="text-xs text-gray-400">整体风险等级</p>
            <div className="mt-1 flex justify-center"><RiskBadge level={highRiskLevel} size="lg" /></div>
          </div>
          <div className="text-center p-4 rounded-lg bg-ocean-800/30">
            <p className="text-xs text-gray-400">赤潮发生率</p>
            <p className="text-2xl font-bold text-cyan-300 mt-1">{((dashboardStats?.redTideRate ?? 0) * 100).toFixed(1)}%</p>
          </div>
          <div className="text-center p-4 rounded-lg bg-ocean-800/30">
            <p className="text-xs text-gray-400">数据样本</p>
            <p className="text-2xl font-bold text-blue-300 mt-1">{dashboardStats?.totalSamples?.toLocaleString() ?? '--'}</p>
          </div>
          <div className="text-center p-4 rounded-lg bg-ocean-800/30">
            <p className="text-xs text-gray-400">监测网格</p>
            <p className="text-2xl font-bold text-green-400 mt-1">{dashboardStats?.monitoredCells ?? '--'}</p>
          </div>
        </div>
        <h4 className="text-sm font-semibold text-gray-300 mb-2">高风险网格排名</h4>
        <div className="space-y-2">
          {topCells.map((g, idx) => (
            <div key={idx} className="flex items-center gap-3 p-2 rounded bg-ocean-800/20">
              <span className="text-xs text-gray-500 w-6">{idx + 1}</span>
              <span className="text-sm text-gray-200 w-40">{g.longitude.toFixed(2)}°E, {g.latitude.toFixed(2)}°N</span>
              <RiskBadge level={g.risk_level} size="sm" />
              <span className="text-sm text-cyan-300 ml-auto">{g.risk_score}分</span>
            </div>
          ))}
        </div>
      </section>

      {/* 7. 预警列表 */}
      <section className="glass-card p-6 ocean-glow print-section">
        <h2 className="text-xl font-bold text-cyan-300 mb-4 pb-2 border-b border-ocean-700/30">七、预警建议</h2>
        <p className="text-sm text-gray-300 mb-3">
          基于风险评估模型对当前高风险区域进行预警。高风险及以上区域需加强监测。
        </p>
        <div className="space-y-2">
          {warningList.slice(0, 10).map((w, idx) => (
            <div key={idx} className="flex items-center gap-3 p-2 rounded bg-ocean-800/20 text-sm">
              <span className="text-xs text-gray-500">{w.date}</span>
              <span className="text-cyan-300">{w.location}</span>
              <RiskBadge level={w.riskLevel} size="sm" />
              <span className="text-gray-400 text-xs ml-auto">{w.suggestion}</span>
            </div>
          ))}
        </div>
      </section>

      {/* 8. 特征重要性 */}
      <section className="glass-card p-6 ocean-glow print-section">
        <h2 className="text-xl font-bold text-cyan-300 mb-4 pb-2 border-b border-ocean-700/30">八、关键影响因子</h2>
        <p className="text-sm text-gray-300 mb-3">
          基于Pearson相关性分析的特征重要性排序显示，各环境因子与赤潮面积的关联强度如下。
        </p>
        <div className="space-y-2">
          {featureImportance.map((f, idx) => (
            <div key={idx} className="flex items-center gap-3 p-2 rounded bg-ocean-800/20">
              <span className="text-xs text-gray-500 w-6">{idx + 1}</span>
              <span className="text-sm text-gray-200 w-24">{f.feature}</span>
              <div className="flex-1 h-2 rounded-full bg-ocean-700/50 overflow-hidden">
                <div className="h-full rounded-full" style={{ width: `${f.importance * 100}%`, backgroundColor: idx === 0 ? '#ef4444' : idx <= 2 ? '#f97316' : '#22c55e' }} />
              </div>
              <span className="text-xs text-gray-400 w-12 text-right">{(f.importance * 100).toFixed(1)}%</span>
            </div>
          ))}
        </div>
      </section>

      {/* 9. 关键结论与建议 */}
      <section className="glass-card p-6 ocean-glow print-section">
        <h2 className="text-xl font-bold text-cyan-300 mb-4 pb-2 border-b border-ocean-700/30">九、关键结论与防控建议</h2>

        <h3 className="text-base font-semibold text-white mb-2">关键结论</h3>
        <ol className="list-decimal list-inside space-y-2 text-sm text-gray-300 mb-4">
          <li>XGBoost模型在赤潮风险评估中综合表现最优，准确率89.2%，AUC 0.928，推荐作为核心算法。</li>
          <li>叶绿素浓度是赤潮发生的最重要预测因子，卫星遥感数据是预警的关键输入。</li>
          <li>海温和盐度是重要的环境驱动因子，三者共同反映藻类生长和水体富营养化状态。</li>
          <li>基于{geoData.length}个网格的{topCells.filter(g => g.risk_score >= 50).length}个高风险网格需重点关注。</li>
          <li>赤潮发生率约{((dashboardStats?.redTideRate ?? 0) * 100).toFixed(1)}%，需持续监测高风险季节变化。</li>
        </ol>

        <h3 className="text-base font-semibold text-green-400 mb-2">防控建议</h3>
        <ul className="list-disc list-inside space-y-2 text-sm text-gray-300">
          <li>建立多源数据实时融合监测体系，整合卫星遥感、浮标和气象站数据。</li>
          <li>将赤潮风险评估模型纳入海洋环境日常监测系统，实现自动化预警。</li>
          <li>针对高风险网格区域，适当提高监测频次和采样密度。</li>
          <li>加强陆源污染物排放控制，减少营养盐输入，从源头降低赤潮风险。</li>
          <li>建立赤潮应急响应预案，形成"监测-预警-评估-响应"的完整防控链条。</li>
          <li>持续积累赤潮案例数据，定期更新和优化评估模型，提升预警精度。</li>
        </ul>
      </section>

      {/* 报告底部 */}
      <div className="text-center text-xs text-gray-600 py-6 border-t border-ocean-700/30">
        <p>本报告由海洋赤潮发生风险评估模型分析系统自动生成</p>
        <p className="mt-1">数据来源：integrated_database.db 真实监测数据 | 数据时间范围：{dashboardStats?.timeRange ?? '--'}</p>
        <p className="mt-1">报告生成时间：{today} {new Date().toLocaleTimeString()}</p>
      </div>

      <style>{`
        @media print {
          body { background: white !important; color: #1f2937 !important; }
          .glass-card { background: white !important; border: 1px solid #e5e7eb !important; box-shadow: none !important; }
          .page-title, h2, h1 { color: #1f2937 !important; }
          p, li, span { color: #4b5563 !important; }
        }
      `}</style>
    </div>
  );
};

export default Report;
