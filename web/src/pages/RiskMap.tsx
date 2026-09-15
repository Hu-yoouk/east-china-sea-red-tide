import { useState, useEffect, useRef, useMemo } from 'react';
import { MapContainer, TileLayer, CircleMarker, Popup, Tooltip } from 'react-leaflet';
import 'leaflet/dist/leaflet.css';
import ChartCard from '../components/ChartCard';
import RiskBadge from '../components/RiskBadge';
import { useData } from '../services/dataContext';
import ReactECharts from 'echarts-for-react';

const getColor = (level: string): string => {
  switch (level) {
    case '低风险': return '#22c55e';
    case '中风险': return '#eab308';
    case '高风险': return '#f97316';
    case '极高风险': return '#ef4444';
    default: return '#6b7280';
  }
};

const RiskMap: React.FC = () => {
  const { geoData, timeSeries } = useData();

  const allDates = useMemo(() => {
    return timeSeries.map(t => `${t.year}-${String(t.month).padStart(2, '0')}`);
  }, [timeSeries]);

  const [dateIdx, setDateIdx] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const currentDate = allDates[dateIdx] || '';

  // Filter geoData - always show all grid cells (they all have risk scores from full dataset)
  const mapCenter: [number, number] = geoData.length > 0
    ? [geoData.reduce((s, g) => s + g.latitude, 0) / geoData.length,
       geoData.reduce((s, g) => s + g.longitude, 0) / geoData.length]
    : [28.5, 120];

  // Playback effect
  useEffect(() => {
    if (isPlaying) {
      timerRef.current = setInterval(() => {
        setDateIdx(prev => {
          if (prev >= allDates.length - 1) {
            setIsPlaying(false);
            return prev;
          }
          return prev + 1;
        });
      }, 600);
    } else {
      if (timerRef.current) clearInterval(timerRef.current);
    }
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
  }, [isPlaying, allDates.length]);

  // Handle empty state
  if (geoData.length === 0) {
    return (
      <div className="space-y-5 animate-fade-in">
        <div><h2 className="page-title">赤潮风险地图</h2><p className="page-subtitle">中国近海赤潮发生风险空间分布</p></div>
        <div className="glass-card p-12 flex flex-col items-center justify-center ocean-glow" style={{ minHeight: 400 }}>
          <p className="text-gray-400 text-lg">正在加载数据...</p>
        </div>
      </div>
    );
  }

  const topCells = [...geoData].sort((a, b) => b.risk_score - a.risk_score).slice(0, 8);

  const barOption = {
    tooltip: { trigger: 'axis', backgroundColor: 'rgba(10,22,40,0.9)', borderColor: '#1e64c8', textStyle: { color: '#e0f0ff' } },
    grid: { left: '3%', right: '4%', bottom: '3%', top: '5px', containLabel: true },
    xAxis: { type: 'category', data: topCells.map(g => `${g.longitude.toFixed(1)}°E\n${g.latitude.toFixed(1)}°N`), axisLine: { lineStyle: { color: '#1e3a5f' } }, axisLabel: { color: '#8ab4d6', fontSize: 9 } },
    yAxis: { type: 'value', name: '风险评分', axisLine: { lineStyle: { color: '#1e3a5f' } }, axisLabel: { color: '#8ab4d6' }, splitLine: { lineStyle: { color: 'rgba(30,58,95,0.4)' } } },
    series: [{
      type: 'bar',
      data: topCells.map(g => ({ value: g.risk_score, itemStyle: { color: getColor(g.risk_level), borderRadius: [6, 6, 0, 0] } })),
      barWidth: '50%',
    }],
  };

  const selectedCell = geoData.sort((a, b) => b.risk_score - a.risk_score)[0];

  return (
    <div className="space-y-5 animate-fade-in">
      <div>
        <h2 className="page-title">赤潮风险地图</h2>
        <p className="page-subtitle">中国近海赤潮发生风险空间分布 · 共 {geoData.length} 个监测网格</p>
      </div>

      <div className="grid grid-cols-3 gap-5">
        <div className="col-span-2 space-y-3">
          <div className="glass-card overflow-hidden ocean-glow" style={{ height: 450 }}>
            <MapContainer
              center={mapCenter}
              zoom={5}
              style={{ height: '100%', width: '100%', borderRadius: 12 }}
              zoomControl={true}
            >
              <TileLayer
                attribution='&copy; <a href="https://carto.com/">CARTO</a>'
                url="https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}{r}.png"
              />
              {geoData.map(g => (
                <CircleMarker
                  key={`${g.longitude}_${g.latitude}`}
                  center={[g.latitude, g.longitude]}
                  radius={Math.max(8, Math.min(22, g.risk_score * 0.22))}
                  pathOptions={{
                    fillColor: getColor(g.risk_level),
                    color: getColor(g.risk_level),
                    fillOpacity: 0.65,
                    weight: 1,
                  }}
                >
                  <Tooltip direction="top" offset={[0, -8]} opacity={0.95}>
                    <div style={{ fontSize: 13, fontWeight: 'bold' }}>
                      {g.longitude.toFixed(2)}°E, {g.latitude.toFixed(2)}°N
                    </div>
                    <div style={{ fontSize: 11 }}>风险: {g.risk_level} | 评分: {g.risk_score}</div>
                    <div style={{ fontSize: 11 }}>样本数: {g.sample_count} | 赤潮频次: {(g.red_tide_frequency * 100).toFixed(1)}%</div>
                  </Tooltip>
                  <Popup>
                    <div style={{ minWidth: 240, fontSize: 13 }}>
                      <h4 style={{ margin: '0 0 8px', color: '#1e90ff' }}>
                        {g.longitude.toFixed(3)}°E, {g.latitude.toFixed(3)}°N
                      </h4>
                      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '4px 12px' }}>
                        <span>风险评分:</span><strong style={{ color: getColor(g.risk_level) }}>{g.risk_score}</strong>
                        <span>风险等级:</span><strong style={{ color: getColor(g.risk_level) }}>{g.risk_level}</strong>
                        <span>样本数:</span><span>{g.sample_count}</span>
                        <span>赤潮频次:</span><span>{(g.red_tide_frequency * 100).toFixed(1)}%</span>
                        <span>叶绿素均值:</span><span>{g.avg_chlorophyll?.toFixed(2)}</span>
                        <span>海温均值:</span><span>{g.avg_sst?.toFixed(1)}℃</span>
                        <span>盐度均值:</span><span>{g.avg_salinity?.toFixed(1)}</span>
                        <span>硝酸盐均值:</span><span>{g.avg_nitrate?.toFixed(2)}</span>
                        <span>磷酸盐均值:</span><span>{g.avg_phosphate?.toFixed(3)}</span>
                        <span>硅酸盐均值:</span><span>{g.avg_silicate?.toFixed(2)}</span>
                      </div>
                      {g.organisms.length > 0 && (
                        <div style={{ marginTop: 8, padding: '6px 8px', background: 'rgba(0,212,255,0.08)', borderRadius: 4, fontSize: 12 }}>
                          <strong>藻种:</strong> {g.organisms.join(', ')}
                        </div>
                      )}
                    </div>
                  </Popup>
                </CircleMarker>
              ))}
            </MapContainer>
          </div>

          {/* Time animation controls */}
          <div className="glass-card p-4 ocean-glow">
            <div className="flex items-center gap-4">
              <button
                onClick={() => setIsPlaying(!isPlaying)}
                className="w-10 h-10 rounded-full bg-gradient-to-r from-cyan-500 to-blue-600 flex items-center justify-center text-white text-lg hover:shadow-lg hover:shadow-cyan-500/25 transition-all shrink-0"
              >
                {isPlaying ? '⏸' : '▶'}
              </button>
              <button
                onClick={() => setDateIdx(0)}
                className="px-3 py-1.5 rounded-lg bg-ocean-700/50 text-gray-400 text-xs border border-ocean-600/50 hover:text-gray-200 transition-colors shrink-0"
              >
                重置
              </button>
              <div className="flex-1">
                <input
                  type="range"
                  min={0}
                  max={allDates.length - 1}
                  value={dateIdx}
                  onChange={e => setDateIdx(Number(e.target.value))}
                  className="w-full h-2 rounded-full appearance-none cursor-pointer"
                  style={{
                    background: `linear-gradient(to right, #00d4ff ${(dateIdx / Math.max(1, allDates.length - 1)) * 100}%, rgba(30,58,95,0.5) ${(dateIdx / Math.max(1, allDates.length - 1)) * 100}%)`,
                    outline: 'none',
                  }}
                />
              </div>
              <span className="text-sm text-cyan-300 font-mono font-semibold min-w-[80px] text-right shrink-0">
                {currentDate}
              </span>
            </div>
            <p className="text-xs text-gray-500 mt-2 text-center">
              时间轴浏览 {allDates.length} 个月度数据 · 点击播放自动播放 · 当前: {currentDate}
            </p>
          </div>
        </div>

        <div className="space-y-5">
          <ChartCard title="高风险网格评分" subtitle="风险评分 TOP8">
            <ReactECharts option={barOption} style={{ height: 240 }} />
          </ChartCard>

          <div className="glass-card p-4 ocean-glow">
            <h3 className="text-sm font-semibold text-cyan-300 mb-3">最高风险网格详情</h3>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between py-1.5 border-b border-ocean-700/30">
                <span className="text-gray-400">位置</span>
                <span className="text-white font-semibold">{selectedCell.longitude.toFixed(3)}°E, {selectedCell.latitude.toFixed(3)}°N</span>
              </div>
              <div className="flex justify-between py-1.5 border-b border-ocean-700/30">
                <span className="text-gray-400">风险等级</span>
                <RiskBadge level={selectedCell.risk_level} size="sm" />
              </div>
              <div className="flex justify-between py-1.5 border-b border-ocean-700/30">
                <span className="text-gray-400">风险评分</span>
                <span className="text-cyan-300 font-semibold">{selectedCell.risk_score}</span>
              </div>
              <div className="flex justify-between py-1.5 border-b border-ocean-700/30">
                <span className="text-gray-400">赤潮频次</span>
                <span className="text-red-400">{(selectedCell.red_tide_frequency * 100).toFixed(1)}%</span>
              </div>
              <div className="flex justify-between py-1.5 border-b border-ocean-700/30">
                <span className="text-gray-400">样本数</span>
                <span className="text-blue-300">{selectedCell.sample_count}</span>
              </div>
              <div className="flex justify-between py-1.5 border-b border-ocean-700/30">
                <span className="text-gray-400">叶绿素均值</span>
                <span className="text-green-400">{selectedCell.avg_chlorophyll?.toFixed(2)}</span>
              </div>
              <div className="flex justify-between py-1.5">
                <span className="text-gray-400">海温均值</span>
                <span className="text-orange-400">{selectedCell.avg_sst?.toFixed(1)}℃</span>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default RiskMap;
