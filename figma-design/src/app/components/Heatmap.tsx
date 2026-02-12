import React from 'react';

interface HeatmapData {
  maturity: string;
  industry: string;
  value: number;
}

interface HeatmapProps {
  data: HeatmapData[];
  maturities: string[];
  industries: string[];
}

export function Heatmap({ data, maturities, industries }: HeatmapProps) {
  // 找出最大和最小值用于颜色映射
  const values = data.map(d => d.value);
  const maxValue = Math.max(...values);
  const minValue = Math.min(...values);
  const range = maxValue - minValue;

  // 根据值获取颜色
  const getColor = (value: number) => {
    if (range === 0) return 'rgba(59, 130, 246, 0.5)';
    
    const normalized = (value - minValue) / range;
    
    if (value > 0) {
      // 正值：绿色渐变
      const intensity = normalized * 255;
      return `rgba(16, 185, 129, ${0.2 + normalized * 0.6})`;
    } else if (value < 0) {
      // 负值：红色渐变
      const intensity = Math.abs(normalized) * 255;
      return `rgba(239, 68, 68, ${0.2 + Math.abs(normalized) * 0.6})`;
    } else {
      return 'rgba(107, 114, 128, 0.3)';
    }
  };

  // 根据maturity和industry找到对应的值
  const getValue = (maturity: string, industry: string) => {
    const item = data.find(d => d.maturity === maturity && d.industry === industry);
    return item?.value || 0;
  };

  return (
    <div className="overflow-x-auto">
      <div className="inline-block min-w-full">
        <div className="flex">
          {/* Y轴标签（行业） */}
          <div className="flex flex-col">
            <div className="h-10"></div> {/* 占位符，对齐X轴标签 */}
            {industries.map(industry => (
              <div
                key={industry}
                className="h-12 flex items-center justify-end pr-3 text-sm text-muted-foreground"
              >
                {industry}
              </div>
            ))}
          </div>

          {/* 热力图主体 */}
          <div className="flex-1">
            {/* X轴标签（期限） */}
            <div className="flex">
              {maturities.map(maturity => (
                <div
                  key={maturity}
                  className="flex-1 h-10 flex items-center justify-center text-sm text-muted-foreground"
                >
                  {maturity}
                </div>
              ))}
            </div>

            {/* 热力图单元格 */}
            {industries.map(industry => (
              <div key={industry} className="flex">
                {maturities.map(maturity => {
                  const value = getValue(maturity, industry);
                  return (
                    <div
                      key={`${maturity}-${industry}`}
                      className="flex-1 h-12 border border-border/30 flex items-center justify-center group cursor-pointer hover:border-blue-500/50 transition-all relative"
                      style={{ backgroundColor: getColor(value) }}
                    >
                      <span className="text-xs font-medium text-foreground">
                        {value > 0 ? '+' : ''}{value.toFixed(0)}
                      </span>
                      
                      {/* Tooltip on hover */}
                      <div className="absolute bottom-full left-1/2 transform -translate-x-1/2 mb-2 px-3 py-2 bg-gray-900 text-white text-xs rounded shadow-lg opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none whitespace-nowrap z-10">
                        <div className="font-medium">{industry} - {maturity}</div>
                        <div className="text-gray-300">净买入: {value > 0 ? '+' : ''}{value.toFixed(2)} 亿元</div>
                      </div>
                    </div>
                  );
                })}
              </div>
            ))}
          </div>
        </div>

        {/* 图例 */}
        <div className="flex items-center justify-center gap-6 mt-6 text-sm">
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded" style={{ backgroundColor: 'rgba(239, 68, 68, 0.8)' }}></div>
            <span className="text-muted-foreground">净卖出</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded" style={{ backgroundColor: 'rgba(107, 114, 128, 0.3)' }}></div>
            <span className="text-muted-foreground">持平</span>
          </div>
          <div className="flex items-center gap-2">
            <div className="w-6 h-6 rounded" style={{ backgroundColor: 'rgba(16, 185, 129, 0.8)' }}></div>
            <span className="text-muted-foreground">净买入</span>
          </div>
        </div>
      </div>
    </div>
  );
}
