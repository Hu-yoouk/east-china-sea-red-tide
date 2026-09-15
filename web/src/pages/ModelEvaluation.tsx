import React from 'react';
import ReactECharts from 'echarts-for-react';
import ChartCard from '../components/ChartCard';
import { useData } from '../services/dataContext';

const ModelEvaluation: React.FC = () => {
  const { modelPerformance } = useData();
  const barOption = {
    tooltip: { trigger: 'axis', backgroundColor: 'rgba(10,22,40,0.9)', borderColor: '#1e64c8', textStyle: { color: '#e0f0ff' } },
    legend: { data: ['Accuracy', 'Precision', 'Recall', 'F1-score', 'AUC'], textStyle: { color: '#8ab4d6', fontSize: 10 }, top: 0 },
    grid: { left: '3%', right: '4%', bottom: '3%', top: '40px', containLabel: true },
    xAxis: { type: 'category', data: modelPerformance.map(m => m.model.replace(' ', '\n')), axisLine: { lineStyle: { color: '#1e3a5f' } }, axisLabel: { color: '#8ab4d6', fontSize: 10 } },
    yAxis: { type: 'value', name: '分值', min: 0.6, max: 1, axisLine: { lineStyle: { color: '#1e3a5f' } }, axisLabel: { color: '#8ab4d6' }, splitLine: { lineStyle: { color: 'rgba(30,58,95,0.4)' } } },
    series: [
      { name: 'Accuracy', type: 'bar', data: modelPerformance.map(m => m.accuracy), itemStyle: { color: '#00d4ff' }, barGap: '10%' },
      { name: 'Precision', type: 'bar', data: modelPerformance.map(m => m.precision), itemStyle: { color: '#1e90ff' } },
      { name: 'Recall', type: 'bar', data: modelPerformance.map(m => m.recall), itemStyle: { color: '#00e676' } },
      { name: 'F1-score', type: 'bar', data: modelPerformance.map(m => m.f1), itemStyle: { color: '#ffd54f' } },
      { name: 'AUC', type: 'bar', data: modelPerformance.map(m => m.auc), itemStyle: { color: '#ce93d8' } },
    ],
  };

  const radarOption = {
    tooltip: {},
    legend: { data: modelPerformance.map(m => m.model), textStyle: { color: '#8ab4d6', fontSize: 9 }, bottom: 0 },
    radar: {
      center: ['50%', '45%'],
      radius: '60%',
      indicator: [
        { name: 'Accuracy', max: 1 },
        { name: 'Precision', max: 1 },
        { name: 'Recall', max: 1 },
        { name: 'F1-score', max: 1 },
        { name: 'AUC', max: 1 },
      ],
      axisName: { color: '#8ab4d6', fontSize: 10 },
      splitArea: { areaStyle: { color: ['rgba(0,212,255,0.02)', 'rgba(0,212,255,0.04)'] } },
    },
    series: [{
      type: 'radar',
      data: modelPerformance.map((m, idx) => ({
        name: m.model,
        value: [m.accuracy, m.precision, m.recall, m.f1, m.auc],
        lineStyle: { color: ['#00d4ff', '#00e676', '#ffd54f', '#ce93d8', '#ff6b6b'][idx], width: 1.5 },
        areaStyle: { color: ['rgba(0,212,255,0.1)', 'rgba(0,230,118,0.1)', 'rgba(255,213,79,0.1)', 'rgba(206,147,216,0.1)', 'rgba(255,107,107,0.1)'][idx] },
        itemStyle: { color: ['#00d4ff', '#00e676', '#ffd54f', '#ce93d8', '#ff6b6b'][idx] },
      })),
    }],
  };

  const runtimeOption = {
    tooltip: { trigger: 'axis', backgroundColor: 'rgba(10,22,40,0.9)', borderColor: '#1e64c8', textStyle: { color: '#e0f0ff' } },
    grid: { left: '3%', right: '12%', bottom: '3%', top: '10px', containLabel: true },
    xAxis: { type: 'category', data: modelPerformance.map(m => m.model), axisLine: { lineStyle: { color: '#1e3a5f' } }, axisLabel: { color: '#8ab4d6', fontSize: 10, rotate: 20 } },
    yAxis: { type: 'value', name: '秒', axisLine: { lineStyle: { color: '#1e3a5f' } }, axisLabel: { color: '#8ab4d6' }, splitLine: { lineStyle: { color: 'rgba(30,58,95,0.4)' } } },
    series: [{
      type: 'bar', data: modelPerformance.map(m => m.runtime),
      itemStyle: { color: '#00d4ff', borderRadius: [6, 6, 0, 0] }, barWidth: '40%',
      label: { show: true, position: 'top', color: '#8ab4d6', fontSize: 11, formatter: '{c}s' },
    }],
  };

  // 模拟混淆矩阵
  const confusionMatrixOption = {
    tooltip: { trigger: 'item' },
    grid: { left: '5%', right: '5%', bottom: '5%', top: '5%' },
    xAxis: { type: 'category', data: ['预测低', '预测中', '预测高', '预测极高'], position: 'top', axisLine: { lineStyle: { color: '#1e3a5f' } }, axisLabel: { color: '#8ab4d6' } },
    yAxis: { type: 'category', data: ['实际低', '实际中', '实际高', '实际极高'], axisLine: { lineStyle: { color: '#1e3a5f' } }, axisLabel: { color: '#8ab4d6' } },
    visualMap: { min: 0, max: 30, calculable: true, orient: 'horizontal', left: 'center', bottom: 0, textStyle: { color: '#8ab4d6' }, inRange: { color: ['#0a1628', '#0f3d5c', '#1a6d9e', '#00d4ff', '#00e676'] }, show: false },
    series: [{
      type: 'heatmap',
      data: [[0, 0, 28], [0, 1, 3], [0, 2, 0], [0, 3, 0], [1, 0, 4], [1, 1, 22], [1, 2, 3], [1, 3, 0], [2, 0, 0], [2, 1, 3], [2, 2, 24], [2, 3, 4], [3, 0, 0], [3, 1, 0], [3, 2, 3], [3, 3, 25]],
      label: { show: true, color: '#fff', fontSize: 14, fontWeight: 'bold' },
      emphasis: { itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0,212,255,0.5)' } },
    }],
  };

  return (
    <div className="space-y-5 animate-fade-in">
      <div><h2 className="page-title">模型性能评估</h2><p className="page-subtitle">多模型赤潮风险预测性能对比与综合评估</p></div>

      {/* 推荐模型卡片 */}
      <div className="glass-card p-5 ocean-glow bg-gradient-to-r from-ocean-800/80 to-ocean-900/80">
        <div className="flex items-center gap-4">
          <span className="text-4xl">🏆</span>
          <div className="flex-1">
            <h3 className="text-lg font-bold text-yellow-400">推荐模型：XGBoost</h3>
            <p className="text-sm text-gray-400 mt-1">综合性能最优：Accuracy 89.2%，AUC 0.928，F1-score 0.867，运行时间仅2.5秒。在准确率与效率之间取得最佳平衡，适合作为赤潮风险评估的核心算法模型。</p>
          </div>
          <div className="text-right">
            <div className="text-3xl font-bold text-yellow-400">0.928</div>
            <div className="text-xs text-gray-500">AUC</div>
          </div>
        </div>
      </div>

      {/* 性能柱状图和雷达图 */}
      <div className="grid grid-cols-2 gap-5">
        <ChartCard title="模型性能对比" subtitle="五大指标柱状图对比">
          <ReactECharts option={barOption} style={{ height: 350 }} />
        </ChartCard>
        <ChartCard title="模型综合雷达图" subtitle="多维度性能雷达对比">
          <ReactECharts option={radarOption} style={{ height: 350 }} />
        </ChartCard>
      </div>

      {/* 混淆矩阵和运行时间 */}
      <div className="grid grid-cols-2 gap-5">
        <ChartCard title="混淆矩阵（XGBoost）" subtitle="预测类别与实际类别的交叉分布">
          <ReactECharts option={confusionMatrixOption} style={{ height: 320 }} />
        </ChartCard>
        <ChartCard title="模型运行时间" subtitle="不同模型的训练/推理耗时对比">
          <ReactECharts option={runtimeOption} style={{ height: 320 }} />
        </ChartCard>
      </div>

      {/* 详细指标表格 */}
      <div className="glass-card p-5 ocean-glow">
        <h3 className="section-title">模型性能详细数据</h3>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-ocean-700/50 text-gray-400 text-xs">
                <th className="py-3 px-3 text-left">模型</th>
                <th className="py-3 px-3 text-center">Accuracy</th>
                <th className="py-3 px-3 text-center">Precision</th>
                <th className="py-3 px-3 text-center">Recall</th>
                <th className="py-3 px-3 text-center">F1-score</th>
                <th className="py-3 px-3 text-center">AUC</th>
                <th className="py-3 px-3 text-center">运行时间(s)</th>
                <th className="py-3 px-3 text-center">综合评级</th>
              </tr>
            </thead>
            <tbody>
              {modelPerformance.map(m => (
                <tr key={m.model} className="border-b border-ocean-700/20 hover:bg-ocean-800/30 transition-colors text-xs">
                  <td className="py-3 px-3 text-cyan-300 font-semibold">{m.model}</td>
                  <td className="py-3 px-3 text-center">{(m.accuracy * 100).toFixed(1)}%</td>
                  <td className="py-3 px-3 text-center">{(m.precision * 100).toFixed(1)}%</td>
                  <td className="py-3 px-3 text-center">{(m.recall * 100).toFixed(1)}%</td>
                  <td className="py-3 px-3 text-center">{(m.f1 * 100).toFixed(1)}%</td>
                  <td className="py-3 px-3 text-center text-yellow-400 font-semibold">{m.auc.toFixed(3)}</td>
                  <td className="py-3 px-3 text-center">{m.runtime.toFixed(1)}</td>
                  <td className="py-3 px-3 text-center">
                    {m.auc >= 0.92 ? '⭐⭐⭐⭐⭐' : m.auc >= 0.89 ? '⭐⭐⭐⭐' : '⭐⭐⭐'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

export default ModelEvaluation;
