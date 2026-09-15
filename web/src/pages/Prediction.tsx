import React, { useState } from 'react';
import ReactECharts from 'echarts-for-react';
import ChartCard from '../components/ChartCard';
import RiskBadge from '../components/RiskBadge';
import { predictRisk } from '../utils/riskModel';

const defaultInputs = {
  chlorophyll: 12.5, sst: 25.0, salinity: 30.0,
  wind_speed: 3.0, solar_radiation: 700,
  pressure: 1008, nitrate: 8.0, phosphate: 1.2, silicate: 5.0, precipitation: 50,
};

const Prediction: React.FC = () => {
  const [inputs, setInputs] = useState(defaultInputs);
  const [result, setResult] = useState<ReturnType<typeof predictRisk> | null>(null);
  const [history, setHistory] = useState<Array<{ time: string; prob: number; level: string }>>([]);

  const handlePredict = () => {
    const res = predictRisk(inputs);
    setResult(res);
    setHistory(prev => [{ time: new Date().toLocaleTimeString(), prob: res.probability, level: res.riskLevel }, ...prev.slice(0, 9)]);
  };

  const contributionOption = result ? {
    tooltip: { trigger: 'axis', backgroundColor: 'rgba(10,22,40,0.9)', borderColor: '#1e64c8', textStyle: { color: '#e0f0ff' } },
    grid: { left: '3%', right: '10%', bottom: '3%', top: '5px', containLabel: true },
    xAxis: { type: 'value', name: '贡献分', axisLine: { lineStyle: { color: '#1e3a5f' } }, axisLabel: { color: '#8ab4d6' }, splitLine: { lineStyle: { color: 'rgba(30,58,95,0.4)' } } },
    yAxis: { type: 'category', data: result.mainFactors.map(f => f.factor).reverse(), axisLine: { lineStyle: { color: '#1e3a5f' } }, axisLabel: { color: '#8ab4d6' } },
    series: [{
      type: 'bar', barWidth: 18,
      data: result.mainFactors.map(f => ({ value: f.contribution, itemStyle: { color: f.contribution > 12 ? '#ef4444' : f.contribution > 8 ? '#f97316' : f.contribution > 4 ? '#eab308' : '#22c55e', borderRadius: [0, 4, 4, 0] } })).reverse(),
      label: { show: true, position: 'right', color: '#8ab4d6', fontSize: 11 },
    }],
  } : null;

  const fields = [
    { key: 'chlorophyll', label: '叶绿素浓度', unit: 'μg/L', min: 0, max: 30, step: 0.1 },
    { key: 'sst', label: '水温', unit: '℃', min: 0, max: 40, step: 0.1 },
    { key: 'salinity', label: '盐度', unit: 'PSU', min: 0, max: 45, step: 0.1 },
    { key: 'wind_speed', label: '风速', unit: 'm/s', min: 0, max: 20, step: 0.1 },
    { key: 'solar_radiation', label: '太阳辐射', unit: 'W/m²', min: 0, max: 1200, step: 10 },
    { key: 'pressure', label: '气压', unit: 'hPa', min: 980, max: 1030, step: 0.1 },
    { key: 'nitrate', label: '硝酸盐', unit: 'μmol/L', min: 0, max: 50, step: 0.1 },
    { key: 'phosphate', label: '磷酸盐', unit: 'μmol/L', min: 0, max: 5, step: 0.1 },
    { key: 'silicate', label: '硅酸盐', unit: 'μmol/L', min: 0, max: 50, step: 0.1 },
    { key: 'precipitation', label: '降水量', unit: 'mm', min: 0, max: 500, step: 1 },
  ];

  return (
    <div className="space-y-5 animate-fade-in">
      <div><h2 className="page-title">赤潮风险预测</h2><p className="page-subtitle">输入海洋环境参数，智能评估赤潮发生概率与风险等级</p></div>
      <div className="grid grid-cols-3 gap-5">
        <div className="glass-card p-5 ocean-glow">
          <h3 className="section-title">环境参数输入</h3>
          <div className="space-y-3 max-h-[520px] overflow-y-auto pr-1">
            {fields.map(f => (
              <div key={f.key}>
                <label className="text-xs text-gray-400 block mb-1">{f.label} ({f.unit})</label>
                <div className="flex gap-2 items-center">
                  <input type="range" min={f.min} max={f.max} step={f.step} value={inputs[f.key as keyof typeof inputs]} onChange={e => setInputs(prev => ({ ...prev, [f.key]: parseFloat(e.target.value) || 0 }))} className="flex-1 h-1.5 accent-cyan-400" />
                  <input type="number" value={inputs[f.key as keyof typeof inputs]} onChange={e => setInputs(prev => ({ ...prev, [f.key]: parseFloat(e.target.value) || 0 }))} className="input-field w-20 text-sm py-1 text-center" step={f.step} />
                </div>
              </div>
            ))}
          </div>
          <div className="flex gap-3 mt-5">
            <button onClick={handlePredict} className="btn-primary flex-1 text-sm">开始预测</button>
            <button onClick={() => { setInputs(defaultInputs); setResult(null); }} className="btn-secondary text-sm">重置参数</button>
          </div>
        </div>
        <div className="col-span-2 space-y-5">
          {result ? (
            <>
              <div className="grid grid-cols-4 gap-4">
                {[
                  { label: '风险评分', value: result.riskScore, unit: '分', color: '#fff' },
                  { label: '发生概率', value: `${result.probability}%`, unit: '', color: '#00d4ff' },
                  { label: '风险等级', value: <RiskBadge level={result.riskLevel} size="lg" />, unit: '', color: '' },
                  { label: '历史预测', value: `${history.length}次`, unit: '', color: '#1e90ff' },
                ].map((item, i) => (
                  <div key={i} className="glass-card p-4 text-center ocean-glow">
                    <p className="text-xs text-gray-400 mb-2">{item.label}</p>
                    {typeof item.value === 'string' ? <p className="text-3xl font-bold" style={{ color: item.color }}>{item.value}</p> : item.value}
                  </div>
                ))}
              </div>
              <div className="grid grid-cols-2 gap-5">
                <ChartCard title="主要贡献因素" subtitle="各环境因子对当前风险的贡献分">
                  {contributionOption && <ReactECharts option={contributionOption} style={{ height: 240 }} />}
                </ChartCard>
                <div className="glass-card p-4 ocean-glow">
                  <h3 className="section-title">风险解释与建议</h3>
                  <div className="space-y-3 max-h-[200px] overflow-y-auto">
                    {result.mainFactors.map((f, idx) => (
                      <div key={idx} className="p-2.5 rounded-lg bg-ocean-800/30 border border-ocean-700/30">
                        <div className="flex justify-between mb-1"><span className="text-sm font-semibold text-cyan-300">{f.factor}</span><span className="text-xs text-gray-500">贡献 {f.contribution} 分</span></div>
                        <p className="text-xs text-gray-400">{f.description}</p>
                      </div>
                    ))}
                  </div>
                  <div className="mt-4 pt-4 border-t border-ocean-700/30">
                    <h4 className="text-sm font-semibold text-green-400 mb-2">防控建议</h4>
                    <ul className="space-y-1.5">
                      {result.suggestions.map((s, idx) => (
                        <li key={idx} className="text-xs text-gray-300 flex gap-2"><span className="text-cyan-400">◆</span>{s}</li>
                      ))}
                    </ul>
                  </div>
                </div>
              </div>
            </>
          ) : (
            <div className="glass-card p-12 flex flex-col items-center justify-center ocean-glow" style={{ minHeight: 400 }}>
              <span className="text-6xl mb-4">🎯</span>
              <p className="text-gray-400 text-lg">请调整左侧参数后点击"开始预测"</p>
              <p className="text-gray-600 text-sm mt-2">系统将根据多源环境参数综合评估赤潮风险</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default Prediction;
