import { useState, useEffect, useMemo } from 'react';
import ReactECharts from 'echarts-for-react';
import ChartCard from '../components/ChartCard';
import { useData } from '../services/dataContext';
import type { RawDataRecord } from '../types';

function exportCSV(records: RawDataRecord[], filename: string) {
  const headers = ['year', 'month', 'longitude', 'latitude', 'sst', 'chlorophyll', 'salinity',
    'nitrate', 'phosphate', 'silicate', 'wind_speed', 'pressure', 'solar_radiation', 'precipitation',
    'red_tide_label', 'red_tide_area', 'red_tide_organism', 'red_tide_toxicity'];
  const headerNames = ['年份', '月份', '经度', '纬度', '海温(℃)', '叶绿素', '盐度', '硝酸盐', '磷酸盐', '硅酸盐', '风速(m/s)', '气压(hPa)', '太阳辐射(W/m²)', '降水量(mm)', '赤潮标签', '赤潮面积', '藻种', '毒性'];
  const csvRows = [headerNames.join(',')];
  records.forEach(r => {
    csvRows.push(headers.map(h => {
      const v = r[h as keyof RawDataRecord];
      if (typeof v === 'string' && (v.includes(',') || v.includes('"'))) return `"${v.replace(/"/g, '""')}"`;
      return String(v ?? '');
    }).join(','));
  });
  const blob = new Blob(['﻿' + csvRows.join('\n')], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url; a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

const DataProcessing: React.FC = () => {
  const { stats, geoData, samplesIndex, loadSamplePage, dataProcessSteps } = useData();
  const [page, setPage] = useState(1);
  const [records, setRecords] = useState<RawDataRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [searchYear, setSearchYear] = useState('');
  const [selectedRisk, setSelectedRisk] = useState('全部');

  const totalPages = samplesIndex?.total_pages ?? 1;

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    loadSamplePage(page).then(data => {
      if (!cancelled) { setRecords(data); setLoading(false); }
    }).catch(() => { if (!cancelled) setLoading(false); });
    return () => { cancelled = true; };
  }, [page, loadSamplePage]);

  const filteredRecords = useMemo(() => {
    return records.filter(r => {
      if (searchYear && String(r.year) !== searchYear) return false;
      if (selectedRisk === '赤潮事件' && r.red_tide_label !== 1) return false;
      if (selectedRisk === '正常' && r.red_tide_label !== 0) return false;
      return true;
    });
  }, [records, searchYear, selectedRisk]);

  const chlBins = useMemo(() => {
    const all = geoData.map(g => g.avg_chlorophyll).filter(v => v != null);
    const bins = [
      all.filter(v => v < 1).length,
      all.filter(v => v >= 1 && v < 3).length,
      all.filter(v => v >= 3 && v < 5).length,
      all.filter(v => v >= 5 && v < 10).length,
      all.filter(v => v >= 10 && v < 20).length,
      all.filter(v => v >= 20).length,
    ];
    return bins;
  }, [geoData]);

  const chlDistOption = {
    tooltip: { trigger: 'axis', backgroundColor: 'rgba(10,22,40,0.9)', borderColor: '#1e64c8', textStyle: { color: '#e0f0ff' } },
    grid: { left: '3%', right: '4%', bottom: '3%', top: '10px', containLabel: true },
    xAxis: { type: 'category', data: ['<1', '1-3', '3-5', '5-10', '10-20', '20+'], axisLine: { lineStyle: { color: '#1e3a5f' } }, axisLabel: { color: '#8ab4d6' } },
    yAxis: { type: 'value', name: '网格数', axisLine: { lineStyle: { color: '#1e3a5f' } }, axisLabel: { color: '#8ab4d6' }, splitLine: { lineStyle: { color: 'rgba(30,58,95,0.4)' } } },
    series: [{
      type: 'bar',
      data: chlBins,
      itemStyle: { color: '#00d4ff', borderRadius: [6, 6, 0, 0] },
      barWidth: '50%',
    }],
  };

  const riskDistData = useMemo(() => {
    const low = geoData.filter(g => g.risk_level === '低风险').length;
    const mid = geoData.filter(g => g.risk_level === '中风险').length;
    const high = geoData.filter(g => g.risk_level === '高风险').length;
    return [
      { value: low, name: '低风险', itemStyle: { color: '#22c55e' } },
      { value: mid, name: '中风险', itemStyle: { color: '#eab308' } },
      { value: high, name: '高风险', itemStyle: { color: '#f97316' } },
    ];
  }, [geoData]);

  const riskDistOption = {
    tooltip: { trigger: 'item', backgroundColor: 'rgba(10,22,40,0.9)', borderColor: '#1e64c8', textStyle: { color: '#e0f0ff' } },
    legend: { orient: 'vertical', right: '5%', top: 'center', textStyle: { color: '#8ab4d6' }, itemWidth: 12, itemHeight: 12 },
    series: [{
      type: 'pie', radius: ['55%', '75%'], center: ['40%', '50%'], label: { show: false },
      emphasis: { label: { show: true, fontSize: 14, fontWeight: 'bold' } },
      data: riskDistData,
    }],
  };

  return (
    <div className="space-y-5 animate-fade-in">
      <div>
        <h2 className="page-title">数据采集与处理</h2>
        <p className="page-subtitle">多源海洋环境数据采集、清洗、融合与特征工程处理流程</p>
      </div>

      {/* 数据概览 */}
      <div className="grid grid-cols-6 gap-3">
        {[
          { title: '总样本量', value: stats?.total_samples?.toLocaleString() ?? '--', icon: '📦', color: '#00d4ff' },
          { title: '监测网格', value: stats?.unique_grid_cells ?? '--', icon: '🌐', color: '#66d0ff' },
          { title: '赤潮事件', value: stats?.red_tide_count ?? '--', icon: '🔴', color: '#ff6b6b' },
          { title: '赤潮率', value: stats ? (stats.red_tide_rate * 100).toFixed(1) + '%' : '--', icon: '📊', color: '#ffd54f' },
          { title: '时间范围', value: stats?.time_range?.from ?? '--', icon: '📅', color: '#b39ddb' },
          { title: '空间范围', value: stats ? `${stats.spatial_extent.lat_min}-${stats.spatial_extent.lat_max}°N` : '--', icon: '🗺️', color: '#4fc3f7' },
        ].map((item, idx) => (
          <div key={idx} className="glass-card p-4 text-center">
            <span className="text-3xl block mb-2">{item.icon}</span>
            <p className="text-lg font-bold" style={{ color: item.color }}>{String(item.value)}</p>
            <p className="text-xs text-gray-400 mt-1">{item.title}</p>
          </div>
        ))}
      </div>

      {/* 数据处理流程 */}
      <ChartCard title="数据处理流程" subtitle="从原始数据到建模数据集的处理链路">
        <div className="flex items-center justify-between py-4 px-2 overflow-x-auto">
          {dataProcessSteps.map((step) => (
            <div key={step.step} className="flex flex-col items-center gap-2 min-w-[80px]">
              <div className="w-12 h-12 rounded-full bg-gradient-to-br from-cyan-500 to-blue-600 flex items-center justify-center text-xl shadow-lg shadow-cyan-500/20">
                {step.icon}
              </div>
              <span className="text-xs font-semibold text-cyan-300">{step.name}</span>
              <span className="text-[10px] text-gray-500 text-center leading-tight">{step.desc}</span>
            </div>
          )).reduce((acc: React.ReactNode[], curr, idx) => {
            acc.push(curr);
            if (idx < dataProcessSteps.length - 1) {
              acc.push(<div key={`line-${idx}`} className="flex-1 h-0.5 bg-gradient-to-r from-cyan-500/50 to-blue-600/50 mx-2 min-w-[30px]" />);
            }
            return acc;
          }, [])}
        </div>
      </ChartCard>

      {/* 数据分布图 */}
      <div className="grid grid-cols-2 gap-5">
        <ChartCard title="叶绿素浓度分布" subtitle={`${geoData.length}个网格叶绿素均值直方图`}>
          <ReactECharts option={chlDistOption} style={{ height: 250 }} />
        </ChartCard>
        <ChartCard title="风险等级分布" subtitle={`${geoData.length}个网格风险等级占比`}>
          <ReactECharts option={riskDistOption} style={{ height: 250 }} />
        </ChartCard>
      </div>

      {/* 数据表格 */}
      <div className="glass-card p-5 ocean-glow">
        <div className="flex items-center justify-between mb-4 flex-wrap gap-3">
          <h3 className="section-title mb-0 pb-0 border-0">
            原始监测数据
            <span className="text-xs text-gray-500 ml-2 font-normal">
              共 {samplesIndex?.total_records?.toLocaleString() ?? 0} 条记录，{totalPages} 页
            </span>
          </h3>
          <div className="flex gap-3 flex-wrap">
            <select className="input-field w-auto text-sm py-1.5" value={selectedRisk} onChange={e => setSelectedRisk(e.target.value)}>
              <option value="全部">全部记录</option>
              <option value="赤潮事件">仅赤潮事件</option>
              <option value="正常">仅正常记录</option>
            </select>
            <input type="text" placeholder="搜索年份..." className="input-field w-auto text-sm py-1.5" value={searchYear} onChange={e => setSearchYear(e.target.value)} />
            <button onClick={() => exportCSV(filteredRecords, `赤潮监测数据_第${page}页.csv`)} className="px-4 py-1.5 rounded-lg bg-cyan-500/20 text-cyan-300 text-xs border border-cyan-500/30 hover:bg-cyan-500/30 transition-colors">
              导出 CSV
            </button>
          </div>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-ocean-700/50 text-gray-400 text-xs">
                <th className="py-2 px-2 text-left">年-月</th>
                <th className="py-2 px-2 text-right">经度</th>
                <th className="py-2 px-2 text-right">纬度</th>
                <th className="py-2 px-2 text-right">海温℃</th>
                <th className="py-2 px-2 text-right">叶绿素</th>
                <th className="py-2 px-2 text-right">盐度</th>
                <th className="py-2 px-2 text-right">硝酸盐</th>
                <th className="py-2 px-2 text-right">磷酸盐</th>
                <th className="py-2 px-2 text-right">硅酸盐</th>
                <th className="py-2 px-2 text-right">风速</th>
                <th className="py-2 px-2 text-center">赤潮标签</th>
                <th className="py-2 px-2 text-right">面积</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan={12} className="py-8 text-center text-gray-400">加载中...</td></tr>
              ) : filteredRecords.length === 0 ? (
                <tr><td colSpan={12} className="py-8 text-center text-gray-400">无匹配数据</td></tr>
              ) : (
                filteredRecords.map(r => (
                  <tr key={r.id} className="border-b border-ocean-700/20 hover:bg-ocean-800/30 transition-colors text-xs">
                    <td className="py-2 px-2 text-gray-300">{r.year}-{String(r.month).padStart(2, '0')}</td>
                    <td className="py-2 px-2 text-right text-cyan-300">{r.longitude?.toFixed(4)}</td>
                    <td className="py-2 px-2 text-right text-cyan-300">{r.latitude?.toFixed(4)}</td>
                    <td className="py-2 px-2 text-right text-orange-400">{r.sst?.toFixed(1)}</td>
                    <td className="py-2 px-2 text-right text-green-400">{r.chlorophyll?.toFixed(2)}</td>
                    <td className="py-2 px-2 text-right text-blue-300">{r.salinity?.toFixed(1)}</td>
                    <td className="py-2 px-2 text-right text-gray-300">{r.nitrate?.toFixed(2)}</td>
                    <td className="py-2 px-2 text-right text-gray-300">{r.phosphate?.toFixed(3)}</td>
                    <td className="py-2 px-2 text-right text-gray-300">{r.silicate?.toFixed(2)}</td>
                    <td className="py-2 px-2 text-right text-gray-300">{r.wind_speed?.toFixed(1)}</td>
                    <td className="py-2 px-2 text-center">{r.red_tide_label === 1 ? <span className="text-red-400">● 是</span> : <span className="text-green-400">○ 否</span>}</td>
                    <td className="py-2 px-2 text-right text-purple-300">{r.red_tide_area ?? '-'}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* 分页 */}
        <div className="flex items-center justify-between mt-4 text-xs text-gray-400">
          <span>第 {page} 页 / 共 {totalPages} 页 · 每页 {samplesIndex?.per_page ?? 500} 条</span>
          <div className="flex gap-2">
            <button onClick={() => setPage(p => Math.max(1, p - 1))} disabled={page === 1} className="btn-secondary !px-3 !py-1 disabled:opacity-40">上一页</button>
            <select className="input-field w-auto text-xs py-1 px-2" value={page} onChange={e => setPage(Number(e.target.value))}>
              {Array.from({ length: Math.min(totalPages, 50) }, (_, i) => i + 1).map(p => (
                <option key={p} value={p}>{p}</option>
              ))}
            </select>
            <button onClick={() => setPage(p => Math.min(totalPages, p + 1))} disabled={page >= totalPages} className="btn-secondary !px-3 !py-1 disabled:opacity-40">下一页</button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default DataProcessing;
