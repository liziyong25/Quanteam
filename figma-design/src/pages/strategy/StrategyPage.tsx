import React, { useEffect, useMemo, useRef, useState } from 'react';
import Plot from 'react-plotly.js';
import { Activity, ChevronDown, ChevronUp, Info } from 'lucide-react';

import { Button } from '@/app/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/app/components/ui/card';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/app/components/ui/dialog';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/app/components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/app/components/ui/tabs';
import { strategyApi, StrategySummary, TableResponse, TimeSeriesResponse } from '@/lib/api/strategy';
import { CHART_TITLE_MAP } from '@/lib/constants/strategy';
import { cn } from '@/lib/utils';

type ChartStatus = 'idle' | 'loading' | 'success' | 'error';
type ChartState = {
  status: ChartStatus;
  data?: TimeSeriesResponse;
  error?: string;
};

type CellValue = string | number | boolean | null;
type SortState = {
  column: string | null;
  direction: 'asc' | 'desc' | null;
};

function optimizePlotlyTraces(traces: any[]): any[] {
  return traces.map((t) => {
    if (!t) return t;
    const xLen = Array.isArray(t.x) ? t.x.length : 0;
    const yLen = Array.isArray(t.y) ? t.y.length : 0;
    const len = Math.max(xLen, yLen);
    if ((t.type === 'scatter' || t.type === 'scattergl' || !t.type) && len >= 6000) {
      return { ...t, type: 'scattergl' };
    }
    return t;
  });
}

function nextSortState(current: SortState | undefined, column: string): SortState {
  if (!current || current.column !== column) {
    return { column, direction: 'asc' };
  }
  if (current.direction === 'asc') {
    return { column, direction: 'desc' };
  }
  if (current.direction === 'desc') {
    return { column: null, direction: null };
  }
  return { column, direction: 'asc' };
}

function sortIndicator(direction: SortState['direction'] | null) {
  if (direction === 'asc') return '↑';
  if (direction === 'desc') return '↓';
  return '⇅';
}

function isPercentColumn(column: string) {
  const normalized = column.toLowerCase();
  if (normalized.includes('%')) return true;
  return normalized.includes('yield') || normalized.includes('return') || normalized.includes('pct');
}

function formatCell(value: CellValue, column: string) {
  if (value === null || value === undefined) return '-';
  if (typeof value === 'number') {
    if (isPercentColumn(column)) {
      return value.toFixed(2);
    }
    return value.toFixed(4);
  }
  if (typeof value === 'boolean') {
    return value ? 'true' : 'false';
  }
  if (typeof value === 'string') {
    return formatDateOnly(value);
  }
  return String(value);
}

function formatDateOnly(value: string) {
  const match = value.match(/^\d{4}-\d{2}-\d{2}/);
  return match ? match[0] : value;
}

function toZhLabel(key: string) {
  const map: Record<string, string> = {
    Start: '开始日期',
    End: '结束日期',
    Period: '期间天数',
    'Start Value': '起始净值',
    'End Value': '结束净值',
    'Coupon Income': '票息收入',
    'Total Return [%]': '总收益率(%)',
    'Benchmark Return [%]': '基准收益率(%)',
    'Max Gross Exposure [%]': '最大杠杆(%)',
    'Total Fees Paid': '总费用',
    'Leverage Fees Paid': '杠杆费用',
    'Debt Fees Paid': '借贷费用',
    'Max Drawdown [%]': '最大回撤(%)',
    'Total Trades': '交易总数',
    'Total Closed Trades': '已平仓数',
    'Total Open Trades': '未平仓数',
    'Open Trade PnL': '未平仓盈亏',
    'Win Rate [%]': '胜率(%)',
    'Best Trade [%]': '最佳交易(%)',
    'Worst Trade [%]': '最差交易(%)',
    'Avg Winning Trade [%]': '平均盈利(%)',
    'Avg Losing Trade [%]': '平均亏损(%)',
    'Max Drawdown Duration': '最大回撤持续时间',
    'Avg Winning Trade Duration': '盈利交易持仓时间',
    'Avg Losing Trade Duration': '亏损交易持仓时间',
    'Profit Factor': '盈亏比',
    'Expectancy': '期望值',
  };
  return map[key] ?? key;
}

function formatMetric(key: string, value: StrategySummary['metrics'][string]) {
  if (value === null || value === undefined) return '-';
  if (typeof value === 'string') {
    return formatDateOnly(value);
  }
  if (typeof value === 'number') {
    if (key.includes('%')) {
      return value.toFixed(2);
    }
    return value.toFixed(4);
  }
  return String(value);
}

