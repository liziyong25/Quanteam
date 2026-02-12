import React, { useEffect, useMemo, useRef, useState } from 'react';

import { Button } from '@/app/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/app/components/ui/card';
import { Input } from '@/app/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/app/components/ui/select';
import { cn } from '@/lib/utils';
import {
  profitEstimatorApi,
  BondTypeOption,
  TableResponse,
} from '@/lib/api/profitestimator';
import { CellValue, DataTable, SortState, formatCell, toView } from '@/pages/daily-report/DailyTables';

import { ProfitEstimatorMetaItem, ProfitEstimatorPlotModal, ProfitEstimatorQuery } from './ProfitEstimatorPlotModal';

const RESULTS_PAGE_SIZE = 200;
const CURVE_PAGE_SIZE = 200;

const RESULT_COLUMNS = [
  'symbol',
  'short_name',
  '票息(%)',
  '税率(%)',
  '返税(%)',
  '个券净价',
  '个券估值',
  '剩余期限(年)',
  '久期',
  '曲线估值',
  '曲线净价',
  '个券-曲线(BP)',
  '远期期限(年)',
  '远期曲线估值',
  '骑乘收益(BP)',
  '远期个券估值',
  '远期个券净价',
  '票息收入',
  '骑乘收益(净价)',
  '税额',
  '返税收入',
  '总收入',
  '持有期(天数)',
  '年化收益(%)',
];

const RESULT_LABELS: Record<string, string> = {
  symbol: '债券代码',
  short_name: '债券简称',
  '票息(%)': '票息(%)',
  '税率(%)': '税率(%)',
  '返税(%)': '返税(%)',
  '个券净价': '个券净价',
  '个券估值': '个券估值',
  '剩余期限(年)': '剩余期限(年)',
  '久期': '久期',
  '曲线估值': '曲线估值',
  '曲线净价': '曲线净价',
  '个券-曲线(BP)': '个券-曲线(BP)',
  '远期期限(年)': '远期期限(年)',
  '远期曲线估值': '远期曲线估值',
  '骑乘收益(BP)': '骑乘收益(BP)',
  '远期个券估值': '远期个券估值',
  '远期个券净价': '远期个券净价',
  '票息收入': '票息收入',
  '骑乘收益(净价)': '骑乘收益(净价)',
  '税额': '税额',
  '返税收入': '返税收入',
  '总收入': '总收入',
  '持有期(天数)': '持有期(天数)',
  '年化收益(%)': '年化收益(%)',
};

const TWO_DECIMAL_COLUMNS = new Set(['剩余期限(年)', '久期']);

const RESULT_ROW_COLORS = [
  'bg-[var(--profit-row-1)]',
  'bg-[var(--profit-row-2)]',
  'bg-[var(--profit-row-3)]',
  'bg-[var(--profit-row-4)]',
  'bg-[var(--profit-row-5)]',
  'bg-[var(--profit-row-6)]',
];

type QueryState = ProfitEstimatorQuery;

function toCell(value: unknown, fallback: CellValue = null): CellValue {
  if (value === null || value === undefined) return fallback;
  if (typeof value === 'string' || typeof value === 'number' || typeof value === 'boolean') {
    return value;
  }
  if (value instanceof Date) {
    return value.toISOString();
  }
  try {
    return JSON.stringify(value);
  } catch {
    return String(value);
  }
}

function formatResultValue(column: string, value: unknown): CellValue {
  if (!TWO_DECIMAL_COLUMNS.has(column)) {
    return toCell(value, null);
  }
  if (value === null || value === undefined) return null;
  const num = Number(value);
  if (!Number.isFinite(num)) return toCell(value, null);
  return num.toFixed(2);
}

function formatResultsTable(table: TableResponse | null | undefined): TableResponse | null {
  if (!table) return null;
  const rows: CellValue[][] = table.rows.map((row) =>
    RESULT_COLUMNS.map((column) => {
      const index = table.columns.indexOf(column);
      const value = index >= 0 ? row[index] : null;
      return formatResultValue(column, value);
    })
  );
  return {
    ...table,
    columns: RESULT_COLUMNS,
    rows,
  };
}

