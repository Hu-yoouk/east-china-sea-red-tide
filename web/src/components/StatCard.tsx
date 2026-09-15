import React from 'react';

interface StatCardProps {
  title: string;
  value: React.ReactNode;
  unit?: string;
  icon?: string;
  color?: string;
  trend?: 'up' | 'down' | 'stable';
  trendValue?: string;
}

const StatCard: React.FC<StatCardProps> = ({ title, value, unit, icon, color = '#00d4ff', trend, trendValue }) => {
  const trendColors = { up: '#22c55e', down: '#ef4444', stable: '#eab308' };
  const trendIcons = { up: '↑', down: '↓', stable: '→' };

  return (
    <div className="glass-card p-5 ocean-glow hover:scale-[1.02] transition-transform duration-300">
      <div className="flex items-center justify-between mb-3">
        <span className="text-sm text-gray-400">{title}</span>
        {icon && <span className="text-2xl">{icon}</span>}
      </div>
      <div className="flex items-baseline gap-1">
        <span className="stat-value" style={{ color }}>{value}</span>
        {unit && <span className="text-sm text-gray-400">{unit}</span>}
      </div>
      {trend && (
        <div className="flex items-center gap-1 mt-2" style={{ color: trendColors[trend] }}>
          <span>{trendIcons[trend]}</span>
          <span className="text-xs">{trendValue}</span>
        </div>
      )}
    </div>
  );
};

export default StatCard;
