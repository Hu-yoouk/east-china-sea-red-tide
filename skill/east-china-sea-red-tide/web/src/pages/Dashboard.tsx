import React from 'react';
import ReactECharts from 'echarts-for-react';
import StatCard from '../components/StatCard';
import RiskBadge from '../components/RiskBadge';
import ChartCard from '../components/ChartCard';
import { useData } from '../services/dataContext';

const Dashboard: React.FC = () => {
  const { dashboardStats, timeSeriesPoints, geoData, warningList } = useData();

  const highRiskLevel = (dashboardStats?.redTideRate ?? 0) > 0.5 ? '高风险' : (dashboardStats?.redTideRate ?? 0) > 0.25 ? '中风险' : '低风险';

  const recentPoints = timeSeriesPoints.slice(-60);

  const riskIndexOption = {
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(10,22,40,0.9)',
      borderColor: '#1e64c8',
      textStyle: { color: '#e0f0ff' },
    },
    legend: {
      data: ['风险指数', '叶绿素'],
      textStyle: { color: '#8ab4d6' },
      top: 0,
    },
    grid: { left: '3%', right: '4%', bottom: '3%', top: '40px', containLabel: true },
    xAxis: {
      type: 'category',
      data: recentPoints.map(d => d.date.slice(2)),
      axisLine: { lineStyle: { color: '#1e3a5f' } },
      axisLabel: { color: '#8ab4d6', fontSize: 10, rotate: 45 },
    },
    yAxis: {
      type: 'value',
      name: '风险指数',
      axisLine: { lineStyle: { color: '#1e3a5f' } },
      axisLabel: { color: '#8ab4d6' },
      splitLine: { lineStyle: { color: 'rgba(30,58,95,0.4)' } },
    },
    series: [
      {
        name: '风险指数',
        type: 'line',
        data: recentPoints.map(d => d.riskIndex),
        smooth: true,
        lineStyle: { color: '#00d4ff', width: 2 },
        itemStyle: { color: '#00d4ff' },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0, y: 0, x2: 0, y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(0,212,255,0.3)' },
              { offset: 1, color: 'rgba(0,212,255,0.02)' },
            ],
          },
        },
      },
      {
        name: '叶绿素',
        type: 'line',
        data: recentPoints.map(d => +(d.chlorophyll * 5).toFixed(1)),
        smooth: true,
        lineStyle: { color: '#00e676', width: 1.5, type: 'dashed' },
        itemStyle: { color: '#00e676' },
      },
    ],
  };

  const currentRiskValue = Math.round((dashboardStats?.redTideRate ?? 0) * 100);

  const gaugeOption = {
    series: [
      {
        type: 'gauge',
        startAngle: 210,
        endAngle: -30,
        center: ['50%', '55%'],
        radius: '85%',
        min: 0,
        max: 100,
        axisLine: {
          show: true,
          lineStyle: {
            width: 18,
            color: [
              [0.25, '#22c55e'],
              [0.5, '#eab308'],
              [0.75, '#f97316'],
              [1, '#ef4444'],
            ],
          },
        },
        pointer: {
          show: true,
          length: '70%',
          width: 6,
          itemStyle: { color: '#00d4ff' },
        },
        axisTick: {
          distance: -18,
          length: 8,
          lineStyle: { width: 1, color: '#8ab4d6' },
        },
        splitLine: {
          distance: -22,
          length: 16,
          lineStyle: { width: 2, color: '#8ab4d6' },
        },
        axisLabel: {
          color: '#8ab4d6',
          distance: 30,
          fontSize: 11,
          formatter: (v: number) => v === 0 ? '低' : v === 50 ? '中' : v === 100 ? '高' : '',
        },
        anchor: { show: true, size: 16, itemStyle: { color: '#00d4ff' } },
        title: {
          show: true,
          offsetCenter: [0, '75%'],
          color: '#8ab4d6',
          fontSize: 13,
        },
        detail: {
          valueAnimation: true,
          formatter: '{value}%',
          color: '#fff',
          fontSize: 28,
          fontWeight: 'bold',
          offsetCenter: [0, '55%'],
        },
        data: [{ value: currentRiskValue, name: '风险率' }],
      },
    ],
  };

  const regionRanking = geoData
    .filter(g => g.sample_count >= 5)
    .sort((a, b) => b.risk_score - a.risk_score)
    .slice(0, 10)
    .map(g => ({
      name: `${g.longitude.toFixed(1)}°E ${g.latitude.toFixed(1)}°N`,
      riskScore: g.risk_score,
      riskLevel: g.risk_level,
      sampleCount: g.sample_count,
    }));

  const regionRankOption = {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
      backgroundColor: 'rgba(10,22,40,0.9)',
      borderColor: '#1e64c8',
      textStyle: { color: '#e0f0ff' },
    },
    grid: { left: '12%', right: '8%', bottom: '3%', top: '5px', containLabel: true },
    xAxis: {
      type: 'value',
      name: '风险评分',
      axisLine: { lineStyle: { color: '#1e3a5f' } },
      axisLabel: { color: '#8ab4d6' },
      splitLine: { lineStyle: { color: 'rgba(30,58,95,0.4)' } },
    },
    yAxis: {
      type: 'category',
      data: regionRanking.map(r => r.name).reverse(),
      axisLine: { lineStyle: { color: '#1e3a5f' } },
      axisLabel: { color: '#8ab4d6', fontSize: 10 },
    },
    series: [{
      type: 'bar',
      data: regionRanking.map(r => ({
        value: r.riskScore,
        itemStyle: {
          color: r.riskLevel === '极高风险' ? '#ef4444'
            : r.riskLevel === '高风险' ? '#f97316'
            : r.riskLevel === '中风险' ? '#eab308'
            : '#22c55e',
          borderRadius: [0, 4, 4, 0],
        },
      })).reverse(),
      barWidth: 16,
      label: { show: true, position: 'right', color: '#8ab4d6', fontSize: 10, formatter: '{c}' },
    }],
  };

  return (
    <div className="space-y-5">
      <div className="mb-2">
        <h2 className="page-title">海洋赤潮发生风险评估模型分析</h2>
        <p className="page-subtitle">
          基于叶绿素、水温、盐度、营养盐、气象等多源数据，构建赤潮发生风险评估模型，为海洋环境治理和赤潮预警提供决策支持
        </p>
      </div>

      <div className="grid grid-cols-6 gap-4">
        <StatCard
          title="整体风险等级"
          value={<RiskBadge level={highRiskLevel} size="lg" />}
          icon="⚠️"
        />
        <StatCard
          title="赤潮发生率"
          value={`${currentRiskValue}%`}
          icon="🎯"
          trend={currentRiskValue > 50 ? 'up' : 'down'}
          trendValue={currentRiskValue > 50 ? '需重点关注' : '当前较稳定'}
        />
        <StatCard
          title="监测网格数"
          value={dashboardStats?.monitoredCells ?? 0}
          unit="个"
          icon="🌐"
        />
        <StatCard
          title="数据样本总量"
          value={(dashboardStats?.totalSamples ?? 0).toLocaleString()}
          unit="条"
          icon="📦"
        />
        <StatCard
          title="赤潮事件数"
          value={dashboardStats?.redTideCount ?? 0}
          unit="次"
          icon="🔴"
        />
        <StatCard
          title="数据更新时间"
          value={dashboardStats?.lastUpdate?.slice(10) ?? '--'}
          icon="🕐"
        />
      </div>

      <div className="grid grid-cols-3 gap-5">
        <div className="col-span-2">
          <ChartCard title="历史赤潮风险指数变化趋势" subtitle={`${recentPoints.length}个月风险指数与叶绿素浓度趋势`}>
            <ReactECharts option={riskIndexOption} style={{ height: 340 }} />
          </ChartCard>
        </div>

        <ChartCard title="整体风险率仪表盘" subtitle="实时风险评估仪表盘">
          <ReactECharts option={gaugeOption} style={{ height: 340 }} />
        </ChartCard>
      </div>

      <div className="grid grid-cols-2 gap-5">
        <ChartCard title="高风险网格排行" subtitle="基于真实数据的风险评分排名">
          <ReactECharts option={regionRankOption} style={{ height: 300 }} />
        </ChartCard>

        <ChartCard title="预警建议" subtitle="基于风险评估的防控建议">
          <div className="space-y-3 mt-2">
            {warningList.slice(0, 4).map((w, idx) => (
              <div key={idx} className="flex items-start gap-3 p-3 rounded-lg bg-ocean-800/30 border border-ocean-700/30">
                <RiskBadge level={w.riskLevel} size="sm" />
                <div className="flex-1">
                  <p className="text-sm text-gray-200 font-medium">{w.location}</p>
                  <p className="text-xs text-gray-400 mt-1">{w.suggestion}</p>
                </div>
              </div>
            ))}
            {warningList.length === 0 && (
              <p className="text-sm text-gray-400 text-center py-6">当前各区域风险等级较低，维持例行监测</p>
            )}
          </div>
        </ChartCard>
      </div>

      <div className="text-center text-xs text-gray-600 py-4 border-t border-ocean-700/30">
        数据来源：integrated_database.db 真实监测数据 &nbsp;|&nbsp; 数据更新时间范围：{dashboardStats?.timeRange ?? '--'} &nbsp;|&nbsp; 系统更新于 {dashboardStats?.lastUpdate ?? '--'}
      </div>
    </div>
  );
};

export default Dashboard;