function buildGroupedRowClass(table: ReturnType<typeof prepareTable> | null, groupColumn: string) {
  if (!table) return null;
  const index = table.columns.indexOf(groupColumn);
  if (index < 0) return null;
  const colors = [
    'bg-[var(--daily-inc-row-1)]',
    'bg-[var(--daily-inc-row-2)]',
    'bg-[var(--daily-inc-row-3)]',
    'bg-[var(--daily-inc-row-4)]',
    'bg-[var(--daily-inc-row-5)]',
    'bg-[var(--daily-inc-row-6)]',
  ];
  const mapping: Record<string, string> = {};
  let colorIndex = 0;
  table.rows.forEach((row) => {
    const key = String(row[index] ?? '');
    if (!mapping[key]) {
      mapping[key] = colors[colorIndex % colors.length];
      colorIndex += 1;
    }
  });
  return (row: CellValue[]) => cn(mapping[String(row[index] ?? '')] ?? '', 'hover:bg-accent/20');
}

function toZhColumn(column: string) {
  const map: Record<string, string> = {
    Symbol: '标的',
    Size: '数量',
    'Entry Timestamp': '开仓日期',
    'Exit Timestamp': '平仓日期',
    'Avg Entry Price': '平均开仓价',
    'Avg Entry Yield': '平均开仓收益率',
    'Entry Fees': '开仓费用',
    'Entry Logs': '开仓日志',
    'Avg Exit Price': '平均平仓价',
    'Avg Exit Yield': '平均平仓收益率',
    'Exit Fees': '平仓费用',
    'Exit Logs': '平仓日志',
    PnL: '盈亏',
    'Yield PnL': '收益率盈亏(BP)',
    'CouPon Income': '票息收入',
    Return: '收益率',
    Direction: '方向',
    Status: '状态',
    Timestamp: '时间',
    Price: '价格',
    close_yield: '收益率',
    'Total Fees': '总费用',
    Fees: '费用',
    'Interest Fees': '利息费用',
    'Leverage Fees': '杠杆费用',
    coupon_income: '票息收入',
    Side: '方向',
    logs: '日志',
  };
  return map[column] ?? column;
}

function prepareTable(table: TableResponse | null, exclude: string[]) {
  if (!table) return null;
  const keepIndexes = table.columns
    .map((col, idx) => (exclude.includes(col) ? -1 : idx))
    .filter((idx) => idx >= 0);
  const columns = keepIndexes.map((idx) => table.columns[idx]);
  const rows = table.rows.map((row) => keepIndexes.map((idx) => (row[idx] ?? null) as CellValue));
  return {
    columns,
    labels: columns.map(toZhColumn),
    rows,
    filters: table.filters ?? null,
  };
}

const FILTER_COLUMNS = ['Symbol', 'Direction', 'Status'];
const PAGE_SIZE = 10;
const PLOT_MODAL_SIZE_KEY = 'strategy:signalPlotModalSize:v1';

type DataTableProps = {
  columns: string[];
  labels: string[];
  rows: CellValue[][];
  filterOptions?: Record<string, string[]> | null;
  filters: Record<string, string>;
  onFiltersChange: (next: Record<string, string>) => void;
  sort: SortState;
  onSortChange: (next: SortState) => void;
  rowClassName?: (row: CellValue[], rowIndex: number) => string;
  onRowClick?: (row: CellValue[], rowIndex: number) => void;
  className?: string;
};

