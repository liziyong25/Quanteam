import React, { useEffect, useMemo, useState } from 'react';

import { Button } from '@/app/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/app/components/ui/card';
import { DatePicker } from '@/app/components/ui/date-picker';
import { cn } from '@/lib/utils';
import { dailyApi, TableResponse } from '@/lib/api/daily';
import { KlineModal } from './KlineModal';
import { DataTable, SortState, SUMMARY_LABELS, toView } from './DailyTables';

const PAGE_SIZE = 200;
const DEFAULT_SORT: SortState = { column: 'age_limit', direction: 'asc' };

const SUMMARY_INT_COLUMNS = new Set(['tkn_vol', 'gvn_vol', 'trade_vol', 'symbol_count', 'trade_count']);
const SUMMARY_TWO_DECIMAL_COLUMNS = new Set(['mean_weight_pct_ytm_bp', 'median_weight_pct_ytm_bp']);

const INC_BOND_COLUMNS = [
  'symbol',
  'short_name',
  'age_limit',
  'trade_date',
  'pre_date',
  'close_price',
  'pre_yield',
  'close_yield',
  'zz_val',
  'bias_bp',
  'pct_ytm',
  'weight_pct_ytm',
  'vol',
  'agent',
  'age_limit_type',
  'delist_date',
  'actual_yield',
] as const;

const INC_BOND_LABELS: Record<(typeof INC_BOND_COLUMNS)[number], string> = {
  symbol: '债券代码',
  short_name: '债券名称',
  age_limit: '剩余年限',
  trade_date: '当前日期',
  pre_date: '上一交易日',
  close_price: '收盘净价',
  pre_yield: '上一收益率',
  close_yield: '收盘收益率',
  zz_val: '估值',
  bias_bp: '成交偏离(BP)',
  pct_ytm: '收益率涨幅/BP',
  weight_pct_ytm: '加权收益率涨幅/BP',
  vol: '成交量',
  agent: '中介',
  age_limit_type: '剩余年限类型',
  delist_date: '到期日',
  actual_yield: '税后收益',
};

const INC_BOND_INT_COLUMNS = new Set(['vol']);
const INC_BOND_TWO_DECIMAL_COLUMNS = new Set(['pct_ytm', 'weight_pct_ytm', 'actual_yield', 'bias_bp']);
const INC_BOND_NUMERIC_COLUMNS = new Set([
  'age_limit',
  'close_price',
  'pre_yield',
  'close_yield',
  'zz_val',
  'pct_ytm',
  'weight_pct_ytm',
  'vol',
  'actual_yield',
  'bias_bp',
]);

type SummaryCell = string | number | boolean | null;

function toNumber(value: unknown) {
  if (value === null || value === undefined) return null;
  const num = Number(value);
  if (!Number.isFinite(num)) return null;
  return num;
}

function formatNumber(value: unknown, decimals: number): SummaryCell {
  if (value === null || value === undefined) return '-';
  const num = Number(value);
  if (!Number.isFinite(num)) return typeof value === 'string' ? value : '-';
  return num.toFixed(decimals);
}

function formatSummaryTable(table: TableResponse | null): TableResponse | null {
  if (!table) return null;
  const rows = table.rows.map((row) =>
    row.map((value, index) => {
      const col = table.columns[index];
      if (SUMMARY_INT_COLUMNS.has(col)) return formatNumber(value, 0);
      if (SUMMARY_TWO_DECIMAL_COLUMNS.has(col)) return formatNumber(value, 2);
      return value;
    })
  );
  return { ...table, rows };
}

function formatIncBondTable(table: TableResponse | null): TableResponse | null {
  if (!table) return null;
  const closeYieldIndex = table.columns.indexOf('close_yield');
  const zzValIndex = table.columns.indexOf('zz_val');
  const rows = table.rows.map((row) => {
    const closeYield = closeYieldIndex >= 0 ? toNumber(row[closeYieldIndex]) : null;
    const zzVal = zzValIndex >= 0 ? toNumber(row[zzValIndex]) : null;
    const bias = closeYield === null || zzVal === null ? null : (closeYield - zzVal) * 100;

    return INC_BOND_COLUMNS.map((column) => {
      if (column === 'bias_bp') return formatNumber(bias, 2);
      const index = table.columns.indexOf(column);
      if (index < 0) return '-';
      const value = row[index];
      if (!INC_BOND_NUMERIC_COLUMNS.has(column)) return value;
      if (INC_BOND_INT_COLUMNS.has(column)) return formatNumber(value, 0);
      if (INC_BOND_TWO_DECIMAL_COLUMNS.has(column)) return formatNumber(value, 2);
      return formatNumber(value, 4);
    });
  });

  const filters: Record<string, string[]> = {};
  INC_BOND_COLUMNS.forEach((col) => {
    if (table.filters?.[col]) {
      filters[col] = table.filters[col];
    }
  });

  return {
    ...table,
    columns: [...INC_BOND_COLUMNS],
    rows,
    filters: Object.keys(filters).length ? filters : undefined,
  };
}

