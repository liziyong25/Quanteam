import api from '@/lib/api';
import type { AxiosRequestConfig } from 'axios';

export interface DailyReportDateList {
  items: string[];
}

export interface TableResponse {
  columns: string[];
  rows: (number | string | null)[][];
  page: number;
  page_size: number;
  total: number;
  dtypes?: string[];
  filters?: Record<string, string[]>;
}

export interface DailyTableParams {
  page?: number;
  page_size?: number;
  sort_by?: string;
  sort_dir?: 'asc' | 'desc';
  filter_symbol?: string;
  filter_common_class?: string;
  filter_age_limit_type?: string;
  filter_agent?: string;
}

export type KlineRequest = {
  symbol: string;
  start: string;
  end: string;
  include_broker?: boolean;
  include_settlement?: boolean;
  include_valuation?: boolean;
};

export type OhlcPoint = {
  trade_date: string;
  open: number | null;
  high: number | null;
  low: number | null;
  close: number | null;
  vol: number | null;
};

export type LinePoint = {
  trade_date: string;
  value: number | null;
};

export type KlineSeries = {
  yield_ohlc: OhlcPoint[];
  price_ohlc: OhlcPoint[];
};

export type KlineResponse = {
  symbol: string;
  range: { start: string; end: string };
  broker: KlineSeries;
  settlement: KlineSeries;
  valuation: { yield_line: LinePoint[]; price_line: LinePoint[] };
  meta: {
    trade_date_format: 'YYYY-MM-DD';
    timezone: string;
    source: string;
    missing_policy: string;
    timings_ms?: Record<string, number>;
  };
};

export const dailyApi = {
  getDates: () => api.get<DailyReportDateList>('/reports/daily/dates'),
  getSummary: (tradeDate: string, page = 1, pageSize = 200) =>
    api.get<TableResponse>(`/reports/daily/${tradeDate}/summary`, {
      params: { page, page_size: pageSize },
    }),
  getIncBond: (tradeDate: string, params: DailyTableParams) =>
    api.get<TableResponse>(`/reports/daily/${tradeDate}/inc_bond`, { params }),
  postKline: (payload: KlineRequest, config?: AxiosRequestConfig) =>
    api.post<KlineResponse>('/reports/daily/kline', payload, { timeout: 30000, ...(config ?? {}) }),
  excelUrl: (tradeDate: string) => `/api/reports/daily/${tradeDate}/excel`,
};
