import React from 'react';
import { LucideIcon } from 'lucide-react';

interface ModuleCardProps {
  title: string;
  description: string;
  icon: LucideIcon;
  stats?: {
    label: string;
    value: string;
  }[];
  status?: 'active' | 'planned' | 'existing';
  onClick?: () => void;
}

export function ModuleCard({ title, description, icon: Icon, stats, status = 'active', onClick }: ModuleCardProps) {
  const statusConfig = {
    active: {
      badge: '新功能',
      badgeColor: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
      clickable: true,
    },
    planned: {
      badge: '规划中',
      badgeColor: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
      clickable: false,
    },
    existing: {
      badge: '已有模块',
      badgeColor: 'bg-green-500/20 text-green-400 border-green-500/30',
      clickable: true,
    },
  };

  const config = statusConfig[status];
  const isClickable = config.clickable && onClick;

  return (
    <div
      onClick={isClickable ? onClick : undefined}
      className={`
        bg-card border border-border rounded-lg p-6 
        transition-all duration-200
        ${isClickable ? 'cursor-pointer hover:border-blue-500/50 hover:shadow-lg hover:shadow-blue-500/10' : 'cursor-default opacity-75'}
      `}
    >
      <div className="flex items-start justify-between mb-4">
        <div className="flex items-center gap-3">
          <div className="p-3 bg-blue-500/10 rounded-lg">
            <Icon className="w-6 h-6 text-blue-400" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-foreground mb-1">{title}</h3>
            <p className="text-sm text-muted-foreground">{description}</p>
          </div>
        </div>
        <span className={`px-3 py-1 text-xs font-medium rounded-full border ${config.badgeColor}`}>
          {config.badge}
        </span>
      </div>

      {stats && stats.length > 0 && (
        <div className="grid grid-cols-2 gap-4 mt-4 pt-4 border-t border-border">
          {stats.map((stat, index) => (
            <div key={index}>
              <div className="text-xs text-muted-foreground mb-1">{stat.label}</div>
              <div className="text-base font-semibold text-foreground">{stat.value}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