function buildGroupedRowClass(table: TableResponse | null, groupColumn: string) {
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
  return (row: Array<string | number | boolean | null>) => {
    const key = String(row[index] ?? '');
    return cn(mapping[key] ?? '', 'hover:bg-accent/20');
  };
}

export function DailyReportPage() {
  const [dates, setDates] = useState<string[]>([]);
  const [selectedDate, setSelectedDate] = useState<string>('');
  const [summary, setSummary] = useState<TableResponse | null>(null);
  const [incBond, setIncBond] = useState<TableResponse | null>(null);
  const [loadingDates, setLoadingDates] = useState(false);
  const [loadingSummary, setLoadingSummary] = useState(false);
  const [loadingIncBond, setLoadingIncBond] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [sort, setSort] = useState<SortState>(DEFAULT_SORT);
  const [filters, setFilters] = useState<Record<string, string>>({});
  const [klineOpen, setKlineOpen] = useState(false);
  const [klineSymbol, setKlineSymbol] = useState<string | null>(null);
  const [klineMeta, setKlineMeta] = useState<
    | {
        short_name?: string | null;
        age_limit?: number | string | null;
        close_yield?: number | string | null;
        zz_val?: number | string | null;
        pct_ytm?: number | string | null;
        bias_bp?: number | string | null;
        delist_date?: string | null;
        actual_yield?: number | string | null;
      }
    | undefined
  >(undefined);

  const availableDates = useMemo(() => dates, [dates]);

  useEffect(() => {
    setLoadingDates(true);
    setError(null);
    dailyApi
      .getDates()
      .then((res) => {
        const items = res.items ?? [];
        setDates(items);
        if (items.length > 0) {
          setSelectedDate(items[0]);
        }
      })
      .catch((e: any) => setError(e?.message || '无法获取日报日期'))
      .finally(() => setLoadingDates(false));
  }, []);

  useEffect(() => {
    if (!selectedDate) return;
    setLoadingSummary(true);
    dailyApi
      .getSummary(selectedDate, 1, 200)
      .then((res) => setSummary(res))
      .catch((e: any) => setError(e?.message || '无法获取汇总'))
      .finally(() => setLoadingSummary(false));
  }, [selectedDate]);

  useEffect(() => {
    if (!selectedDate) return;
    setLoadingIncBond(true);
    dailyApi
      .getIncBond(selectedDate, {
        page,
        page_size: PAGE_SIZE,
        sort_by: sort.column || undefined,
        sort_dir: sort.direction || undefined,
        filter_symbol: filters.symbol || undefined,
        filter_common_class: filters.common_class || undefined,
        filter_age_limit_type: filters.age_limit_type || undefined,
        filter_agent: filters.agent || undefined,
      })
      .then((res) => setIncBond(res))
      .catch((e: any) => setError(e?.message || '无法获取逐笔成交'))
      .finally(() => setLoadingIncBond(false));
  }, [selectedDate, page, sort, filters]);

  const summaryView = useMemo(() => toView(formatSummaryTable(summary), SUMMARY_LABELS), [summary]);
  const formattedIncBond = useMemo(() => formatIncBondTable(incBond), [incBond]);
  const incBondView = useMemo(() => toView(formattedIncBond, INC_BOND_LABELS), [formattedIncBond]);
  const incBondRowClassName = useMemo(() => buildGroupedRowClass(formattedIncBond, 'age_limit_type'), [formattedIncBond]);

  const classOptions = useMemo(() => incBond?.filters?.common_class ?? [], [incBond]);
  const activeClass = filters.common_class ?? '';

  useEffect(() => {
    if (!classOptions.length) return;
    if (filters.common_class !== undefined) return;
    setFilters((prev) => ({ ...prev, common_class: classOptions[0] }));
    setPage(1);
  }, [classOptions, filters.common_class]);

  const totalPages = useMemo(() => {
    if (!incBond) return 1;
    return Math.max(1, Math.ceil(incBond.total / PAGE_SIZE));
  }, [incBond]);

  const summaryRowClassName = useMemo(() => buildGroupedRowClass(summary, 'common_class'), [summary]);

  return (
    <div className="mx-auto flex w-full max-w-[2200px] flex-col gap-6">
      <div className="flex flex-col gap-3 rounded-xl border bg-card/50 p-4 md:flex-row md:items-end md:justify-between">
        <div className="flex flex-col gap-1">
          <div className="text-lg font-semibold">市场日报</div>
          <div className="text-xs text-muted-foreground">数据来自日报缓存表，按日期查询</div>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <div>
            <div className="mb-1 text-xs text-muted-foreground">选择日期</div>
            <DatePicker
              value={selectedDate}
              availableDates={availableDates}
              disabled={loadingDates || dates.length === 0}
              onChange={(v) => {
                setSelectedDate(v);
                setPage(1);
                setSort(DEFAULT_SORT);
                setFilters({});
                setError(null);
              }}
            />
          </div>
          <div className="flex items-center gap-2">
            <a
              href={selectedDate ? dailyApi.excelUrl(selectedDate) : '#'}
              className={cn(
                'inline-flex h-9 items-center rounded-md border border-border bg-background px-3 text-sm hover:bg-accent/30',
                !selectedDate ? 'pointer-events-none opacity-50' : ''
              )}
              target="_blank"
              rel="noreferrer"
            >
              下载 Excel
            </a>
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                if (!selectedDate) return;
                dailyApi.getSummary(selectedDate, 1, 200).then(setSummary).catch(() => undefined);
                dailyApi
                  .getIncBond(selectedDate, {
                    page,
                    page_size: PAGE_SIZE,
                    sort_by: sort.column || undefined,
                    sort_dir: sort.direction || undefined,
                    filter_symbol: filters.symbol || undefined,
                    filter_common_class: filters.common_class || undefined,
                    filter_age_limit_type: filters.age_limit_type || undefined,
                    filter_agent: filters.agent || undefined,
                  })
                  .then(setIncBond)
                  .catch(() => undefined);
              }}
            >
              刷新
            </Button>
          </div>
        </div>
      </div>

      {error ? <div className="rounded-md border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">{error}</div> : null}

      <Card>
        <CardHeader>
          <CardTitle>汇总</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="relative w-full overflow-auto max-h-[320px] rounded-md border">
            {loadingSummary ? (
              <div className="flex h-[180px] items-center justify-center text-sm text-muted-foreground">加载中…</div>
            ) : summaryView ? (
              <DataTable
                columns={summaryView.columns}
                labels={summaryView.labels}
                rows={summaryView.rows}
                filters={{}}
                filterOptions={null}
                onFiltersChange={() => undefined}
                sort={{ column: null, direction: null }}
                onSortChange={() => undefined}
                filterColumns={[]}
                enableSort={false}
                rowClassName={summaryRowClassName ?? undefined}
              />
            ) : (
              <div className="flex h-[180px] items-center justify-center text-sm text-muted-foreground">暂无数据</div>
            )}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>逐笔成交</CardTitle>
        </CardHeader>
        <CardContent>
          {classOptions.length > 0 ? (
            <div className="mb-3 flex flex-wrap gap-2">
              {classOptions.map((item) => (
                <Button
                  key={item}
                  variant={activeClass === item ? 'default' : 'outline'}
                  size="sm"
                  onClick={() => {
                    setPage(1);
                    setFilters((prev) => ({ ...prev, common_class: item }));
                  }}
                >
                  {item}
                </Button>
              ))}
            </div>
          ) : null}

          <div className="rounded-md border">
            <div className="relative w-full overflow-auto max-h-[70vh]">
              {loadingIncBond ? (
                <div className="flex h-[240px] items-center justify-center text-sm text-muted-foreground">加载中…</div>
              ) : incBondView ? (
                <DataTable
                  columns={incBondView.columns}
                  labels={incBondView.labels}
                  rows={incBondView.rows}
                  filters={filters}
                  filterOptions={incBondView.filters ?? null}
                  onFiltersChange={(next) => {
                    setPage(1);
                    setFilters(next);
                  }}
                  sort={sort}
                  onSortChange={(next) => {
                    setPage(1);
                    setSort(next);
                  }}
                  filterColumns={['symbol', 'age_limit_type', 'agent']}
                  rowClassName={incBondRowClassName ?? undefined}
                  onRowDoubleClick={(row) => {
                    const idx = incBondView.columns.indexOf('symbol');
                    const raw = idx >= 0 ? row[idx] : null;
                    const sym = typeof raw === 'string' ? raw : null;
                    if (!sym) return;

                    const at = (col: string) => {
                      const i = incBondView.columns.indexOf(col);
                      return i >= 0 ? row[i] : null;
                    };

                    setKlineSymbol(sym);
                    setKlineMeta({
                      short_name: (at('short_name') as any) ?? null,
                      age_limit: (at('age_limit') as any) ?? null,
                      close_yield: (at('close_yield') as any) ?? null,
                      zz_val: (at('zz_val') as any) ?? null,
                      pct_ytm: (at('pct_ytm') as any) ?? null,
                      bias_bp: (at('bias_bp') as any) ?? null,
                      delist_date: (at('delist_date') as any) ?? null,
                      actual_yield: (at('actual_yield') as any) ?? null,
                    });
                    setKlineOpen(true);
                  }}
                />
              ) : (
                <div className="flex h-[240px] items-center justify-center text-sm text-muted-foreground">暂无数据</div>
              )}
            </div>

            <div className="flex items-center justify-between gap-2 px-4 py-3">
              <div className="text-xs text-muted-foreground">
                第 {incBond?.page ?? page} 页 / 共 {totalPages} 页（共 {incBond?.total ?? 0} 行）
              </div>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                >
                  上一页
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page >= totalPages}
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                >
                  下一页
                </Button>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>

      <KlineModal open={klineOpen} onOpenChange={setKlineOpen} symbol={klineSymbol} endDate={selectedDate || null} meta={klineMeta} />
    </div>
  );
}
