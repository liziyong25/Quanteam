import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Plot from 'react-plotly.js';
import { ChevronDown, ChevronRight, RefreshCw } from 'lucide-react';

import { Button } from '@/app/components/ui/button';
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from '@/app/components/ui/card';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/app/components/ui/dialog';
import { Input } from '@/app/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/app/components/ui/select';
import {
  cfetsApi,
  type CfetsDrilldownResponse,
  type CfetsPivotResponse,
  type CfetsPivotRow,
  type Indicator,
  type IndustryMode,
} from '@/lib/api/cfets';
import { cn } from '@/lib/utils';

interface InstitutionalFlowDashboardProps {
  onBack: () => void;
}

type PivotSelection = {
  symbol: string;
  industry: string;
};

type PlotlyFigure = {
  data: Array<Record<string, unknown>>;
  layout: Record<string, unknown>;
};

type PivotDisplayRow = {
  symbol: string;
  row: CfetsPivotRow;
  isSummary: boolean;
  hasDetails: boolean;
};

type SortState = { column: string | null; direction: 'asc' | 'desc' | null };

type IndustryColumn = {
  key: string;
  label: string;
};

const AGE_TOTAL = '合计';
const PANEL_SIZE_KEY = 'cfets:panelModalSize:v1';
const PIVOT_CACHE_PREFIX = 'cfets:pivot:v1';

const INDICATORS: Array<{ key: Indicator; label: string }> = [
  { key: 'netbuy_amount', label: '净买入' },
  { key: 'buy_amount', label: '买入' },
  { key: 'sell_amount', label: '卖出' },
];

const SYMBOL_ORDER = [
  '国债-新债',
  '国债-老债',
  '政策性金融债-新债',
  '政策性金融债-老债',
  '地方政府债',
  '中期票据',
  '企业债',
  '同业存单',
  '短期融资券',
  '资产支持证券',
  '其他',
  '合计',
];

const INDUSTRY_ORDER_NEW = [
  '大型银行',
  '中小型银行',
  '保险公司',
  '基金公司及产品',
  '证券公司',
  '理财类产品',
  '货币市场基金',
  '其他',
];

const INDUSTRY_ORDER_OLD = [
  '大行及政策行',
  '股份制商业银行',
  '城市商业银行',
  '农村金融机构',
  '外资银行',
  '保险公司',
  '基金公司及产品',
  '证券公司',
  '理财类产品',
  '货币市场基金',
  '其他产品类',
  '其他',
];

const INDUSTRY_MODES: Array<{ key: IndustryMode; label: string }> = [
  { key: 'new', label: '新口径' },
  { key: 'old', label: '老口径' },
];

const ROW_COLORS = [
  'bg-[var(--daily-inc-row-1)]',
  'bg-[var(--daily-inc-row-2)]',
  'bg-[var(--daily-inc-row-3)]',
  'bg-[var(--daily-inc-row-4)]',
  'bg-[var(--daily-inc-row-5)]',
  'bg-[var(--daily-inc-row-6)]',
];

function normalizeKey(value: string) {
  return value.replace(/\s+/g, '').trim();
}

function nextSortState(current: SortState | undefined, column: string): SortState {
  if (!current || current.column !== column) return { column, direction: 'asc' };
  if (current.direction === 'asc') return { column, direction: 'desc' };
  if (current.direction === 'desc') return { column: null, direction: null };
  return { column, direction: 'asc' };
}

function sortIndicator(direction: SortState['direction'] | null) {
  if (direction === 'asc') return '^';
  if (direction === 'desc') return 'v';
  return '-';
}

function today() {
  const d = new Date();
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  const dd = String(d.getDate()).padStart(2, '0');
  return `${yyyy}-${mm}-${dd}`;
}

function buildPivotCacheKey(query: {
  tradeDate: string;
  indicator?: Indicator;
  start?: string;
  end?: string;
  industryMode?: IndustryMode;
}) {
  const parts = [
    PIVOT_CACHE_PREFIX,
    query.tradeDate,
    query.start ?? '',
    query.end ?? '',
    query.indicator ?? '',
    query.industryMode ?? '',
  ];
  return parts.join('|');
}