function DataTable({
  columns,
  labels,
  rows,
  filterOptions,
  filters,
  onFiltersChange,
  sort,
  onSortChange,
  rowClassName,
  onRowClick,
  className,
}: DataTableProps) {
  const labelList = labels.length === columns.length ? labels : columns;
  const activeFilters = filters ?? {};

  return (
    <div className={cn('relative w-full', className)}>
      <table className="w-full table-fixed border-collapse text-[11px]">
        <thead className="sticky top-0 z-10 bg-card/90 text-xs text-muted-foreground backdrop-blur">
          <tr>
            {columns.map((column, index) => {
              const label = labelList[index] ?? column;
              const isFilterable = FILTER_COLUMNS.includes(column);
              const isSorted = sort?.column === column ? sort.direction : null;
              const options = filterOptions?.[column] ?? [];
              return (
                <th key={column} className="border border-border/50 px-2 py-2 text-left align-top">
                  <div className="flex flex-col gap-1">
                    <span className="text-[11px] font-semibold text-foreground">{label}</span>
                    {isFilterable ? (
                      <select
                        className="w-full rounded-md border border-border bg-background/70 px-2 py-1 text-[11px] text-foreground"
                        value={activeFilters[column] ?? ''}
                        onChange={(event) => {
                          const value = event.target.value;
                          const next = { ...activeFilters };
                          if (value) {
                            next[column] = value;
                          } else {
                            delete next[column];
                          }
                          onFiltersChange(next);
                        }}
                      >
                        <option value="">全部</option>
                        {options.map((option) => (
                          <option key={option} value={option}>
                            {option}
                          </option>
                        ))}
                      </select>
                    ) : (
                      <button
                        type="button"
                        className="inline-flex items-center gap-1 rounded-md border border-border bg-background/70 px-2 py-1 text-[11px] text-muted-foreground hover:bg-accent/30"
                        onClick={() => {
                          onSortChange(nextSortState(sort, column));
                        }}
                      >
                        排序
                        <span>{sortIndicator(isSorted)}</span>
                      </button>
                    )}
                  </div>
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, rowIndex) => {
            return (
              <tr
                key={rowIndex}
                className={cn(rowClassName ? rowClassName(row, rowIndex) : 'hover:bg-muted/20', onRowClick ? 'cursor-pointer' : undefined)}
                onClick={() => onRowClick?.(row, rowIndex)}
              >
                {columns.map((column, colIndex) => (
                  <td key={`${rowIndex}-${column}`} className="border border-border/50 px-2 py-1 align-top text-foreground">
                    <span className="break-words">{formatCell(row[colIndex] ?? null, column)}</span>
                  </td>
                ))}
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

const chartTabs = [
  'yield',
  'drawdowns',
  'underwater',
  'position',
  'leverage_ratio',
  'dv01',
  'trades',
  'trades_pnl',
] as const;

export function StrategyPage() {
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const [strategies, setStrategies] = useState<string[]>([]);
  const [selectedStrategy, setSelectedStrategy] = useState<string>('');
  const [runs, setRuns] = useState<StrategySummary[]>([]);
  const [selectedRunId, setSelectedRunId] = useState<string>('');

  const [runData, setRunData] = useState<StrategySummary | null>(null);
  const [charts, setCharts] = useState<Record<string, ChartState>>({});
  const [activeChartTab, setActiveChartTab] = useState<(typeof chartTabs)[number]>('drawdowns');
  const [chartsVisible, setChartsVisible] = useState(true);

  const [trades, setTrades] = useState<TableResponse | null>(null);
  const [orders, setOrders] = useState<TableResponse | null>(null);
  const [tradesPage, setTradesPage] = useState(1);
  const [ordersPage, setOrdersPage] = useState(1);
  const [tradesSort, setTradesSort] = useState<SortState>({ column: null, direction: null });
  const [ordersSort, setOrdersSort] = useState<SortState>({ column: null, direction: null });
  const [tradesFilters, setTradesFilters] = useState<Record<string, string>>({});
  const [ordersFilters, setOrdersFilters] = useState<Record<string, string>>({});
  const [loadingTrades, setLoadingTrades] = useState(false);
  const [loadingOrders, setLoadingOrders] = useState(false);
  const [plotTsOpen, setPlotTsOpen] = useState(false);
  const [plotTsSymbol, setPlotTsSymbol] = useState<string>('');
  const [plotTsState, setPlotTsState] = useState<ChartState>({ status: 'idle' });
  const [plotModalSize, setPlotModalSize] = useState<{ w: number; h: number } | null>(null);
  const resizeRef = useRef<{ startX: number; startY: number; startW: number; startH: number } | null>(null);

  const selectedRun = useMemo(() => runs.find((r) => r.run_id === selectedRunId) ?? null, [runs, selectedRunId]);

  const selectedSummary = useMemo(() => runData ?? selectedRun, [runData, selectedRun]);
  const summaryEntries = useMemo(() => {
    if (!selectedSummary?.metrics) return [] as Array<[string, StrategySummary['metrics'][string]]>;
    return Object.entries(selectedSummary.metrics);
  }, [selectedSummary]);

  const fetchStrategies = async () => {
    setErrorMessage(null);
    try {
      const res = await strategyApi.getStrategies(false);
      const items = Array.isArray((res as any)?.items) ? res.items : null;
      if (!items) throw new Error('Invalid /strategies response: missing items[]');
      const strategyNames = Array.from(new Set(items.map((item) => item.strategy_name))).sort();
      setStrategies(strategyNames);
      if (!selectedStrategy && strategyNames.length > 0) {
        setSelectedStrategy(strategyNames[0]);
      }
    } catch (e: any) {
      const msg = e?.response?.data?.detail || e?.message || 'Unable to load strategies';
      setErrorMessage(msg);
    }
  };

  const fetchRuns = async (strategyName: string) => {
    setErrorMessage(null);
    try {
      const res = await strategyApi.getStrategyRuns(strategyName);
      const items = Array.isArray((res as any)?.items) ? res.items : null;
      if (!items) throw new Error('Invalid /strategies/{name}/runs response: missing items[]');
      const sorted = [...items].sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime());
      setRuns(sorted);
      if (sorted.length > 0) {
        setSelectedRunId(sorted[0].run_id);
      } else {
        setSelectedRunId('');
      }
    } catch (e: any) {
      const msg = e?.response?.data?.detail || e?.message || 'Unable to load strategy runs';
      setErrorMessage(msg);
    }
  };

  const fetchTradesTable = async (
    runId: string,
    page: number,
    sort: SortState,
    filters: Record<string, string>
  ) => {
    setLoadingTrades(true);
    try {
      const res = await strategyApi.getTrades(runId, {
        page,
        page_size: PAGE_SIZE,
        sort_by: sort.column || undefined,
        sort_dir: sort.direction || undefined,
        filter_symbol: filters.Symbol || undefined,
        filter_direction: filters.Direction || undefined,
        filter_status: filters.Status || undefined,
      });
      setTrades(res);
    } finally {
      setLoadingTrades(false);
    }
  };

  const fetchOrdersTable = async (
    runId: string,
    page: number,
    sort: SortState,
    filters: Record<string, string>
  ) => {
    setLoadingOrders(true);
    try {
      const res = await strategyApi.getOrders(runId, {
        page,
        page_size: PAGE_SIZE,
        sort_by: sort.column || undefined,
        sort_dir: sort.direction || undefined,
        filter_symbol: filters.Symbol || undefined,
      });
      setOrders(res);
    } finally {
      setLoadingOrders(false);
    }
  };

  const fetchChart = async (runId: string, chartId: string) => {
    setCharts((prev) => ({ ...prev, [chartId]: { status: 'loading' } }));
    try {
      const data = await strategyApi.getTimeSeries(runId, chartId, true);
      setCharts((prev) => ({ ...prev, [chartId]: { status: 'success', data } }));
    } catch (e: any) {
      const msg = e?.response?.data?.detail || e?.message || '图表加载失败';
      setCharts((prev) => ({ ...prev, [chartId]: { status: 'error', error: msg } }));
    }
  };

  const openPlotTs = async (symbol: string) => {
    if (!selectedRunId) return;
    const clean = String(symbol ?? '').trim();
    if (!clean) return;
    setPlotTsOpen(true);
    setPlotTsSymbol(clean);
    setPlotTsState({ status: 'loading' });
    try {
      // v2: use indicator.plots(column=symbol) server-side, return Plotly JSON directly
      const data = await strategyApi.signalPlot(selectedRunId, clean);
      setPlotTsState({ status: 'success', data });
    } catch (e: any) {
      const msg = e?.response?.data?.detail || e?.message || '图表加载失败';
      setPlotTsState({ status: 'error', error: msg });
    }
  };

  useEffect(() => {
    if (!plotTsOpen) return;
    try {
      const raw = localStorage.getItem(PLOT_MODAL_SIZE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw);
        const w = Number(parsed?.w);
        const h = Number(parsed?.h);
        if (Number.isFinite(w) && Number.isFinite(h) && w > 320 && h > 240) {
          setPlotModalSize({ w, h });
          return;
        }
      }
    } catch {
      // ignore invalid cache
    }
    setPlotModalSize(null);
  }, [plotTsOpen]);

  useEffect(() => {
    if (!plotTsOpen) return;
    if (plotModalSize) return;
    const vw = Math.floor(window.innerWidth * 0.96);
    const vh = Math.floor(window.innerHeight * 0.92);
    let w = Math.min(vw, 1280);
    let h = Math.floor((w * 3) / 4);
    if (h > vh) {
      h = vh;
      w = Math.floor((h * 4) / 3);
    }
    setPlotModalSize({ w, h });
  }, [plotTsOpen, plotModalSize]);

  useEffect(() => {
    if (!plotTsOpen) return;
    const onMove = (e: PointerEvent) => {
      const snap = resizeRef.current;
      if (!snap) return;
      const dx = e.clientX - snap.startX;
      const vw = Math.floor(window.innerWidth * 0.96);
      const vh = Math.floor(window.innerHeight * 0.92);
      let nextW = Math.max(480, snap.startW + dx);
      let nextH = Math.floor((nextW * 3) / 4);
      if (nextW > vw) {
        nextW = vw;
        nextH = Math.floor((nextW * 3) / 4);
      }
      if (nextH > vh) {
        nextH = vh;
        nextW = Math.floor((nextH * 4) / 3);
      }
      setPlotModalSize({ w: nextW, h: nextH });
    };
    const onUp = () => {
      if (!resizeRef.current) return;
      resizeRef.current = null;
      if (plotModalSize) {
        try {
          localStorage.setItem(PLOT_MODAL_SIZE_KEY, JSON.stringify(plotModalSize));
        } catch {
          // ignore storage errors
        }
      }
    };
    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerup', onUp);
    return () => {
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerup', onUp);
    };
  }, [plotTsOpen, plotModalSize]);

  const fetchRunDetail = async (runId: string) => {
    setLoading(true);
    setErrorMessage(null);
    try {
      const [summaryRes] = await Promise.all([strategyApi.getRunSummary(runId)]);
      setRunData(summaryRes);
      setTradesPage(1);
      setOrdersPage(1);
      setTradesSort({ column: null, direction: null });
      setOrdersSort({ column: null, direction: null });
      setTradesFilters({});
      setOrdersFilters({});
      setTrades(null);
      setOrders(null);
      await fetchChart(runId, 'cumrets');
      await fetchChart(runId, activeChartTab);
    } catch (e: any) {
      const msg = e?.response?.data?.detail || e?.message || '加载失败';
      setErrorMessage(msg);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchStrategies();
  }, []);

  useEffect(() => {
    if (!selectedStrategy) return;
    fetchRuns(selectedStrategy);
  }, [selectedStrategy]);

  useEffect(() => {
    if (!selectedRunId) return;
    fetchRunDetail(selectedRunId);
  }, [selectedRunId]);

  useEffect(() => {
    if (!selectedRunId) return;
    fetchTradesTable(selectedRunId, tradesPage, tradesSort, tradesFilters).catch(() => undefined);
  }, [selectedRunId, tradesPage, tradesSort, tradesFilters]);

  useEffect(() => {
    if (!selectedRunId) return;
    fetchOrdersTable(selectedRunId, ordersPage, ordersSort, ordersFilters).catch(() => undefined);
  }, [selectedRunId, ordersPage, ordersSort, ordersFilters]);

  useEffect(() => {
    if (!selectedRunId) return;
    const state = charts[activeChartTab];
    if (state?.status === 'success') return;
    fetchChart(selectedRunId, activeChartTab);
  }, [activeChartTab]);

  const mainChart = charts['cumrets'];
  const activeChart = charts[activeChartTab];

  const canPrevTrades = (trades?.page ?? 1) > 1;
  const canNextTrades = trades ? trades.page * trades.page_size < trades.total : false;
  const canPrevOrders = (orders?.page ?? 1) > 1;
  const canNextOrders = orders ? orders.page * orders.page_size < orders.total : false;

  const preparedTrades = useMemo(() => prepareTable(trades, ['Exit Trade Id', 'Column', 'Position Id']), [trades]);
  const preparedOrders = useMemo(() => prepareTable(orders, ['Order Id', 'Column']), [orders]);
  const tradeSymbolColumnIndex = useMemo(() => {
    if (!preparedTrades) return -1;
    return preparedTrades.columns.findIndex((c) => c === 'Symbol' || c === 'symbol' || c === '标的');
  }, [preparedTrades]);
  const tradesRowClassName = useMemo(() => buildGroupedRowClass(preparedTrades, 'Symbol'), [preparedTrades]);
  const ordersRowClassName = useMemo(() => buildGroupedRowClass(preparedOrders, 'Symbol'), [preparedOrders]);
  const plotSymbolOptions = useMemo(() => {
    const raw = trades?.filters?.Symbol ?? [];
    const fallback =
      tradeSymbolColumnIndex >= 0 && preparedTrades
        ? preparedTrades.rows.map((row) => row[tradeSymbolColumnIndex]).filter((v) => typeof v === 'string')
        : [];
    const merged = [...raw, ...fallback].map((v) => String(v ?? '').trim()).filter(Boolean);
    const unique = Array.from(new Set(merged));
    unique.sort();
    return unique;
  }, [trades, preparedTrades, tradeSymbolColumnIndex]);

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 rounded-xl border bg-card/50 p-4 md:flex-row md:items-end md:justify-between">
        <div className="grid w-full grid-cols-1 gap-3 md:w-auto md:grid-cols-2">
          <div className="min-w-[220px]">
            <div className="mb-1 text-xs text-muted-foreground">选择策略</div>
            <Select value={selectedStrategy} onValueChange={setSelectedStrategy}>
              <SelectTrigger>
                <SelectValue placeholder="请选择策略" />
              </SelectTrigger>
              <SelectContent>
                {strategies.map((s) => (
                  <SelectItem key={s} value={s}>
                    {s}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="min-w-[260px]">
            <div className="mb-1 text-xs text-muted-foreground">运行实例</div>
            <Select value={selectedRunId} onValueChange={setSelectedRunId}>
              <SelectTrigger>
                <SelectValue placeholder="请选择运行实例" />
              </SelectTrigger>
              <SelectContent>
                {runs.map((r) => (
                  <SelectItem key={r.run_id} value={r.run_id}>
                    {r.run_name || r.run_id}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              if (!selectedRunId) return;
              setCharts({});
              fetchStrategies();
              if (selectedStrategy) {
                fetchRuns(selectedStrategy);
              }
              fetchRunDetail(selectedRunId);
            }}
          >
            <Activity className="mr-2 h-4 w-4" />
            刷新数据
          </Button>
        </div>
      </div>

      {errorMessage && (
        <Card className="border-destructive/30">
          <CardHeader className="pb-2">
            <CardTitle className="flex items-center gap-2 text-base text-destructive">
              <Info className="h-4 w-4" />
              加载失败
            </CardTitle>
          </CardHeader>
          <CardContent className="text-sm text-muted-foreground">{errorMessage}</CardContent>
        </Card>
      )}

      <section className="rounded-2xl border bg-card/50 p-5">
        <div className="flex flex-wrap items-center gap-4">
          <div className="text-lg font-semibold">
            {(selectedRun?.strategy_name && selectedRun?.run_name)
              ? `${selectedRun.strategy_name} / ${selectedRun.run_name}`
              : selectedRunId || '—'}
          </div>
          <div className="text-xs text-muted-foreground">
            更新时间：{selectedSummary?.updated_at ? formatDateOnly(selectedSummary.updated_at) : '--'}
          </div>
        </div>

        <div className="mt-4 grid grid-cols-2 gap-3 text-sm md:grid-cols-6 lg:grid-cols-8">
          {summaryEntries.map(([key, value]) => (
            <div key={key} className="rounded-xl border bg-background/40 px-3 py-2">
              <div className="text-[11px] text-muted-foreground">{toZhLabel(key)}</div>
              <div className="mt-1 text-sm font-semibold">{formatMetric(key, value)}</div>
            </div>
          ))}
        </div>
      </section>

      <Card>
        <CardHeader>
          <CardTitle>{CHART_TITLE_MAP['cumrets'] || '累计收益'}</CardTitle>
        </CardHeader>
        <CardContent className="h-[520px] p-2">
          {mainChart?.status === 'loading' && (
            <div className="flex h-full items-center justify-center text-muted-foreground">加载中…</div>
          )}
          {mainChart?.status === 'error' && (
            <div className="flex h-full flex-col items-center justify-center gap-2 text-muted-foreground">
              <div>{mainChart.error || '加载失败'}</div>
              <Button variant="outline" size="sm" onClick={() => selectedRunId && fetchChart(selectedRunId, 'cumrets')}>
                重试
              </Button>
            </div>
          )}
          {mainChart?.status === 'success' && mainChart.data?.plotly && (
            <Plot
              data={optimizePlotlyTraces(mainChart.data.plotly.data)}
              layout={{
                ...mainChart.data.plotly.layout,
                width: undefined,
                height: undefined,
                autosize: true,
                margin: { l: 50, r: 20, t: 30, b: 40 },
                paper_bgcolor: 'rgba(0,0,0,0)',
                plot_bgcolor: 'rgba(0,0,0,0)',
                font: { color: '#94a3b8' },
                xaxis: { ...mainChart.data.plotly.layout?.xaxis, gridcolor: '#334155', showgrid: true },
                yaxis: { ...mainChart.data.plotly.layout?.yaxis, gridcolor: '#334155', showgrid: true },
                showlegend: true,
                legend: { orientation: 'h', y: 1.05 },
              }}
              useResizeHandler
              style={{ width: '100%', height: '100%' }}
              config={{ displayModeBar: true, responsive: true }}
            />
          )}
          {!mainChart && <div className="flex h-full items-center justify-center text-muted-foreground">暂无数据</div>}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>详细记录</CardTitle>
        </CardHeader>
        <CardContent>
          <Tabs defaultValue="trades">
            <TabsList>
              <TabsTrigger value="trades">交易记录</TabsTrigger>
              <TabsTrigger value="orders">委托记录</TabsTrigger>
            </TabsList>

            <TabsContent value="trades">
              <div className="mt-3 rounded-md border">
                <div className="relative w-full overflow-auto max-h-[520px]">
                  {preparedTrades ? (
                    <DataTable
                      columns={preparedTrades.columns}
                      labels={preparedTrades.labels}
                      rows={preparedTrades.rows}
                      filterOptions={preparedTrades.filters}
                      filters={tradesFilters}
                      rowClassName={tradesRowClassName ?? undefined}
                      onFiltersChange={(next) => {
                        setTradesPage(1);
                        setTradesFilters(next);
                      }}
                      sort={tradesSort}
                      onSortChange={(next) => {
                        setTradesPage(1);
                        setTradesSort(next);
                      }}
                      onRowClick={(row) => {
                        if (tradeSymbolColumnIndex < 0) return;
                        const symbol = String(row[tradeSymbolColumnIndex] ?? '').trim();
                        if (!symbol) return;
                        openPlotTs(symbol);
                      }}
                    />
                  ) : (
                    <div className="flex h-[240px] items-center justify-center text-sm text-muted-foreground">
                      {loadingTrades ? '加载中…' : '暂无数据'}
                    </div>
                  )}
                </div>

                <div className="flex items-center justify-between gap-2 px-4 py-3">
                  <div className="text-xs text-muted-foreground">
                    第 {trades?.page ?? tradesPage} 页 / 共 {trades ? Math.max(1, Math.ceil(trades.total / trades.page_size)) : 1} 页
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={!selectedRunId || !canPrevTrades}
                      onClick={() => {
                        if (!selectedRunId) return;
                        const next = Math.max(1, tradesPage - 1);
                        setTradesPage(next);
                      }}
                    >
                      上一页
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={!selectedRunId || !canNextTrades}
                      onClick={() => {
                        if (!selectedRunId) return;
                        const next = tradesPage + 1;
                        setTradesPage(next);
                      }}
                    >
                      下一页
                    </Button>
                  </div>
                </div>
              </div>
            </TabsContent>

            <TabsContent value="orders">
              <div className="mt-3 rounded-md border">
                <div className="relative w-full overflow-auto max-h-[520px]">
                  {preparedOrders ? (
                    <DataTable
                      columns={preparedOrders.columns}
                      labels={preparedOrders.labels}
                      rows={preparedOrders.rows}
                      filterOptions={preparedOrders.filters}
                      filters={ordersFilters}
                      rowClassName={ordersRowClassName ?? undefined}
                      onFiltersChange={(next) => {
                        setOrdersPage(1);
                        setOrdersFilters(next);
                      }}
                      sort={ordersSort}
                      onSortChange={(next) => {
                        setOrdersPage(1);
                        setOrdersSort(next);
                      }}
                    />
                  ) : (
                    <div className="flex h-[240px] items-center justify-center text-sm text-muted-foreground">
                      {loadingOrders ? '加载中…' : '暂无数据'}
                    </div>
                  )}
                </div>

                <div className="flex items-center justify-between gap-2 px-4 py-3">
                  <div className="text-xs text-muted-foreground">
                    第 {orders?.page ?? ordersPage} 页 / 共 {orders ? Math.max(1, Math.ceil(orders.total / orders.page_size)) : 1} 页
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={!selectedRunId || !canPrevOrders}
                      onClick={() => {
                        if (!selectedRunId) return;
                        const next = Math.max(1, ordersPage - 1);
                        setOrdersPage(next);
                      }}
                    >
                      上一页
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={!selectedRunId || !canNextOrders}
                      onClick={() => {
                        if (!selectedRunId) return;
                        const next = ordersPage + 1;
                        setOrdersPage(next);
                      }}
                    >
                      下一页
                    </Button>
                  </div>
                </div>
              </div>
            </TabsContent>
          </Tabs>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
          <div className="flex flex-1 items-center gap-2 overflow-x-auto">
            {chartTabs.map((id) => (
              <Button
                key={id}
                variant={activeChartTab === id ? 'default' : 'ghost'}
                size="sm"
                className="whitespace-nowrap"
                onClick={() => {
                  setActiveChartTab(id);
                  setChartsVisible(true);
                }}
              >
                {CHART_TITLE_MAP[id] || id}
              </Button>
            ))}
          </div>

          <Button variant="ghost" size="sm" onClick={() => setChartsVisible((v) => !v)}>
            {chartsVisible ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
            <span className="ml-1 text-xs">{chartsVisible ? '收起' : '展开'}</span>
          </Button>
        </CardHeader>

        {chartsVisible && (
          <CardContent className="space-y-3">
            <div className="h-[420px] rounded-lg border bg-background/20 p-2">
              {activeChart?.status === 'loading' && (
                <div className="flex h-full items-center justify-center text-muted-foreground">加载中…</div>
              )}
              {activeChart?.status === 'error' && (
                <div className="flex h-full flex-col items-center justify-center gap-2 text-muted-foreground">
                  <div>{activeChart.error || '加载失败'}</div>
                  <Button variant="outline" size="sm" onClick={() => selectedRunId && fetchChart(selectedRunId, activeChartTab)}>
                    重试
                  </Button>
                </div>
              )}
              {activeChart?.status === 'success' && activeChart.data?.plotly && (
                <Plot
                  data={optimizePlotlyTraces(activeChart.data.plotly.data)}
                  layout={{
                    ...activeChart.data.plotly.layout,
                    width: undefined,
                    height: undefined,
                    autosize: true,
                    margin: { l: 50, r: 20, t: 30, b: 40 },
                    paper_bgcolor: 'rgba(0,0,0,0)',
                    plot_bgcolor: 'rgba(0,0,0,0)',
                    font: { color: '#94a3b8' },
                    xaxis: { ...activeChart.data.plotly.layout?.xaxis, gridcolor: '#334155', showgrid: true },
                    yaxis: { ...activeChart.data.plotly.layout?.yaxis, gridcolor: '#334155', showgrid: true },
                  }}
                  useResizeHandler
                  style={{ width: '100%', height: '100%' }}
                  config={{ displayModeBar: true, responsive: true }}
                />
              )}
              {!activeChart && <div className="flex h-full items-center justify-center text-muted-foreground">请选择图表</div>}
            </div>
          </CardContent>
        )}
      </Card>

      <Dialog
        open={plotTsOpen}
        onOpenChange={(open) => {
          setPlotTsOpen(open);
          if (!open) {
            setPlotTsState({ status: 'idle' });
            setPlotTsSymbol('');
          }
        }}
      >
        <DialogContent
          className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 p-0 flex flex-col overflow-hidden"
          style={
            plotModalSize
              ? {
                  width: plotModalSize.w,
                  height: plotModalSize.h,
                  maxWidth: '96vw',
                  maxHeight: '92vh',
                }
              : undefined
          }
        >
          <DialogHeader className="px-6 pt-6">
            <DialogTitle>{plotTsSymbol ? `交易信号 - ${plotTsSymbol}` : '交易信号'}</DialogTitle>
          </DialogHeader>
          <div className="flex-1 min-h-0 px-6 pb-6 overflow-auto">
            <div className="mt-2 flex items-center justify-between gap-3">
              <div className="text-xs text-muted-foreground">选择标的后刷新图表</div>
              <div className="w-[260px]">
                <Select
                  value={plotTsSymbol || ''}
                  onValueChange={(next) => {
                    if (!next) return;
                    openPlotTs(next);
                  }}
                >
                  <SelectTrigger>
                    <SelectValue placeholder="请选择标的" />
                  </SelectTrigger>
                  <SelectContent>
                    {plotSymbolOptions.map((s) => (
                      <SelectItem key={s} value={s}>
                        {s}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="mt-4 flex h-full min-h-[320px] flex-col">
              <div className="flex-1 min-h-0 rounded-lg border bg-background/20">
                {plotTsState.status === 'loading' && (
                  <div className="flex h-full items-center justify-center text-muted-foreground">加载中…</div>
                )}
                {plotTsState.status === 'error' && (
                  <div className="flex h-full flex-col items-center justify-center gap-2 text-muted-foreground">
                    <div>{plotTsState.error || '加载失败'}</div>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        if (!plotTsSymbol) return;
                        openPlotTs(plotTsSymbol);
                      }}
                    >
                      重试
                    </Button>
                  </div>
                )}
                {plotTsState.status === 'success' && plotTsState.data?.plotly && (
                  <Plot
                    data={optimizePlotlyTraces(plotTsState.data.plotly.data)}
                    layout={{
                      ...plotTsState.data.plotly.layout,
                      width: undefined,
                      height: undefined,
                      autosize: true,
                      margin: { l: 50, r: 20, t: 30, b: 40 },
                      paper_bgcolor: 'rgba(0,0,0,0)',
                      plot_bgcolor: 'rgba(0,0,0,0)',
                      font: { color: '#94a3b8' },
                      xaxis: { ...plotTsState.data.plotly.layout?.xaxis, gridcolor: '#334155', showgrid: true },
                      yaxis: { ...plotTsState.data.plotly.layout?.yaxis, gridcolor: '#334155', showgrid: true },
                    }}
                    useResizeHandler
                    style={{ width: '100%', height: '100%' }}
                    config={{ displayModeBar: true, responsive: true }}
                  />
                )}
                {plotTsState.status === 'success' && !plotTsState.data?.plotly && (
                  <div className="flex h-full items-center justify-center text-muted-foreground">暂无图表数据</div>
                )}
                {plotTsState.status === 'idle' && (
                  <div className="flex h-full items-center justify-center text-muted-foreground">请选择交易记录行</div>
                )}
              </div>
            </div>
          </div>

          <div
            className="absolute bottom-2 right-2 size-4 cursor-se-resize rounded-sm border border-border bg-background/70"
            onPointerDown={(e) => {
              if (!plotModalSize) return;
              e.preventDefault();
              resizeRef.current = {
                startX: e.clientX,
                startY: e.clientY,
                startW: plotModalSize.w,
                startH: plotModalSize.h,
              };
            }}
          />
        </DialogContent>
      </Dialog>
    </div>
  );
}
