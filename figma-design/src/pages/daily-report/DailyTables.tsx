import React from 'react';

export type CellValue = string | number | boolean | null;
export type SortState = { column: string | null; direction: 'asc' | 'desc' | null };

export const FILTER_COLUMNS = ['symbol', 'common_class', 'age_limit_type', 'agent'];

export const SUMMARY_LABELS: Record<string, string> = {
  common_class: '类别',
  age_limit_type: '剩余年限类型',
  mean_weight_pct_ytm_bp: '加权收益率均值(BP)',
  median_weight_pct_ytm_bp: '加权收益率中位数(BP)',
  tkn_vol: 'TKN 量',
  gvn_vol: 'GVN 量',
  trade_vol: '成交量',
  symbol_count: '标的数',
  trade_count: '笔数',
};

export const INC_BOND_LABELS: Record<string, string> = {
  symbol: '债券代码',
  short_name: '债券名称',
  age_limit: '剩余年限',
  trade_date: '当前日期',
  pre_date: '上一交易日',
  close_price: '收盘净价',
  pre_yield: '上一收益率',
  close_yield: '收盘收益率',
  zz_val: '估值收益率',
  bias_bp: '成交偏离(BP)',
  pct_ytm: '收益率涨幅(BP)',
  weight_pct_ytm: '加权收益率涨幅(BP)',
  vol: '成交量',
  agent: '中介',
  age_limit_type: '剩余年限类型',
  delist_date: '到期日',
  actual_yield: '税后收益',
};

function formatDateOnly(value: string) {
  const match = value.match(/^\d{4}-\d{2}-\d{2}/);
  return match ? match[0] : value;
}

function isPercentColumn(column: string) {
  const normalized = column.toLowerCase();
  if (normalized.includes('%')) return true;
  return normalized.includes('yield') || normalized.includes('return') || normalized.includes('pct');
}

export function formatCell(value: CellValue, column: string) {
  if (value === null || value === undefined) return '-';
  if (typeof value === 'number') {
    if (isPercentColumn(column)) return value.toFixed(2);
    return value.toFixed(4);
  }
  if (typeof value === 'boolean') return value ? 'true' : 'false';
  if (typeof value === 'string') return formatDateOnly(value);
  return String(value);
}

export function nextSortState(current: SortState | undefined, column: string): SortState {
  if (!current || current.column !== column) return { column, direction: 'asc' };
  if (current.direction === 'asc') return { column, direction: 'desc' };
  if (current.direction === 'desc') return { column: null, direction: null };
  return { column, direction: 'asc' };
}

export function sortIndicator(direction: SortState['direction'] | null) {
  if (direction === 'asc') return '↑';
  if (direction === 'desc') return '↓';
  return '⇅';
}

export function toView(
  table: { columns: string[]; rows: (number | string | null)[][]; filters?: Record<string, string[]> } | null,
  labels: Record<string, string>
) {
  if (!table) return null;
  return {
    columns: table.columns,
    labels: table.columns.map((c) => labels[c] ?? c),
    rows: table.rows as CellValue[][],
    filters: table.filters ?? null,
  };
}

export function DataTable({
  columns,
  labels,
  rows,
  filters,
  filterOptions,
  onFiltersChange,
  sort,
  onSortChange,
  onRowDoubleClick,
  filterColumns,
  enableSort = true,
  rowClassName,
}: {
  columns: string[];
  labels: string[];
  rows: CellValue[][];
  filters: Record<string, string>;
  filterOptions?: Record<string, string[]> | null;
  onFiltersChange: (next: Record<string, string>) => void;
  sort: SortState;
  onSortChange: (next: SortState) => void;
  onRowDoubleClick?: (row: CellValue[], rowIndex: number) => void;
  filterColumns?: string[];
  enableSort?: boolean;
  rowClassName?: (row: CellValue[], rowIndex: number) => string;
}) {
  const labelList = labels.length === columns.length ? labels : columns;
  const activeFilterColumns = filterColumns ?? FILTER_COLUMNS;
  return (
    <div className="relative w-full">
      <table className="w-full table-fixed border-collapse text-[11px]">
        <thead className="sticky top-0 z-10 bg-card/90 text-xs text-muted-foreground backdrop-blur">
          <tr>
            {columns.map((column, index) => {
              const label = labelList[index] ?? column;
              const isFilterable = activeFilterColumns.includes(column);
              const isSorted = sort?.column === column ? sort.direction : null;
              const options = filterOptions?.[column] ?? [];
              return (
                <th key={column} className="border border-border/50 px-2 py-2 text-left align-top">
                  <div className="flex flex-col gap-1">
                    <span className="text-[11px] font-semibold text-foreground">{label}</span>
                    {isFilterable ? (
                      <select
                        className="w-full rounded-md border border-border bg-background/70 px-2 py-1 text-[11px] text-foreground"
                        value={filters[column] ?? ''}
                        onChange={(event) => {
                          const value = event.target.value;
                          const next = { ...filters };
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
                    ) : enableSort ? (
                      <button
                        type="button"
                        className="inline-flex items-center gap-1 rounded-md border border-border bg-background/70 px-2 py-1 text-[11px] text-muted-foreground hover:bg-accent/30"
                        onClick={() => onSortChange(nextSortState(sort, column))}
                      >
                        排序
                        <span>{sortIndicator(isSorted)}</span>
                      </button>
                    ) : null}
                  </div>
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, rowIndex) => (
            <tr
              key={rowIndex}
              className={rowClassName ? rowClassName(row, rowIndex) : 'hover:bg-muted/20'}
              onDoubleClick={() => onRowDoubleClick?.(row, rowIndex)}
            >
              {columns.map((column, colIndex) => (
                <td key={`${rowIndex}-${column}`} className="border border-border/50 px-2 py-1 align-top text-foreground">
                  <span className="break-words">{formatCell(row[colIndex] ?? null, column)}</span>
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
