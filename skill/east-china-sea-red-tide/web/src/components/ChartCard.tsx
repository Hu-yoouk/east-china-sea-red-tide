import React from 'react';

interface ChartCardProps {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
  className?: string;
  action?: React.ReactNode;
}

const ChartCard: React.FC<ChartCardProps> = ({ title, subtitle, children, className = '', action }) => {
  return (
    <div className={`glass-card p-5 ocean-glow animate-fade-in ${className}`}>
      <div className="flex items-center justify-between mb-3">
        <div>
          <h3 className="text-base font-semibold text-cyan-300">{title}</h3>
          {subtitle && <p className="text-xs text-gray-500 mt-0.5">{subtitle}</p>}
        </div>
        {action && <div>{action}</div>}
      </div>
      <div className="w-full">{children}</div>
    </div>
  );
};

export default ChartCard;