function parseOptionalNumber(raw: string): number | undefined {
  if (!raw) return undefined;
  const value = Number(raw);
  return Number.isFinite(value) ? value : undefined;
}

function parseRequiredNumber(raw: string): number | null {
  if (!raw) return null;
  const value = Number(raw);
  if (!Number.isFinite(value) || value <= 0) return null;
  return value;
}

export function ProfitEstimatorDashboard() {
  const [bondTypes, setBondTypes] = useState<BondTypeOption[]>([]);
  const [tradeDate, setTradeDate] = useState('');
  const [bondType, setBondType] = useState('');
  const [holdingDays, setHoldingDays] = useState('180');
  const [ageLimitMin, setAgeLimitMin] = useState('0');
  const [ageLimitMax, setAgeLimitMax] = useState('10');
  const [activeQuery, setActiveQuery] = useState<QueryState | null>(null);

  const [results, setResults] = useState<TableResponse | null>(null);
  const [curve, setCurve] = useState<TableResponse | null>(null);
  const [loadingResults, setLoadingResults] = useState(false);
  const [loadingCurve, setLoadingCurve] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [issuerList, setIssuerList] = useState<string[]>([]);
  const [loadingIssuers, setLoadingIssuers] = useState(false);
  const [issuerError, setIssuerError] = useState<string | null>(null);
  const [loadingBondTypes, setLoadingBondTypes] = useState(false);

  const [showCurve, setShowCurve] = useState(false);
  const [resultsPage, setResultsPage] = useState(1);
  const [curvePage, setCurvePage] = useState(1);
  const [resultsSort, setResultsSort] = useState<SortState>({ column: null, direction: null });
  const [curveSort, setCurveSort] = useState<SortState>({ column: null, direction: null });

  const [plotOpen, setPlotOpen] = useState(false);
  const [plotSymbol, setPlotSymbol] = useState<string | null>(null);
  const [plotMeta, setPlotMeta] = useState<ProfitEstimatorMetaItem[] | undefined>(undefined);

  const [preparedReady, setPreparedReady] = useState(false);

  const resultsAbortRef = useRef<AbortController | null>(null);
  const curveAbortRef = useRef<AbortController | null>(null);

  useEffect(() => {
    setLoadingBondTypes(true);
    profitEstimatorApi
      .getBondTypes()
      .then((data) => {
        setBondTypes(data.items || []);
        if (data.items?.length) {
          setBondType((prev) => prev || data.items[0].bond_type);
        }
      })
      .catch((err: any) => setError(err?.message || '无法加载债券类型'))
      .finally(() => setLoadingBondTypes(false));
  }, []);

  useEffect(() => {
    if (!bondType) {
      setIssuerList([]);
      return;
    }
    setLoadingIssuers(true);
    setIssuerError(null);
    profitEstimatorApi
      .getIssuers(bondType)
      .then((data) => setIssuerList(data.items || []))
      .catch((err: any) => setIssuerError(err?.message || '无法加载发行人列表'))
      .finally(() => setLoadingIssuers(false));
  }, [bondType]);

  useEffect(() => {
    if (!activeQuery) return;
    curveAbortRef.current?.abort();
    const controller = new AbortController();
    curveAbortRef.current = controller;
    setLoadingCurve(true);
    setError(null);
    profitEstimatorApi
      .compute(
        {
          trade_date: activeQuery.tradeDate,
          bond_type: activeQuery.bondType,
          holding_days: activeQuery.holdingDays,
          age_limit_min: activeQuery.ageLimitMin,
          age_limit_max: activeQuery.ageLimitMax,
          include_results: false,
          include_curve: true,
          curve_page: curvePage,
          curve_page_size: CURVE_PAGE_SIZE,
          curve_sort_by: curveSort.column ?? undefined,
          curve_sort_dir: curveSort.direction ?? undefined,
        },
        { signal: controller.signal }
      )
      .then((data) => {
        if (controller.signal.aborted) return;
        setCurve(data.curve);
        setPreparedReady(true);
      })
      .catch((err: any) => {
        if (controller.signal.aborted || err?.code === 'ERR_CANCELED' || err?.name === 'CanceledError') return;
        setError(err?.response?.data?.detail || err?.message || '样本曲线加载失败');
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setLoadingCurve(false);
        }
      });
    return () => controller.abort();
  }, [activeQuery, curvePage, curveSort]);

  useEffect(() => {
    if (!activeQuery || !preparedReady) return;
    resultsAbortRef.current?.abort();
    const controller = new AbortController();
    resultsAbortRef.current = controller;
    setLoadingResults(true);
    setError(null);
    profitEstimatorApi
      .compute(
        {
          trade_date: activeQuery.tradeDate,
          bond_type: activeQuery.bondType,
          holding_days: activeQuery.holdingDays,
          age_limit_min: activeQuery.ageLimitMin,
          age_limit_max: activeQuery.ageLimitMax,
          include_results: true,
          include_curve: false,
          results_fast_mode: true,
          results_page: resultsPage,
          results_page_size: RESULTS_PAGE_SIZE,
          results_sort_by: resultsSort.column ?? undefined,
          results_sort_dir: resultsSort.direction ?? undefined,
        },
        { signal: controller.signal, timeout: 30000 }
      )
      .then((data) => {
        if (controller.signal.aborted) return;
        setResults(data.results);
      })
      .catch((err: any) => {
        if (controller.signal.aborted || err?.code === 'ERR_CANCELED' || err?.name === 'CanceledError') return;
        setError(err?.response?.data?.detail || err?.message || '收益测算失败');
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          setLoadingResults(false);
        }
      });
    return () => controller.abort();
  }, [activeQuery, preparedReady, resultsPage, resultsSort]);

  const resultsTotalPages = useMemo(() => {
    if (!results) return 1;
    return Math.max(1, Math.ceil(results.total / RESULTS_PAGE_SIZE));
  }, [results]);

  const curveTotalPages = useMemo(() => {
    if (!curve) return 1;
    return Math.max(1, Math.ceil(curve.total / CURVE_PAGE_SIZE));
  }, [curve]);

  const resultsView = useMemo(() => toView(formatResultsTable(results), RESULT_LABELS), [results]);
  const curveView = useMemo(() => {
    if (!curve) return null;
    return {
      columns: curve.columns,
      labels: curve.columns,
      rows: curve.rows as CellValue[][],
      filters: curve.filters ?? null,
    };
  }, [curve]);

  const resultsRowClassName = useMemo(() => {
    return (_row: CellValue[], rowIndex: number) =>
      cn(RESULT_ROW_COLORS[rowIndex % RESULT_ROW_COLORS.length], 'hover:bg-accent/20');
  }, []);

  const handleRun = () => {
    const holding = parseRequiredNumber(holdingDays);
    if (!tradeDate || !bondType || holding === null) {
      setError('请填写交易日期、债券类型与持有期。');
      return;
    }
    const ageMin = parseOptionalNumber(ageLimitMin);
    const ageMax = parseOptionalNumber(ageLimitMax);
    if (ageMin !== undefined && ageMax !== undefined && ageMin > ageMax) {
      setError('期限范围的下限不能大于上限。');
      return;
    }

    setResultsPage(1);
    setCurvePage(1);
    setResultsSort({ column: null, direction: null });
    setCurveSort({ column: null, direction: null });
    setResults(null);
    setCurve(null);
    setPreparedReady(false);
    setPlotOpen(false);
    setPlotSymbol(null);
    setPlotMeta(undefined);
    setShowCurve(false);
    setActiveQuery({
      tradeDate,
      bondType,
      holdingDays: holding,
      ageLimitMin: ageMin,
      ageLimitMax: ageMax,
    });
  };

  const buildPlotMeta = (row: CellValue[], columns: string[]): ProfitEstimatorMetaItem[] => {
    const fields = [
      'symbol',
      'short_name',
      '剩余期限(年)',
      '久期',
      '票息(%)',
      '个券估值',
      '曲线估值',
      '年化收益(%)',
    ];
    return fields.map((field) => {
      const idx = columns.indexOf(field);
      const raw = idx >= 0 ? row[idx] : null;
      const formatted = formatCell(raw ?? null, field);
      return {
        label: RESULT_LABELS[field] ?? field,
        value: formatted === null ? '-' : String(formatted),
      };
    });
  };

  return (
    <div className="mx-auto flex w-full max-w-[2200px] flex-col gap-6">
      <div className="flex flex-col gap-3 rounded-xl border bg-card/50 p-4 md:flex-row md:items-end md:justify-between">
        <div className="flex flex-col gap-1">
          <div className="text-lg font-semibold">收益测算</div>
          <div className="text-xs text-muted-foreground">按收益测算条件计算骑乘收益与曲线估值</div>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <div className="flex flex-col gap-1 text-xs text-muted-foreground">
            交易日期
            <Input type="date" value={tradeDate} onChange={(e) => setTradeDate(e.target.value)} className="min-w-[180px]" />
          </div>
          <div className="flex flex-col gap-1 text-xs text-muted-foreground">
            债券类型
            <Select value={bondType} onValueChange={setBondType} disabled={loadingBondTypes}>
              <SelectTrigger className="min-w-[200px]">
                <SelectValue placeholder={loadingBondTypes ? '加载中...' : '选择债券类型'} />
              </SelectTrigger>
              <SelectContent>
                {bondTypes.map((item) => (
                  <SelectItem key={item.bond_type} value={item.bond_type}>
                    {item.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="flex flex-col gap-1 text-xs text-muted-foreground">
            持有期(天)
            <Input
              type="number"
              min={1}
              value={holdingDays}
              onChange={(e) => setHoldingDays(e.target.value)}
              className="w-[120px]"
            />
          </div>
          <div className="flex flex-col gap-1 text-xs text-muted-foreground">
            期限范围
            <div className="flex items-center gap-2">
              <Input
                type="number"
                min={0}
                value={ageLimitMin}
                onChange={(e) => setAgeLimitMin(e.target.value)}
                className="w-[90px]"
              />
              <span className="text-xs text-muted-foreground">-</span>
              <Input
                type="number"
                min={0}
                value={ageLimitMax}
                onChange={(e) => setAgeLimitMax(e.target.value)}
                className="w-[90px]"
              />
            </div>
          </div>
          <Button onClick={handleRun} disabled={loadingResults || loadingCurve}>
            {loadingResults || loadingCurve ? '运行中...' : 'Run'}
          </Button>
        </div>
      </div>

      {bondType ? (
        <div className="rounded-md border border-border/60 bg-card/40 px-4 py-3 text-xs text-muted-foreground">
          <span className="mr-2 text-foreground font-medium">样本发行人:</span>
          {loadingIssuers
            ? '加载中...'
            : issuerError
              ? `加载失败: ${issuerError}`
              : issuerList.length
                ? issuerList.join(', ')
                : '暂无'}
        </div>
      ) : null}

      {error ? (
        <div className="rounded-md border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">{error}</div>
      ) : null}

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>样本曲线</CardTitle>
          <div className="flex items-center gap-3">
            {curve ? <div className="text-xs text-muted-foreground">共 {curve.total} 行</div> : null}
            <Button variant="outline" size="sm" onClick={() => setShowCurve((prev) => !prev)}>
              {showCurve ? '收起' : '展开'}
            </Button>
          </div>
        </CardHeader>
        <CardContent>
          {showCurve ? (
            <div className="rounded-md border">
              <div className="relative w-full overflow-auto max-h-[55vh]">
                {!activeQuery ? (
                  <div className="flex h-[200px] items-center justify-center text-sm text-muted-foreground">请先运行查询</div>
                ) : loadingCurve && !curveView ? (
                  <div className="flex h-[200px] items-center justify-center text-sm text-muted-foreground">加载中…</div>
                ) : curveView ? (
                  <DataTable
                    columns={curveView.columns}
                    labels={curveView.labels}
                    rows={curveView.rows}
                    filters={{}}
                    filterOptions={null}
                    onFiltersChange={() => undefined}
                    sort={curveSort}
                    onSortChange={(next) => {
                      setCurvePage(1);
                      setCurveSort(next);
                    }}
                    filterColumns={[]}
                    enableSort
                  />
                ) : (
                  <div className="flex h-[200px] items-center justify-center text-sm text-muted-foreground">暂无数据</div>
                )}
              </div>
              {curve ? (
                <div className="flex items-center justify-between gap-2 px-4 py-3">
                  <div className="text-xs text-muted-foreground">
                    第 {curve.page ?? curvePage} 页 / 共 {curveTotalPages} 页（共 {curve.total} 行）
                  </div>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={curvePage <= 1}
                      onClick={() => setCurvePage((p) => Math.max(1, p - 1))}
                    >
                      上一页
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      disabled={curvePage >= curveTotalPages}
                      onClick={() => setCurvePage((p) => Math.min(curveTotalPages, p + 1))}
                    >
                      下一页
                    </Button>
                  </div>
                </div>
              ) : null}
            </div>
          ) : (
            <div className="text-sm text-muted-foreground">已隐藏，点击展开。</div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="flex flex-row items-center justify-between">
          <CardTitle>骑乘收益测算</CardTitle>
          {results ? <div className="text-xs text-muted-foreground">共 {results.total} 行</div> : null}
        </CardHeader>
        <CardContent>
          <div className="rounded-md border">
            <div className="relative w-full overflow-auto max-h-[70vh]">
              {!activeQuery ? (
                <div className="flex h-[240px] items-center justify-center text-sm text-muted-foreground">请先运行查询</div>
              ) : loadingResults && !resultsView ? (
                <div className="flex h-[240px] items-center justify-center text-sm text-muted-foreground">加载中…</div>
              ) : resultsView ? (
                <DataTable
                  columns={resultsView.columns}
                  labels={resultsView.labels}
                  rows={resultsView.rows}
                  filters={{}}
                  filterOptions={null}
                  onFiltersChange={() => undefined}
                  sort={resultsSort}
                  onSortChange={(next) => {
                    setResultsPage(1);
                    setResultsSort(next);
                  }}
                  filterColumns={[]}
                  rowClassName={resultsRowClassName}
                  onRowDoubleClick={(row) => {
                    const idx = resultsView.columns.indexOf('symbol');
                    const raw = idx >= 0 ? row[idx] : null;
                    const symbol = raw ? String(raw) : '';
                    if (!symbol) return;
                    setPlotSymbol(symbol);
                    setPlotMeta(buildPlotMeta(row, resultsView.columns));
                    setPlotOpen(true);
                  }}
                />
              ) : (
                <div className="flex h-[240px] items-center justify-center text-sm text-muted-foreground">暂无数据</div>
              )}
            </div>
            {results ? (
              <div className="flex items-center justify-between gap-2 px-4 py-3">
                <div className="text-xs text-muted-foreground">
                  第 {results.page ?? resultsPage} 页 / 共 {resultsTotalPages} 页（共 {results.total} 行）
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={resultsPage <= 1}
                    onClick={() => setResultsPage((p) => Math.max(1, p - 1))}
                  >
                    上一页
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={resultsPage >= resultsTotalPages}
                    onClick={() => setResultsPage((p) => Math.min(resultsTotalPages, p + 1))}
                  >
                    下一页
                  </Button>
                </div>
              </div>
            ) : null}
          </div>
        </CardContent>
      </Card>

      <ProfitEstimatorPlotModal open={plotOpen} onOpenChange={setPlotOpen} symbol={plotSymbol} query={activeQuery} meta={plotMeta} />
    </div>
  );
}
