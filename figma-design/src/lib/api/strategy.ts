import api from '@/lib/api';

const CACHE_TTL_MS = 5 * 60 * 1000;
const cache = new Map<string, { ts: number; data: any }>();

function cacheGet<T>(key: string): T | undefined {
  const hit = cache.get(key);
  if (!hit) return undefined;
  if (Date.now() - hit.ts > CACHE_TTL_MS) {
    cache.delete(key);
    return undefined;
  }
  return hit.data as T;
}

function cacheSet<T>(key: string, data: T) {
  cache.set(key, { ts: Date.now(), data });
}

export type MetricValue = number | string | null;

export interface SummaryKpis {
  start?: string;
  end?: string;
  period?: number;
  start_value?: number;
  end_value?: number;
  total_return_pct?: number;
  benchmark_return_pct?: number;
  max_drawdown_pct?: number;
  win_rate_pct?: number;
  total_trades?: number;
  total_closed_trades?: number;
  total_open_trades?: number;
}

export interface StrategySummary {
  run_id: string;
  strategy_name: string;
  run_name: string;
  param_label: string;
  updated_at: string;
  metrics: Record<string, MetricValue>;
  kpis: SummaryKpis;
}

export interface StrategyListResponse {
  items: StrategySummary[];
}

export interface TimeSeriesSeries {
  label: string;
  x: string[];
  y: MetricValue[];
}

export interface TimeSeriesMeta {
  title?: string;
  y_format?: string;
}

export interface TimeSeriesResponse {
  name: string;
  series: TimeSeriesSeries[];
  meta: TimeSeriesMeta;
  plotly?: any;
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

export interface TableParams {
  page?: number;
  page_size?: number;
  sort_by?: string;
  sort_dir?: string;
  filter_symbol?: string;
  filter_direction?: string;
  filter_status?: string;
}

function assertStrategyListResponse(value: any, endpoint: string): StrategyListResponse {
  if (!value || !Array.isArray(value.items)) {
    throw new Error(`${endpoint} response missing items[]`);
  }
  return value as StrategyListResponse;
}

export const strategyApi = {
  // èŽ·å–ç­–ç•¥åˆ—è¡¨ï¼ˆè¿”å›žæ‰€æœ‰è¿è¡Œå®žä¾‹çš„æ‘˜è¦ï¼?
  getStrategies: (refresh: boolean = false) => {
    const key = `strategies:refresh=${refresh}`;
    if (!refresh) {
      const hit = cacheGet<StrategyListResponse>(key);
      if (hit) return Promise.resolve(hit);
    }
    return api.get<StrategyListResponse>('/strategies', { params: { refresh } }).then((res) => {
      const data = assertStrategyListResponse(res, '/strategies');
      cacheSet(key, data);
      return data;
    });
  },

  // èŽ·å–ç‰¹å®šç­–ç•¥çš„è¿è¡Œå®žä¾?
  getStrategyRuns: (strategyName: string) => {
    const key = `strategyRuns:${encodeURIComponent(strategyName)}`;
    const hit = cacheGet<StrategyListResponse>(key);
    if (hit) return Promise.resolve(hit);
    const endpoint = `/strategies/${encodeURIComponent(strategyName)}/runs`;
    return api.get<StrategyListResponse>(endpoint).then((res) => {
      const data = assertStrategyListResponse(res, endpoint);
      cacheSet(key, data);
      return data;
    });
  },

  // èŽ·å–è¿è¡Œå®žä¾‹æ‘˜è¦
  getRunSummary: (runId: string) => {
    const key = `runSummary:${encodeURIComponent(runId)}`;
    const hit = cacheGet<StrategySummary>(key);
    if (hit) return Promise.resolve(hit);
    return api.get<StrategySummary>(`/runs/${runId}/summary`).then((res) => {
      cacheSet(key, res);
      return res;
    });
  },

  // èŽ·å–æ—¶é—´åºåˆ—æ•°æ®
  getTimeSeries: (runId: string, name: string, plotly: boolean = false) => {
    const key = `timeseries:${encodeURIComponent(runId)}:${encodeURIComponent(name)}:plotly=${plotly}`;
    const hit = cacheGet<TimeSeriesResponse>(key);
    if (hit) return Promise.resolve(hit);
    return api
      .get<TimeSeriesResponse>(`/runs/${runId}/timeseries`, {
        params: { name, plotly },
      })
      .then((res) => {
        cacheSet(key, res);
        return res;
      });
  },

  // èŽ·å–ä¿¡å·æ•°æ®
  getSignal: (runId: string, symbol?: string) => {
    const key = `signal:${encodeURIComponent(runId)}:${encodeURIComponent(symbol || '')}`;
    const hit = cacheGet<TimeSeriesResponse>(key);
    if (hit) return Promise.resolve(hit);
    return api
      .get<TimeSeriesResponse>(`/runs/${runId}/signal`, {
        params: { symbol },
      })
      .then((res) => {
        cacheSet(key, res);
        return res;
      });
  },

  // èŽ·å–äº¤æ˜“è®°å½•
  getTrades: (runId: string, params: TableParams = {}) => {
    return api.get<TableResponse>(`/runs/${runId}/trades`, { params });
  },

  // èŽ·å–è®¢å•è®°å½•
  getOrders: (runId: string, params: TableParams = {}) => {
    return api.get<TableResponse>(`/runs/${runId}/orders`, { params });
  },

  // plot_ts（按 symbol）
  plotTs: (runId: string, symbol: string) => {
    return api.post<TimeSeriesResponse>(`/runs/${runId}/plot_ts`, { symbol });
  },

  // signal_plot（按 symbol，v2 主链路：indicator.plots(column=symbol)）
  signalPlot: (runId: string, symbol: string) => {
    return api.post<TimeSeriesResponse>(`/runs/${runId}/signal_plot`, { symbol });
  },
};
