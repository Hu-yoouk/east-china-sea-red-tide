import React from 'react';

interface RiskBadgeProps {
  level: string;
  size?: 'sm' | 'md' | 'lg';
}

const colorMap: Record<string, string> = {
  '低风险': '#22c55e',
  '中风险': '#eab308',
  '高风险': '#f97316',
  '极高风险': '#ef4444',
};

const bgMap: Record<string, string> = {
  '低风险': 'rgba(34,197,94,0.15)',
  '中风险': 'rgba(234,179,8,0.15)',
  '高风险': 'rgba(249,115,22,0.15)',
  '极高风险': 'rgba(239,68,68,0.15)',
};

const RiskBadge: React.FC<RiskBadgeProps> = ({ level, size = 'md' }) => {
  const sizeClasses = {
    sm: 'px-2 py-0.5 text-xs',
    md: 'px-3 py-1 text-sm',
    lg: 'px-4 py-1.5 text-base font-semibold',
  };

  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full ${sizeClasses[size]}`}
      style={{
        color: colorMap[level] || '#6b7280',
        backgroundColor: bgMap[level] || 'rgba(107,114,128,0.15)',
        border: `1px solid ${colorMap[level] || '#6b7280'}40`,
      }}
    >
      <span
        className="w-2 h-2 rounded-full animate-pulse"
        style={{ backgroundColor: colorMap[level] || '#6b7280' }}
      />
      {level}
    </span>
  );
};

export default RiskBadge;
