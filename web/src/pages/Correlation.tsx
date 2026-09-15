import { useMemo } from 'react';
import ReactECharts from 'echarts-for-react';
import ChartCard from '../components/ChartCard';
import { useData } from '../services/dataContext';

function getCorrelationColor(v: number): string {
  const absV = Math.abs(v);
  if (absV >= 0.8) return '#ef4444';
  if (absV >= 0.6) return '#f97316';
  if (absV >= 0.4) return '#eab308';
  if (absV >= 0.2) return '#84cc16';
  return '#22c55e';
}

export default function Correlation() {
  const { correlation } = useData();

  const redTideIdx = correlation ? correlation.labels.length - 1 : -1;
  const redTideCorr = correlation
    ? correlation.labels.slice(0, -1).map((label, i) => ({
        factor: label,
        correlation: correlation.matrix[i][redTideIdx],
      })).sort((a, b) => Math.abs(b.correlation) - Math.abs(a.correlation))
    : [];

  if (!correlation) {
    return (
      <div className="space-y-5 animate-fade-in">
        <div><h2 className="page-title">相关性分析</h2><p className="page-subtitle">分析各环境因子之间的相关性</p></div>
        <div className="glass-card p-12 flex flex-col items-center justify-center ocean-glow" style={{ minHeight: 400 }}>
          <p className="text-gray-400 text-lg">正在加载相关性数据...</p>
        </div>
      </div>
    );
  }

  const heatmapOption = useMemo(() => {
    const data: [number, number, number][] = [];
    for (let i = 0; i < correlation.labels.length; i++) {
      for (let j = 0; j < correlation.labels.length; j++) {
        data.push([j, i, correlation.matrix[i][j]]);
      }
    }

    return {
      tooltip: {
        backgroundColor: 'rgba(10,22,40,0.95)',
        borderColor: '#1e64c8',
        textStyle: { color: '#e0f0ff', fontSize: 12 },
        formatter: (p: { value: number[] }) => {
          const [x, y, v] = p.value;
          const a = correlation.labels[y];
          const b = correlation.labels[x];
          const strength = Math.abs(v) >= 0.7 ? '强' : Math.abs(v) >= 0.4 ? '中等' : Math.abs(v) >= 0.2 ? '弱' : '极弱';
          const dir = v > 0 ? '正' : v < 0 ? '负' : '无';
          return `${a} ↔ ${b}<br/>相关系数: <b>${v.toFixed(3)}</b><br/>${strength}${dir}相关`;
        },
      },
      grid: { left: '12%', right: '5%', bottom: '8%', top: '5%' },
      xAxis: {
        type: 'category',
        data: correlation.labels,
        axisLine: { lineStyle: { color: '#1e3a5f' } },
        axisLabel: { color: '#8ab4d6', fontSize: 11, rotate: 45 },
        position: 'top',
      },
      yAxis: {
        type: 'category',
        data: correlation.labels,
        axisLine: { lineStyle: { color: '#1e3a5f' } },
        axisLabel: { color: '#8ab4d6', fontSize: 11 },
      },
      visualMap: {
        min: -1,
        max: 1,
        calculable: true,
        orient: 'vertical',
        right: 10,
        top: 'center',
        text: ['1', '0', '-1'],
        textStyle: { color: '#8ab4d6' },
        inRange: {
          color: ['#1e40af', '#3b82f6', '#60a5fa', '#334155', '#f59e0b', '#f97316', '#ef4444']
        },
      },
      series: [{
        type: 'heatmap',
        data,
        label: {
          show: true,
          color: '#e0f0ff',
          fontSize: 10,
          formatter: (p: { value: number[] }) => (p.value[2] as number).toFixed(2),
        },
        emphasis: {
          itemStyle: { shadowBlur: 10, shadowColor: 'rgba(0, 212, 255, 0.5)' },
        },
      }],
    };
  }, [correlation]);

  const redTideCorrOption = {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      backgroundColor: 'rgba(10,22,40,0.9)',
      borderColor: '#1e64c8',
      textStyle: { color: '#e0f0ff' },
      formatter: (p: { value: number; name: string }[]) => `${p[0].name}<br/>与赤潮相关系数: <b>${p[0].value.toFixed(3)}</b>`,
    },
    grid: { left: '3%', right: '8%', bottom: '3%', top: '5px', containLabel: true },
    xAxis: {
      type: 'value',
      name: '相关系数',
      min: -1,
      max: 1,
      axisLine: { lineStyle: { color: '#1e3a5f' } },
      axisLabel: { color: '#8ab4d6' },
      splitLine: { lineStyle: { color: 'rgba(30,58,95,0.4)' } },
    },
    yAxis: {
      type: 'category',
      data: redTideCorr.map(r => r.factor).reverse(),
      axisLine: { lineStyle: { color: '#1e3a5f' } },
      axisLabel: { color: '#8ab4d6' },
    },
    series: [{
      type: 'bar',
      data: redTideCorr.map(r => ({
        value: r.correlation,
        itemStyle: {
          color: getCorrelationColor(r.correlation),
          borderRadius: r.correlation >= 0 ? [0, 4, 4, 0] : [4, 0, 0, 4],
        },
      })).reverse(),
      barWidth: 20,
      label: {
        show: true,
        position: 'right',
        color: '#8ab4d6',
        fontSize: 10,
        formatter: (p: { value: number }) => p.value.toFixed(3),
      },
      markLine: {
        silent: true,
        symbol: 'none',
        data: [
          { xAxis: 0, lineStyle: { color: '#6b7280', type: 'dashed', width: 1 } },
        ],
      },
    }],
  };

  const topPositive = redTideCorr.filter(r => r.correlation > 0).slice(0, 3);
  const topNegative = redTideCorr.filter(r => r.correlation < 0).slice(-3).reverse();

  return (
    <div className="space-y-5 animate-fade-in">
      <div>
        <h2 className="page-title">相关性分析</h2>
        <p className="page-subtitle">分析各环境因子之间的相关性，以及与赤潮发生的关联强度</p>
      </div>

      {/* Correlation heatmap */}
      <ChartCard title="环境因子相关性热力图" subtitle="矩阵显示各因子之间的 Pearson 相关系数（红=正相关，蓝=负相关）">
        <ReactECharts option={heatmapOption} style={{ height: 480 }} />
      </ChartCard>

      <div className="grid grid-cols-2 gap-5">
        {/* Red tide correlation bar chart */}
        <ChartCard title="各因子与赤潮发生相关系数" subtitle="条柱越长表示与赤潮发生的关联越强，红色=正相关，绿色=负相关">
          <ReactECharts option={redTideCorrOption} style={{ height: 320 }} />
        </ChartCard>

        {/* Key findings */}
        <ChartCard title="关键发现" subtitle="基于真实监测数据的相关分析结果">
          <div className="space-y-3 mt-2">
            {/* Positive correlations */}
            <div className="p-4 rounded-lg bg-ocean-800/30 border border-ocean-700/30">
              <h4 className="text-sm font-semibold text-orange-400 mb-2">促进赤潮发生的主要因子（正相关）</h4>
              <div className="space-y-1.5">
                {topPositive.map((item, i) => (
                  <div key={i} className="flex items-center justify-between text-xs">
                    <span className="text-gray-300">{i + 1}. {item.factor}</span>
                    <span className="text-orange-400 font-mono font-semibold">{item.correlation.toFixed(3)}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Negative correlations */}
            <div className="p-4 rounded-lg bg-ocean-800/30 border border-ocean-700/30">
              <h4 className="text-sm font-semibold text-green-400 mb-2">抑制赤潮发生的主要因子（负相关）</h4>
              <div className="space-y-1.5">
                {topNegative.map((item, i) => (
                  <div key={i} className="flex items-center justify-between text-xs">
                    <span className="text-gray-300">{i + 1}. {item.factor}</span>
                    <span className="text-green-400 font-mono font-semibold">{item.correlation.toFixed(3)}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Strongest pairwise */}
            <div className="p-4 rounded-lg bg-ocean-800/30 border border-ocean-700/30">
              <h4 className="text-sm font-semibold text-cyan-300 mb-2">最强因子间关联（非赤潮）</h4>
              <div className="space-y-1.5">
                {(() => {
                  const pairs: { a: string; b: string; v: number }[] = [];
                  const labels = correlation.labels;
                  for (let i = 0; i < labels.length - 1; i++) {
                    for (let j = i + 1; j < labels.length - 1; j++) {
                      pairs.push({ a: labels[i], b: labels[j], v: correlation.matrix[i][j] });
                    }
                  }
                  pairs.sort((a, b) => Math.abs(b.v) - Math.abs(a.v));
                  return pairs.slice(0, 3).map((pair, i) => (
                    <div key={i} className="flex items-center justify-between text-xs">
                      <span className="text-gray-300">{i + 1}. {pair.a} ↔ {pair.b}</span>
                      <span className={`font-mono font-semibold ${pair.v >= 0 ? 'text-orange-400' : 'text-green-400'}`}>
                        {pair.v.toFixed(3)}
                      </span>
                    </div>
                  ));
                })()}
              </div>
            </div>
          </div>
        </ChartCard>
      </div>
    </div>
  );
}
