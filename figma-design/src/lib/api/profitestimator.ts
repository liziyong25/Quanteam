import api from '@/lib/api';
import type { AxiosRequestConfig } from 'axios';

export type BondTypeOption = {
  bond_type: string;
  label: string;
};

export type BondTypeListResponse = {
  items: BondTypeOption[];
};

export type IssuerListResponse = {
  items: string[];
};

export type TableResponse = {
  columns: string[];
  rows: (number | string | null)[][];
  page: number;
  page_size: number;
  total: number;
  dtypes?: string[];
  filters?: Record<string, string[]>;
};

export type ProfitEstimatorRequest = {
  trade_date: string;
  bond_type: string;
  holding_days: number;
  age_limit_min?: number;
  age_limit_max?: number;
  include_results?: boolean;
  include_curve?: boolean;
  results_fast_mode?: boolean;
  results_page?: number;
  results_page_size?: number;
  curve_page?: number;
  curve_page_size?: number;
  results_sort_by?: string | null;
  results_sort_dir?: 'asc' | 'desc' | null;
  curve_sort_by?: string | null;
  curve_sort_dir?: 'asc' | 'desc' | null;
};

export type ProfitEstimatorResponse = {
  results: TableResponse;
  curve: TableResponse;
  meta?: { timings_ms?: Record<string, number>; universe_total?: number } | null;
};

export type ProfitEstimatorPlotRequest = {
  trade_date: string;
  bond_type: string;
  holding_days: number;
  age_limit_min?: number;
  age_limit_max?: number;
  symbol: string;
};

export type ProfitEstimatorPlotResponse = {
  plotly: any | null;
};

export const profitEstimatorApi = {
  getBondTypes: () => api.get<BondTypeListResponse>('/profitestimator/bond_types'),
  getIssuers: (bondType: string) =>
    api.get<IssuerListResponse>('/profitestimator/issuers', { params: { bond_type: bondType } }),
  compute: (payload: ProfitEstimatorRequest, config?: AxiosRequestConfig) =>
    api.post<ProfitEstimatorResponse>('/profitestimator/compute', payload, { timeout: 30000, ...(config ?? {}) }),
  plot: (payload: ProfitEstimatorPlotRequest, config?: AxiosRequestConfig) =>
    api.post<ProfitEstimatorPlotResponse>('/profitestimator/plot', payload, { timeout: 30000, ...(config ?? {}) }),
};
