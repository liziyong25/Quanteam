export const STRATEGY_KPI_MAP: Record<string, string> = {
  // 核心指标
  'start': '开始日期',
  'end': '结束日期',
  'period': '期间天数',
  'start_value': '起始净值',
  'end_value': '结束净值',
  'total_return_pct': '总收益率',
  'benchmark_return_pct': '基准收益率',
  'max_drawdown_pct': '最大回撤',
  'win_rate_pct': '胜率',
  'total_trades': '交易总数',
  'total_closed_trades': '已平仓数',
  'total_open_trades': '未平仓数',
  
  // 补充指标 (可能存在于 metrics 中)
  'Sharpe Ratio': '夏普比率',
  'Sortino Ratio': '索提诺比率',
  'Calmar Ratio': '卡玛比率',
  'Max Drawdown': '最大回撤',
  'Total Return': '总收益率',
  'Win Rate': '胜率',
  'Profit Factor': '盈亏比',
  'Avg Trade': '平均交易收益',
  'Best Trade': '最佳交易',
  'Worst Trade': '最差交易',
  'Avg Win': '平均盈利',
  'Avg Loss': '平均亏损',
  'Expectancy': '期望值',
  'SQN': 'SQN',
};

export const CHART_TITLE_MAP: Record<string, string> = {
  'cumrets': '累计收益',
  'yield': '累计收益(BP)',
  'drawdowns': '回撤',
  'underwater': '水下回撤',
  'position': '仓位',
  'leverage_ratio': '杠杆比例',
  'dv01': 'DV01',
  'trades': '成交次数',
  'trades_pnl': '成交盈亏',
  'signal': '交易信号',
};

export const TABLE_COLUMN_MAP: Record<string, string> = {
  'Entry Timestamp': '开仓时间',
  'Exit Timestamp': '平仓时间',
  'Symbol': '标的',
  'Direction': '方向',
  'Size': '数量',
  'Entry Price': '开仓价',
  'Exit Price': '平仓价',
  'PnL': '盈亏',
  'Return': '收益率',
  'Status': '状态',
  'Timestamp': '时间',
  'Price': '价格',
  'Type': '类型',
  'Tag': '标签',
  'Commission': '佣金',
  'Slippage': '滑点',
};

export const DIRECTION_MAP: Record<string, string> = {
  'Long': '做多',
  'Short': '做空',
  'LONG': '做多',
  'SHORT': '做空',
};