function formatPivotValue(value: unknown) {
  if (value === null || value === undefined) return { text: '-', isNumeric: false };
  if (typeof value === 'boolean') return { text: value ? 'true' : 'false', isNumeric: false };
  if (typeof value === 'number') {
    if (!Number.isFinite(value)) return { text: '-', isNumeric: false };
    return { text: String(Math.round(value)), isNumeric: true };
  }
  const num = Number(value);
  if (Number.isFinite(num)) {
    return { text: String(Math.round(num)), isNumeric: true };
  }
  const text = String(value).trim();
  if (!text) return { text: '-', isNumeric: false };
  return { text, isNumeric: false };
}

function toNumber(value: unknown) {
  if (value === null || value === undefined) return null;
  const num = Number(value);
  if (!Number.isFinite(num)) return null;
  return num;
}

function buildPanelFigure(data: CfetsDrilldownResponse, age: string, indicatorLabel: string): PlotlyFigure {
  return {
    data: [
      {
        type: 'scatter',
        mode: 'lines',
        name: indicatorLabel,
        x: data.dates,
        y: data.series[age] ?? [],
      },
      {
        type: 'scatter',
        mode: 'lines',
        name: '估值',
        x: data.dates,
        y: data.valuation,
        yaxis: 'y2',
        line: { width: 2 },
      },
    ],
    layout: {
      paper_bgcolor: 'rgba(0,0,0,0)',
      plot_bgcolor: 'rgba(0,0,0,0)',
      font: { color: 'var(--muted-foreground)' },
      xaxis: { gridcolor: 'var(--border)', showgrid: true },
      yaxis: { gridcolor: 'var(--border)', showgrid: true },
      yaxis2: { overlaying: 'y', side: 'right', showgrid: false },
      showlegend: false,
      margin: { l: 40, r: 30, t: 10, b: 30 },
    },
  };
}

