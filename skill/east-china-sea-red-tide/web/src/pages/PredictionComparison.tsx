import { useState, useMemo } from 'react';
import ReactECharts from 'echarts-for-react';
import ChartCard from '../components/ChartCard';
import { useData } from '../services/dataContext';

const PredictionComparison: React.FC = () => {
  const { timeSeries, geoData } = useData();

  const topCells = useMemo(() =>
    geoData.sort((a, b) => b.risk_score - a.risk_score).slice(0, 6),
  [geoData]);

  const [selectedCellIdx, setSelectedCellIdx] = useState(0);
  const selectedCell = topCells[selectedCellIdx];

  const lineData = useMemo(() => timeSeries.map(t => ({
    date: `${t.year}-${String(t.month).padStart(2, '0')}`,
    riskRate: +(t.red_tide_rate * 100).toFixed(1),
  })), [timeSeries]);

  const lineOption = {
    tooltip: { trigger: 'axis', backgroundColor: 'rgba(10,22,40,0.9)', borderColor: '#1e64c8', textStyle: { color: '#e0f0ff' } },
    legend: { data: ['实际风险率', '高风险阈值'], textStyle: { color: '#8ab4d6' }, top: 0 },
    grid: { left: '3%', right: '4%', bottom: '3%', top: '40px', containLabel: true },
    xAxis: { type: 'category', data: lineData.map(d => d.date.slice(2)), axisLine: { lineStyle: { color: '#1e3a5f' } }, axisLabel: { color: '#8ab4d6', fontSize: 10, rotate: 45 } },
    yAxis: { type: 'value', name: '风险率(%)', axisLine: { lineStyle: { color: '#1e3a5f' } }, axisLabel: { color: '#8ab4d6' }, splitLine: { lineStyle: { color: 'rgba(30,58,95,0.4)' } } },
    series: [
      { name: '实际风险率', type: 'line', data: lineData.map(d => d.riskRate), lineStyle: { color: '#ef4444', width: 2 }, itemStyle: { color: '#ef4444' }, smooth: true,
        areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: 'rgba(239,68,68,0.15)' }, { offset: 1, color: 'rgba(239,68,68,0)' }] } } },
      { name: '高风险阈值', type: 'line', data: Array(lineData.length).fill(50), lineStyle: { color: '#eab308', width: 1.5, type: 'dotted' }, itemStyle: { color: '#eab308' }, symbol: 'none' },
    ],
  };

  const scatterData = useMemo(() => timeSeries.map(t => [t.avg_chlorophyll, +(t.red_tide_rate * 100).toFixed(1)]), [timeSeries]);

  const scatterOption = {
    tooltip: { trigger: 'item', backgroundColor: 'rgba(10,22,40,0.9)', borderColor: '#1e64c8', textStyle: { color: '#e0f0ff' }, formatter: (p: any) => `叶绿素: ${p.value[0].toFixed(2)}<br/>风险率: ${p.value[1]}%` },
    grid: { left: '8%', right: '5%', bottom: '8%', top: '10px', containLabel: true },
    xAxis: { type: 'value', name: '叶绿素均值', axisLine: { lineStyle: { color: '#1e3a5f' } }, axisLabel: { color: '#8ab4d6' }, splitLine: { lineStyle: { color: 'rgba(30,58,95,0.4)' } } },
    yAxis: { type: 'value', name: '赤潮风险率(%)', axisLine: { lineStyle: { color: '#1e3a5f' } }, axisLabel: { color: '#8ab4d6' }, splitLine: { lineStyle: { color: 'rgba(30,58,95,0.4)' } } },
    series: [{ type: 'scatter', data: scatterData, symbolSize: 10, itemStyle: { color: '#00d4ff', borderColor: '#fff', borderWidth: 1, shadowBlur: 8, shadowColor: 'rgba(0,212,255,0.4)' } }],
  };

  if (topCells.length === 0) {
    return (
      <div className="space-y-5 animate-fade-in">
        <div><h2 className="page-title">数据对比分析</h2><p className="page-subtitle">环境因子与赤潮风险的关联分析</p></div>
        <div className="glass-card p-12 flex flex-col items-center justify-center ocean-glow" style={{ minHeight: 400 }}>
          <p className="text-gray-400 text-lg">正在加载数据...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-5 animate-fade-in">
      <div>
        <h2 className="page-title">数据对比分析</h2>
        <p className="page-subtitle">环境因子与赤潮风险的关联分析和趋势对比</p>
      </div>

      <div className="flex gap-2 flex-wrap">
        {topCells.map((cell, idx) => (
          <button key={idx} onClick={() => setSelectedCellIdx(idx)} className={`px-4 py-2 rounded-lg text-sm transition-all ${selectedCellIdx === idx ? 'bg-gradient-to-r from-cyan-500 to-blue-600 text-white shadow-lg shadow-cyan-500/25' : 'bg-ocean-800/50 text-gray-400 border border-ocean-700/30 hover:text-gray-200'}`}>
            {cell.longitude.toFixed(1)}°E, {cell.latitude.toFixed(1)}°N
          </button>
        ))}
      </div>

      <ChartCard title="赤潮风险率月度趋势" subtitle="红色为实际风险率，黄色虚线为高风险阈值(50%)">
        <ReactECharts option={lineOption} style={{ height: 380 }} />
      </ChartCard>

      <div className="grid grid-cols-2 gap-5">
        <ChartCard title="叶绿素 vs 风险率散点图" subtitle="叶绿素浓度与赤潮风险率的关系">
          <ReactECharts option={scatterOption} style={{ height: 320 }} />
        </ChartCard>
        <ChartCard title="网格详情" subtitle="基于真实数据的分析">
          <div className="space-y-4 mt-2">
            <div className="p-4 rounded-lg bg-ocean-800/30 border border-ocean-700/30">
              <h4 className="text-sm font-semibold text-cyan-300 mb-2">选定网格</h4>
              <p className="text-xs text-gray-400 leading-relaxed">
                位置: {selectedCell?.longitude.toFixed(3)}°E, {selectedCell?.latitude.toFixed(3)}°N<br/>
                风险评分: <span className="text-cyan-300 font-semibold">{selectedCell?.risk_score}</span><br/>
                风险等级: <span className="text-yellow-300 font-semibold">{selectedCell?.risk_level}</span><br/>
                赤潮频次: <span className="text-orange-400">{((selectedCell?.red_tide_frequency ?? 0) * 100).toFixed(1)}%</span><br/>
                样本数: {selectedCell?.sample_count}
              </p>
            </div>
            <div className="p-4 rounded-lg bg-ocean-800/30 border border-ocean-700/30">
              <h4 className="text-sm font-semibold text-yellow-400 mb-2">关键发现</h4>
              <p className="text-xs text-gray-400 leading-relaxed">
                叶绿素浓度与赤潮风险率呈正相关，高叶绿素区域赤潮发生频率显著更高。营养盐（硝酸盐、磷酸盐）也是重要驱动因子。
              </p>
            </div>
            <div className="p-4 rounded-lg bg-ocean-800/30 border border-ocean-700/30">
              <h4 className="text-sm font-semibold text-green-400 mb-2">后续方向</h4>
              <p className="text-xs text-gray-400 leading-relaxed">
                引入更高频次卫星遥感数据和实时浮标监测，进一步提升模型时效性和预警精度。
              </p>
            </div>
          </div>
        </ChartCard>
      </div>
    </div>
  );
};

export default PredictionComparison;
