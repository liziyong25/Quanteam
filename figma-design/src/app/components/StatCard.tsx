import React from 'react';
import { TrendingUp, TrendingDown, Minus } from 'lucide-react';

interface StatCardProps {
  title: string;
  value: string | number;
  change?: number;
  trend?: 'up' | 'down' | 'stable';
  unit?: string;
  color?: 'green' | 'red' | 'blue' | 'gray';
}

export function StatCard({ title, value, change, trend, unit = '', color = 'blue' }: StatCardProps) {
  const colorClasses = {
    green: 'bg-green-500/10 text-green-500',
    red: 'bg-red-500/10 text-red-500',
    blue: 'bg-blue-500/10 text-blue-500',
    gray: 'bg-gray-500/10 text-gray-500',
  };

  const getTrendIcon = () => {
    if (trend === 'up') return <TrendingUp className="w-4 h-4" />;
    if (trend === 'down') return <TrendingDown className="w-4 h-4" />;
    return <Minus className="w-4 h-4" />;
  };

  return (
    <div className="bg-card border border-border rounded-lg p-4">
      <div className="text-sm text-muted-foreground mb-2">{title}</div>
      <div className="flex items-end justify-between">
        <div className="flex items-baseline gap-2">
          <div className="text-2xl font-semibold text-foreground">
            {typeof value === 'number' ? value.toLocaleString('zh-CN', { maximumFractionDigits: 2 }) : value}
          </div>
          {unit && <div className="text-sm text-muted-foreground">{unit}</div>}
        </div>
        {change !== undefined && (
          <div className={`flex items-center gap-1 px-2 py-1 rounded ${colorClasses[color]}`}>
            {getTrendIcon()}
            <span className="text-sm font-medium">
              {change > 0 ? '+' : ''}{change.toFixed(2)}%
            </span>
          </div>
        )}
      </div>
    </div>
  );
}