export function InstitutionalFlowDashboard({ onBack }: InstitutionalFlowDashboardProps) {
  const [start, setStart] = useState('2024-01-01');
  const [end, setEnd] = useState('');
  const [tradeDate, setTradeDate] = useState('');
  const [indicator, setIndicator] = useState<Indicator>('netbuy_amount');
  const [industryMode, setIndustryMode] = useState<IndustryMode>('new');

  const [metaLoading, setMetaLoading] = useState(false);
  const [metaError, setMetaError] = useState<string | null>(null);

  const [pivot, setPivot] = useState<CfetsPivotResponse | null>(null);
  const [pivotLoading, setPivotLoading] = useState(false);
  const [pivotError, setPivotError] = useState<string | null>(null);

  const [expandedSymbols, setExpandedSymbols] = useState<Set<string>>(new Set());
  const [selection, setSelection] = useState<PivotSelection | null>(null);
  const [sort, setSort] = useState<SortState>({ column: null, direction: null });

  const [modalOpen, setModalOpen] = useState(false);
  const [panelSize, setPanelSize] = useState<{ w: number; h: number } | null>(null);
  const resizeRef = useRef<{ startX: number; startY: number; startW: number; startH: number } | null>(null);

  const [drilldown, setDrilldown] = useState<CfetsDrilldownResponse | null>(null);
  const [drilldownLoading, setDrilldownLoading] = useState(false);
  const [drilldownError, setDrilldownError] = useState<string | null>(null);

  const indicatorLabel = useMemo(() => {
    const found = INDICATORS.find((item) => item.key === indicator);
    return found ? found.label : indicator;
  }, [indicator]);

  const dateRangeLabel = useMemo(() => {
    if (start && end) return `${start} ~ ${end}`;
    if (start) return `${start} ~`;
    if (end) return `~ ${end}`;
    return '';
  }, [start, end]);

  const industryColumns = useMemo<IndustryColumn[]>(() => {
    if (!pivot) return [];
    const normalizedMap = new Map<string, string>();
    pivot.industries.forEach((name) => {
      normalizedMap.set(normalizeKey(name), name);
    });
    const order = industryMode === 'new' ? INDUSTRY_ORDER_NEW : INDUSTRY_ORDER_OLD;
    return order.map((label) => {
      const key = normalizedMap.get(normalizeKey(label)) ?? label;
      return { key, label };
    });
  }, [pivot, industryMode]);

  const pivotQuery = useMemo(
    () => ({ tradeDate, indicator, start, end, industryMode }),
    [tradeDate, indicator, start, end, industryMode]
  );
  const pivotCacheKey = useMemo(() => buildPivotCacheKey(pivotQuery), [pivotQuery]);

  const drilldownQuery = useMemo(() => {
    if (!selection) return null;
    return { industry: selection.industry, symbol: selection.symbol, indicator, start, end, industryMode };
  }, [selection, indicator, start, end, industryMode]);

  const requestPivot = useCallback(async () => {
    if (!start || !end || !tradeDate) {
      setPivotError('请先加载最新交易日');
      return;
    }
    setPivotLoading(true);
    setPivotError(null);
    try {
      const data = await cfetsApi.getPivot(pivotQuery);
      setPivot(data);
      setExpandedSymbols(new Set());
      setSort({ column: null, direction: null });
      try {
        localStorage.setItem(
          pivotCacheKey,
          JSON.stringify({ cachedAt: new Date().toISOString(), data })
        );
      } catch {
        // ignore cache write errors
      }
    } catch (error: any) {
      setPivotError(error?.message || '加载 Pivot 失败');
    } finally {
      setPivotLoading(false);
    }
  }, [pivotQuery, pivotCacheKey]);

  const requestDrilldown = useCallback(async () => {
    if (!drilldownQuery) return;
    setDrilldownLoading(true);
    setDrilldownError(null);
    try {
      const data = await cfetsApi.getDrilldown(drilldownQuery);
      setDrilldown(data);
    } catch (error: any) {
      setDrilldownError(error?.message || '加载面板失败');
    } finally {
      setDrilldownLoading(false);
    }
  }, [drilldownQuery]);

  useEffect(() => {
    let active = true;
    const loadMeta = async () => {
      setMetaLoading(true);
      setMetaError(null);
      try {
        const data = await cfetsApi.getMeta();
        const latest = data?.latest_trade_date;
        if (active && latest) {
          setEnd(latest);
          setTradeDate(latest);
        }
      } catch (error: any) {
        if (!active) return;
        setMetaError(error?.message || '加载最新交易日失败');
        const fallback = today();
        setEnd((current) => current || fallback);
        setTradeDate((current) => current || fallback);
      } finally {
        if (active) {
          setMetaLoading(false);
        }
      }
    };

    loadMeta();
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    if (!tradeDate || !end) return;
    try {
      const raw = localStorage.getItem(pivotCacheKey);
      if (!raw) return;
      const cached = JSON.parse(raw);
      if (cached?.data?.rows && cached?.data?.industries) {
        setPivot(cached.data);
      }
    } catch {
      // ignore cache read errors
    }
  }, [pivotCacheKey]);

  useEffect(() => {
    if (!tradeDate || !end) return;
    requestPivot();
  }, [requestPivot, tradeDate, end]);

  useEffect(() => {
    setExpandedSymbols(new Set());
    setSort({ column: null, direction: null });
    setSelection(null);
    setModalOpen(false);
    setDrilldown(null);
    setDrilldownError(null);
  }, [industryMode]);

  useEffect(() => {
    if (!modalOpen) return;
    requestDrilldown();
  }, [modalOpen, requestDrilldown]);

  useEffect(() => {
    if (!modalOpen) return;
    setDrilldownError(null);
    setDrilldown(null);
  }, [selection?.symbol, selection?.industry, modalOpen]);

  useEffect(() => {
    if (!modalOpen) return;
    setDrilldown(null);
    setDrilldownError(null);
    try {
      const raw = localStorage.getItem(PANEL_SIZE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw);
        const w = Number(parsed?.w);
        const h = Number(parsed?.h);
        if (Number.isFinite(w) && Number.isFinite(h) && w > 300 && h > 200) {
          setPanelSize({ w, h });
        } else {
          setPanelSize(null);
        }
      } else {
        setPanelSize(null);
      }
    } catch {
      setPanelSize(null);
    }
  }, [modalOpen, selection?.symbol]);

  useEffect(() => {
    if (!modalOpen) return;
    if (panelSize) return;
    const vw = Math.floor(window.innerWidth * 0.96);
    const vh = Math.floor(window.innerHeight * 0.92);
    const maxW = Math.min(vw, 1770);
    let w = maxW;
    let h = Math.floor((w * 9) / 16);
    if (h > vh) {
      h = vh;
      w = Math.floor((h * 16) / 9);
    }
    setPanelSize({ w, h });
  }, [modalOpen, panelSize]);

  useEffect(() => {
    if (!modalOpen) return;
    const onMove = (e: PointerEvent) => {
      const snap = resizeRef.current;
      if (!snap) return;
      const dx = e.clientX - snap.startX;
      const dy = e.clientY - snap.startY;
      const intent = Math.max(dx, dy);

      const vw = window.innerWidth * 0.96;
      const vh = window.innerHeight * 0.92;
      const minW = 640;
      const maxW = Math.min(vw, 2400);

      let nextW = snap.startW + intent;
      nextW = Math.max(minW, Math.min(maxW, nextW));
      let nextH = (nextW * 9) / 16;

      if (nextH > vh) {
        nextH = vh;
        nextW = (nextH * 16) / 9;
      }

      setPanelSize({ w: Math.round(nextW), h: Math.round(nextH) });
    };

    const onUp = () => {
      if (!resizeRef.current) return;
      resizeRef.current = null;
      setPanelSize((cur) => {
        if (cur) {
          try {
            localStorage.setItem(PANEL_SIZE_KEY, JSON.stringify(cur));
          } catch {
            return cur;
          }
        }
        return cur;
      });
    };

    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerup', onUp);
    return () => {
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerup', onUp);
    };
  }, [modalOpen]);

  const { displayRows, symbolColors } = useMemo(() => {
    if (!pivot) return { displayRows: [] as PivotDisplayRow[], symbolColors: {} as Record<string, string> };

    const baseOrder = SYMBOL_ORDER.filter((item) => item !== AGE_TOTAL);
    const orderMap = new Map(baseOrder.map((item, idx) => [item, idx]));

    const grouped = new Map<
      string,
      { symbol: string; summary: CfetsPivotRow | null; details: CfetsPivotRow[]; order: number }
    >();

    pivot.rows.forEach((row, index) => {
      const symbol = String(row.symbol ?? '').trim();
      if (!symbol) return;
      const age = String(row.new_age ?? '');
      let group = grouped.get(symbol);
      if (!group) {
        group = { symbol, summary: null, details: [], order: index };
        grouped.set(symbol, group);
      }
      if (age === AGE_TOTAL) {
        group.summary = row;
      } else {
        group.details.push(row);
      }
    });

    const ageIndex = new Map(pivot.age_order.map((age, idx) => [age, idx]));

    const sortedGroups = Array.from(grouped.values())
      .map((group, fallback) => ({
        ...group,
        fallback,
        sortKey: group.summary ?? group.details[0] ?? null,
      }))
      .sort((a, b) => {
        if (!sort.column || !sort.direction) {
          const aIndex = a.symbol === AGE_TOTAL
            ? baseOrder.length + 1
            : orderMap.get(a.symbol) ?? baseOrder.length + a.fallback / 100;
          const bIndex = b.symbol === AGE_TOTAL
            ? baseOrder.length + 1
            : orderMap.get(b.symbol) ?? baseOrder.length + b.fallback / 100;
          return aIndex - bIndex;
        }

        const aValRaw = a.sortKey ? a.sortKey[sort.column] : null;
        const bValRaw = b.sortKey ? b.sortKey[sort.column] : null;
        const aValNum = toNumber(aValRaw);
        const bValNum = toNumber(bValRaw);
        const dir = sort.direction === 'desc' ? -1 : 1;

        if (aValNum === null && bValNum === null) return 0;
        if (aValNum === null) return 1;
        if (bValNum === null) return -1;
        if (aValNum !== null && bValNum !== null) return (aValNum - bValNum) * dir;
        return String(aValRaw ?? '').localeCompare(String(bValRaw ?? ''), 'zh-CN') * dir;
      });

    const symbolColors: Record<string, string> = {};
    let colorIndex = 0;
    const assignColor = (symbol: string) => {
      if (symbolColors[symbol]) return;
      symbolColors[symbol] = ROW_COLORS[colorIndex % ROW_COLORS.length];
      colorIndex += 1;
    };

    baseOrder.forEach((symbol) => {
      if (grouped.has(symbol)) assignColor(symbol);
    });
    if (grouped.has(AGE_TOTAL)) assignColor(AGE_TOTAL);
    grouped.forEach((_, symbol) => assignColor(symbol));

    const displayRows: PivotDisplayRow[] = [];
    sortedGroups.forEach((group) => {
      const sortedDetails = group.details.slice().sort((left, right) => {
        const leftIndex = ageIndex.get(String(left.new_age ?? '')) ?? 9999;
        const rightIndex = ageIndex.get(String(right.new_age ?? '')) ?? 9999;
        return leftIndex - rightIndex;
      });

      let summary = group.summary;
      let details = sortedDetails;
      if (!summary && details.length > 0) {
        summary = details[0];
        details = details.slice(1);
      }
      if (!summary) return;

      const hasDetails = details.length > 0;
      displayRows.push({ symbol: group.symbol, row: summary, isSummary: true, hasDetails });
      if (expandedSymbols.has(group.symbol)) {
        details.forEach((detail) => {
          displayRows.push({ symbol: group.symbol, row: detail, isSummary: false, hasDetails: false });
        });
      }
    });

    return { displayRows, symbolColors };
  }, [pivot, expandedSymbols, sort]);

  const panelAges = useMemo(() => {
    if (!drilldown) return [] as string[];
    return drilldown.age_order.slice(0, 12);
  }, [drilldown]);

  return (
    <div className="flex w-full flex-col gap-6">
      <div className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold text-foreground">机构行为分析</h1>
          <p className="text-sm text-muted-foreground">CFETS Bond Amount</p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" onClick={onBack}>返回</Button>
        </div>
      </div>

      <Card>
        <CardHeader>
          <div>
            <CardTitle>筛选条件</CardTitle>
            <CardDescription>交易日与指标切换；展示范围按 start/end 控制。</CardDescription>
          </div>
          <CardAction className="flex items-center gap-2">
            <Button
              variant="outline"
              size="sm"
              onClick={requestPivot}
              disabled={pivotLoading || metaLoading || !end || !tradeDate}
            >
              <RefreshCw className="w-4 h-4" />
              刷新
            </Button>
          </CardAction>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap items-end gap-4">
            <div className="flex flex-col gap-1 text-xs text-muted-foreground">
              start
              <Input type="date" value={start} onChange={(e) => setStart(e.target.value)} className="min-w-[160px]" />
            </div>
            <div className="flex flex-col gap-1 text-xs text-muted-foreground">
              end
              <Input type="date" value={end} onChange={(e) => setEnd(e.target.value)} className="min-w-[160px]" />
            </div>
            <div className="flex flex-col gap-1 text-xs text-muted-foreground">
              trade_date
              <Input type="date" value={tradeDate} onChange={(e) => setTradeDate(e.target.value)} className="min-w-[160px]" />
            </div>
            <div className="flex flex-col gap-1 text-xs text-muted-foreground">
              口径
              <Select value={industryMode} onValueChange={(value) => setIndustryMode(value as IndustryMode)}>
                <SelectTrigger className="min-w-[160px]">
                  <SelectValue placeholder="选择口径" />
                </SelectTrigger>
                <SelectContent>
                  {INDUSTRY_MODES.map((mode) => (
                    <SelectItem key={mode.key} value={mode.key}>
                      {mode.label}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              {INDICATORS.map((item) => (
                <Button
                  key={item.key}
                  variant={indicator === item.key ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => setIndicator(item.key)}
                >
                  {item.label}
                </Button>
              ))}
            </div>
          </div>
          {metaLoading ? (
            <div className="mt-2 text-xs text-muted-foreground">加载最新交易日...</div>
          ) : null}
          {metaError ? (
            <div className="mt-2 text-xs text-destructive">{metaError}</div>
          ) : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <div>
            <CardTitle>Pivot Table（单日）</CardTitle>
            <CardDescription>{tradeDate} · {indicatorLabel}</CardDescription>
          </div>
          <CardAction className="flex items-center gap-3 text-xs text-muted-foreground">
            {pivot ? <span>rows: {pivot.rows.length}</span> : null}
          </CardAction>
        </CardHeader>
        <CardContent>
          {pivotLoading ? (
            <div className="flex h-[240px] items-center justify-center text-sm text-muted-foreground">加载 Pivot 中...</div>
          ) : pivotError ? (
            <div className="rounded-md border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">{pivotError}</div>
          ) : pivot ? (
            <div className="relative w-full overflow-auto max-h-[70vh] rounded-md border">
              <table className="w-full min-w-[980px] border-collapse text-[11px]">
                <thead className="sticky top-0 z-10 bg-card/90 text-xs text-muted-foreground backdrop-blur">
                  <tr>
                    <th className="border border-border/50 px-2 py-2 text-left align-top">
                      <div className="flex flex-col gap-1">
                        <span className="text-[11px] font-semibold text-foreground">symbol</span>
                      </div>
                    </th>
                    <th className="border border-border/50 px-2 py-2 text-left align-top">
                      <div className="flex flex-col gap-1">
                        <span className="text-[11px] font-semibold text-foreground">年限</span>
                      </div>
                    </th>
                    {industryColumns.map((column) => {
                      const isSorted = sort.column === column.key ? sort.direction : null;
                      return (
                        <th key={column.key} className="border border-border/50 px-2 py-2 text-left align-top">
                          <div className="flex flex-col gap-1">
                            <span className="text-[11px] font-semibold text-foreground">{column.label}</span>
                            <button
                              type="button"
                              className="inline-flex items-center gap-1 rounded-md border border-border bg-background/70 px-2 py-1 text-[11px] text-muted-foreground hover:bg-accent/30"
                              onClick={() => setSort(nextSortState(sort, column.key))}
                            >
                              排序
                              <span>{sortIndicator(isSorted)}</span>
                            </button>
                          </div>
                        </th>
                      );
                    })}
                  </tr>
                </thead>
                <tbody>
                  {displayRows.map((item, rowIndex) => {
                    const age = String(item.row.new_age ?? '');
                    const isExpanded = expandedSymbols.has(item.symbol);
                    const rowColor = symbolColors[item.symbol] ?? '';
                    return (
                      <tr
                        key={`${item.symbol}-${rowIndex}`}
                        className={cn(rowColor, 'hover:bg-accent/20 transition-colors')}
                      >
                        <td className="border border-border/50 px-2 py-1 align-top text-foreground">
                          <div className="flex items-center gap-2">
                            {item.isSummary ? (
                              <Button
                                variant="ghost"
                                size="icon"
                                className="h-7 w-7"
                                disabled={!item.hasDetails}
                                onClick={() => {
                                  if (!item.hasDetails) return;
                                  setExpandedSymbols((prev) => {
                                    const next = new Set(prev);
                                    if (next.has(item.symbol)) {
                                      next.delete(item.symbol);
                                    } else {
                                      next.add(item.symbol);
                                    }
                                    return next;
                                  });
                                }}
                              >
                                {isExpanded ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
                              </Button>
                            ) : (
                              <span className="h-7 w-7" />
                            )}
                            <span className={cn(item.isSummary ? 'font-medium text-foreground' : 'text-muted-foreground')}>
                              {item.isSummary ? item.symbol : ''}
                            </span>
                          </div>
                        </td>
                        <td className="border border-border/50 px-2 py-1 align-top text-foreground">
                          <span className={cn(item.isSummary ? 'text-foreground' : 'pl-6 text-muted-foreground')}>
                            {age || '-'}
                          </span>
                        </td>
                        {industryColumns.map((column) => {
                          const value = item.row[column.key];
                          const selected = selection?.symbol === item.symbol && selection?.industry === column.key;
                          const display = formatPivotValue(value);
                          return (
                            <td
                              key={`${item.symbol}-${column.key}-${rowIndex}`}
                              className={cn(
                                'border border-border/50 px-2 py-1 align-top text-foreground cursor-pointer',
                                display.isNumeric ? 'font-semibold' : '',
                                selected ? 'bg-accent/40' : 'hover:bg-accent/20'
                              )}
                              onClick={() => {
                                setSelection({ symbol: item.symbol, industry: column.key });
                                setModalOpen(true);
                              }}
                            >
                              {display.text}
                            </td>
                          );
                        })}
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="flex h-[240px] items-center justify-center text-sm text-muted-foreground">暂无 Pivot 数据</div>
          )}
        </CardContent>
      </Card>

      <Dialog open={modalOpen} onOpenChange={setModalOpen}>
        <DialogContent
          className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 p-0 flex flex-col overflow-hidden"
          style={
            panelSize
              ? {
                  width: panelSize.w,
                  height: panelSize.h,
                  maxWidth: '96vw',
                  maxHeight: '92vh',
                }
              : undefined
          }
        >
          <DialogHeader className="px-6 pt-6">
            <DialogTitle>图表详情（弹窗）</DialogTitle>
            {selection ? (
              <div className="text-xs text-muted-foreground">
                {selection.symbol} · {selection.industry} · {indicatorLabel} · {tradeDate}
                {dateRangeLabel ? ` · ${dateRangeLabel}` : ''}
              </div>
            ) : null}
          </DialogHeader>

          <div className="flex-1 min-h-0 px-6 pb-6 overflow-auto">
            <div className="mt-2 flex items-center justify-end">
              <Button variant="outline" size="sm" disabled={!selection || drilldownLoading} onClick={requestDrilldown}>
                刷新
              </Button>
            </div>

            {drilldownError ? (
              <div className="mt-4 rounded-md border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">{drilldownError}</div>
            ) : null}

            <div className="mt-4">
              {drilldownLoading ? (
                <div className="flex h-[320px] items-center justify-center text-sm text-muted-foreground">加载面板中...</div>
              ) : drilldown && panelAges.length ? (
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
                  {panelAges.map((age) => {
                    const fig = buildPanelFigure(drilldown, age, indicatorLabel);
                    return (
                      <div key={age} className="rounded-md border border-border/60 bg-card/30 p-3">
                        <div className="text-xs font-semibold text-foreground mb-2">{age}</div>
                        <div className="h-[220px]">
                          <Plot
                            data={fig.data as any[]}
                            layout={{ ...fig.layout, autosize: true }}
                            useResizeHandler
                            style={{ width: '100%', height: '100%' }}
                            config={{ displayModeBar: false, responsive: true }}
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div className="flex h-[320px] items-center justify-center text-sm text-muted-foreground">暂无面板数据</div>
              )}
            </div>
          </div>

          <div
            className="absolute bottom-2 right-2 size-4 cursor-se-resize rounded-sm border border-border bg-background/70"
            onPointerDown={(e) => {
              if (!panelSize) return;
              e.preventDefault();
              resizeRef.current = {
                startX: e.clientX,
                startY: e.clientY,
                startW: panelSize.w,
                startH: panelSize.h,
              };
            }}
          />
        </DialogContent>
      </Dialog>
    </div>
  );
}
