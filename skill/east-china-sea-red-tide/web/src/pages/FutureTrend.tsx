import { useMemo } from 'react';
import ReactECharts from 'echarts-for-react';
import ChartCard from '../components/ChartCard';
import RiskBadge from '../components/RiskBadge';
import { useData } from '../services/dataContext';

const FutureTrend: React.FC = () => {
  const { timeSeries, warningList, geoData } = useData();

  // Build trend from real time series data
  const trendData = useMemo(() => {
    return timeSeries.map(t => ({
      date: `${t.year}-${String(t.month).padStart(2, '0')}`,
      riskRate: +(t.red_tide_rate * 100).toFixed(1),
      chlorophyll: t.avg_chlorophyll,
      sst: t.avg_sst,
    }));
  }, [timeSeries]);

  const allDates = trendData.map(d => d.date);

  const trendOption = useMemo(() => ({
    tooltip: { trigger: 'axis', backgroundColor: 'rgba(10,22,40,0.9)', borderColor: '#1e64c8', textStyle: { color: '#e0f0ff' } },
    legend: { data: ['赤潮风险率', '叶绿素均值', '高风险线'], textStyle: { color: '#8ab4d6' }, top: 0 },
    grid: { left: '3%', right: '4%', bottom: '3%', top: '40px', containLabel: true },
    xAxis: { type: 'category', data: allDates.map(d => d.slice(2)), axisLine: { lineStyle: { color: '#1e3a5f' } }, axisLabel: { color: '#8ab4d6', fontSize: 9, rotate: 45 } },
    yAxis: { type: 'value', name: '风险率(%)', axisLine: { lineStyle: { color: '#1e3a5f' } }, axisLabel: { color: '#8ab4d6' }, splitLine: { lineStyle: { color: 'rgba(30,58,95,0.4)' } } },
    series: [
      {
        name: '赤潮风险率', type: 'line', data: trendData.map(d => d.riskRate),
        smooth: true, lineStyle: { color: '#00d4ff', width: 2 }, itemStyle: { color: '#00d4ff' },
        areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: 'rgba(0,212,255,0.25)' }, { offset: 1, color: 'rgba(0,212,255,0.02)' }] } },
      },
      {
        name: '叶绿素均值', type: 'line', data: trendData.map(d => +(d.chlorophyll * 3).toFixed(1)),
        smooth: true, lineStyle: { color: '#00e676', width: 1.5, type: 'dashed' }, itemStyle: { color: '#00e676' },
      },
      {
        name: '高风险线', type: 'line', data: Array(allDates.length).fill(50),
        lineStyle: { color: '#f97316', width: 1, type: 'dotted' }, itemStyle: { color: '#f97316' }, symbol: 'none',
      },
    ],
  }), [trendData, allDates]);

  // Heatmap: grid cells over time
  const heatmapData: [number, number, number][] = [];
  const topCells = geoData.sort((a, b) => b.risk_score - a.risk_score).slice(0, 12);
  const heatmapLabels = topCells.map(g => `${g.longitude.toFixed(1)}°E\n${g.latitude.toFixed(1)}°N`);
  topCells.forEach((_cell, ci) => {
    trendData.forEach((d, di) => {
      heatmapData.push([di, ci, d.riskRate]);
    });
  });

  const heatmapOption = useMemo(() => ({
    tooltip: { backgroundColor: 'rgba(10,22,40,0.9)', borderColor: '#1e64c8', textStyle: { color: '#e0f0ff' } },
    grid: { left: '12%', right: '5%', bottom: '8%', top: '5px', containLabel: true },
    xAxis: { type: 'category', data: allDates.map(d => d.slice(2)), axisLine: { lineStyle: { color: '#1e3a5f' } }, axisLabel: { color: '#8ab4d6', fontSize: 8, rotate: 45 } },
    yAxis: { type: 'category', data: heatmapLabels, axisLine: { lineStyle: { color: '#1e3a5f' } }, axisLabel: { color: '#8ab4d6', fontSize: 9 } },
    visualMap: { min: 0, max: 100, calculable: true, orient: 'horizontal', left: 'center', bottom: 0, textStyle: { color: '#8ab4d6' }, inRange: { color: ['#22c55e', '#eab308', '#f97316', '#ef4444'] }, dimension: 2 },
    series: [{ type: 'heatmap', data: heatmapData, label: { show: false }, emphasis: { itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0,212,255,0.5)' } } }],
  }), [heatmapData, allDates, heatmapLabels]);

  return (
    <div className="space-y-5 animate-fade-in">
      <div><h2 className="page-title">未来趋势预测</h2><p className="page-subtitle">基于时间序列分析的历史趋势与高风险网格预警列表</p></div>

      <ChartCard title="赤潮风险率历史趋势" subtitle={`${allDates.length}个月度数据分析，橙色虚线为高风险线(50%)`}>
        <ReactECharts option={trendOption} style={{ height: 380 }} />
      </ChartCard>

      <div className="grid grid-cols-3 gap-5">
        <div className="col-span-2">
          <ChartCard title="高风险网格月度趋势热力图" subtitle="颜色越红表示赤潮风险率越高">
            <ReactECharts option={heatmapOption} style={{ height: 320 }} />
          </ChartCard>
        </div>
        <ChartCard title="高风险预警列表" subtitle="基于风险评分的预警建议" action={<span className="text-xs text-gray-500">{warningList.length}条</span>}>
          <div className="space-y-2 max-h-[290px] overflow-y-auto mt-2">
            {warningList.map((w, idx) => (
              <div key={idx} className="flex items-start gap-2 p-2.5 rounded-lg bg-ocean-800/30 border border-ocean-700/30 hover:bg-ocean-800/50 transition-colors">
                <RiskBadge level={w.riskLevel} size="sm" />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-0.5">
                    <span className="text-xs text-cyan-300 font-semibold">{w.location}</span>
                    <span className="text-[10px] text-gray-500">{w.date}</span>
                  </div>
                  <p className="text-[11px] text-gray-400 truncate">{w.suggestion}</p>
                </div>
              </div>
            ))}
          </div>
        </ChartCard>
      </div>
    </div>
  );
};

export default FutureTrend;
