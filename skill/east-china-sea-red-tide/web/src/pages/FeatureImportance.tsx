import React, { useState } from 'react';
import ReactECharts from 'echarts-for-react';
import ChartCard from '../components/ChartCard';
import { useData } from '../services/dataContext';

const FeatureImportance: React.FC = () => {
  const { featureImportance } = useData();
  const [selectedFeature, setSelectedFeature] = useState(featureImportance[0]);

  const barOption = {
    tooltip: { trigger: 'axis', backgroundColor: 'rgba(10,22,40,0.9)', borderColor: '#1e64c8', textStyle: { color: '#e0f0ff' }, formatter: (p: any) => `${p[0].name}<br/>重要性: ${(p[0].value * 100).toFixed(1)}%` },
    grid: { left: '3%', right: '15%', bottom: '3%', top: '5px', containLabel: true },
    xAxis: { type: 'value', name: '重要性', axisLine: { lineStyle: { color: '#1e3a5f' } }, axisLabel: { color: '#8ab4d6', formatter: (v: number) => (v * 100).toFixed(0) + '%' }, splitLine: { lineStyle: { color: 'rgba(30,58,95,0.4)' } } },
    yAxis: { type: 'category', data: featureImportance.map(f => f.feature).reverse(), axisLine: { lineStyle: { color: '#1e3a5f' } }, axisLabel: { color: '#8ab4d6', fontSize: 11 } },
    series: [{
      type: 'bar',
      data: featureImportance.map((f, idx) => ({
        value: f.importance,
        itemStyle: {
          color: idx === 0 ? '#ef4444' : idx <= 2 ? '#f97316' : idx <= 4 ? '#eab308' : '#22c55e',
          borderRadius: [0, 6, 6, 0],
        },
      })).reverse(),
      barWidth: 20,
      label: { show: true, position: 'right', color: '#8ab4d6', fontSize: 11, formatter: (p: any) => (p.value * 100).toFixed(1) + '%' },
    }],
  };

  const pieOption = {
    tooltip: { trigger: 'item', backgroundColor: 'rgba(10,22,40,0.9)', borderColor: '#1e64c8', textStyle: { color: '#e0f0ff' }, formatter: '{b}: {c}%' },
    legend: { orient: 'vertical', right: '5%', top: 'center', textStyle: { color: '#8ab4d6', fontSize: 10 } },
    series: [{
      type: 'pie',
      radius: ['50%', '75%'],
      center: ['40%', '50%'],
      label: { show: false },
      emphasis: { label: { show: true, fontSize: 12 } },
      data: featureImportance.map((f, i) => ({
        value: +(f.importance * 100).toFixed(1),
        name: f.feature,
        itemStyle: { color: ['#ef4444', '#f97316', '#eab308', '#22c55e', '#00d4ff', '#1e90ff', '#ce93d8', '#78909c'][i] },
      })),
    }],
  };

  return (
    <div className="space-y-5 animate-fade-in">
      <div><h2 className="page-title">特征重要性分析</h2><p className="page-subtitle">基于SHAP值的模型关键影响因子分析与生态意义解读</p></div>

      <div className="grid grid-cols-3 gap-5">
        {/* 横向柱状图 */}
        <div className="col-span-2">
          <ChartCard title="特征重要性排序" subtitle="各环境因子对赤潮风险的贡献度（SHAP值）">
            <ReactECharts option={barOption} style={{ height: 380 }} />
          </ChartCard>
        </div>

        {/* 饼图 + 点击详情 */}
        <div className="space-y-5">
          <ChartCard title="重要性占比" subtitle="特征贡献百分比分布">
            <ReactECharts option={pieOption} style={{ height: 220 }} />
          </ChartCard>

          {/* 选中特征详情 */}
          <div className="glass-card p-4 ocean-glow">
            <h3 className="text-sm font-semibold text-cyan-300 mb-3">特征生态意义</h3>
            <div className="space-y-2">
              <div className="flex justify-between py-1.5 border-b border-ocean-700/30">
                <span className="text-xs text-gray-400">选中特征</span>
                <span className="text-xs text-cyan-300 font-semibold">{selectedFeature.feature}</span>
              </div>
              <div className="flex justify-between py-1.5 border-b border-ocean-700/30">
                <span className="text-xs text-gray-400">重要性权重</span>
                <span className="text-xs text-yellow-400 font-semibold">{(selectedFeature.importance * 100).toFixed(1)}%</span>
              </div>
              <div className="flex justify-between py-1.5 border-b border-ocean-700/30">
                <span className="text-xs text-gray-400">排名</span>
                <span className="text-xs text-white">
                  第 {featureImportance.findIndex(f => f.feature === selectedFeature.feature) + 1} / {featureImportance.length}
                </span>
              </div>
            </div>
            <div className="mt-4 p-3 rounded-lg bg-ocean-800/30 border border-ocean-700/30">
              <p className="text-xs text-gray-400 leading-relaxed">{selectedFeature.description}</p>
            </div>
          </div>
        </div>
      </div>

      {/* 特征选择列表 */}
      <div className="glass-card p-5 ocean-glow">
        <h3 className="section-title">特征详情列表（点击查看生态意义）</h3>
        <div className="grid grid-cols-4 gap-3">
          {featureImportance.map((f, idx) => (
            <button
              key={f.feature}
              onClick={() => setSelectedFeature(f)}
              className={`p-3 rounded-lg text-left transition-all border ${
                selectedFeature.feature === f.feature
                  ? 'bg-cyan-500/15 border-cyan-500/40 shadow-lg shadow-cyan-500/10'
                  : 'bg-ocean-800/30 border-ocean-700/30 hover:bg-ocean-800/50'
              }`}
            >
              <div className="flex items-center justify-between mb-1">
                <span className="text-sm font-semibold text-gray-200">{f.feature}</span>
                <span className="text-xs px-2 py-0.5 rounded-full bg-ocean-700/50 text-gray-400">#{idx + 1}</span>
              </div>
              <div className="w-full h-1.5 rounded-full bg-ocean-700/50 mt-2 overflow-hidden">
                <div
                  className="h-full rounded-full transition-all"
                  style={{
                    width: `${(f.importance * 100).toFixed(0)}%`,
                    backgroundColor: idx === 0 ? '#ef4444' : idx <= 2 ? '#f97316' : idx <= 4 ? '#eab308' : '#22c55e',
                  }}
                />
              </div>
              <p className="text-xs text-gray-500 mt-2">{(f.importance * 100).toFixed(1)}%</p>
            </button>
          ))}
        </div>
      </div>

      {/* 关键结论 */}
      <div className="glass-card p-5 ocean-glow bg-gradient-to-r from-ocean-800/80 to-ocean-900/80">
        <h3 className="section-title">关键发现</h3>
        <div className="grid grid-cols-3 gap-4 text-sm">
          <div className="p-3 rounded-lg bg-ocean-800/30 border border-ocean-700/30">
            <p className="text-red-400 font-semibold mb-1">首要因子：叶绿素a (31.2%)</p>
            <p className="text-xs text-gray-400">叶绿素a浓度是赤潮发生的最直接生物量指标，贡献超过30%。建议将卫星遥感叶绿素a作为核心监测指标。</p>
          </div>
          <div className="p-3 rounded-lg bg-ocean-800/30 border border-ocean-700/30">
            <p className="text-orange-400 font-semibold mb-1">前三因子贡献超67%</p>
            <p className="text-xs text-gray-400">叶绿素a、水温、溶解氧三个因子合计贡献67.5%，是赤潮预警的核心关注指标。这三者共同反映了藻类生长、水体富营养化和环境适宜度。</p>
          </div>
          <div className="p-3 rounded-lg bg-ocean-800/30 border border-ocean-700/30">
            <p className="text-green-400 font-semibold mb-1">物理因子不可忽视</p>
            <p className="text-xs text-gray-400">风速和海流速度合计贡献12.4%，在低风速低流速条件下赤潮风险显著升高，水体交换能力是防控的关键因素之一。</p>
          </div>
        </div>
      </div>
    </div>
  );
};

export default FeatureImportance;
