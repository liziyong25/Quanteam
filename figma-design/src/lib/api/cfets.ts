import api from '@/lib/api';

export type Indicator = 'netbuy_amount' | 'buy_amount' | 'sell_amount';
export type IndustryMode = 'new' | 'old';
export type CfetsPivotRow = Record<string, string | number | boolean | null> & {
  symbol?: string | number | null;
  new_age?: string | number | null;
};

export type CfetsPivotResponse = {
  trade_date: string;
  indicator: string;
  age_order: string[];
  industries: string[];
  rows: CfetsPivotRow[];
};

export type CfetsDrilldownResponse = {
  symbol: string;
  industry: string;
  indicator: string;
  age_order: string[];
  dates: string[];
  series: Record<string, Array<number | null>>;
  valuation: Array<number | null>;
};

export type CfetsGridSymbol = {
  symbol: string;
  dates: string[];
  indicator: Array<number | null>;
  valuation: Array<number | null>;
};

export type CfetsGridResponse = {
  indicator: string;
  industry?: string | null;
  cumulative: boolean;
  symbols: CfetsGridSymbol[];
};

export type CfetsMetaResponse = {
  latest_trade_date: string;
};

export type CfetsPivotQuery = {
  tradeDate: string;
  indicator?: Indicator;
  start?: string;
  end?: string;
  industryMode?: IndustryMode;
};

export type CfetsDrilldownQuery = {
  industry: string;
  symbol: string;
  indicator?: Indicator;
  start?: string;
  end?: string;
  industryMode?: IndustryMode;
};

export type CfetsGridQuery = {
  indicator?: Indicator;
  industry?: string | null;
  start?: string;
  end?: string;
  cumulative?: boolean;
  limit?: number;
  industryMode?: IndustryMode;
};

export const cfetsApi = {
  getMeta: () => api.get<CfetsMetaResponse>('/cfets/bond/meta'),
  getPivot: (query: CfetsPivotQuery) =>
    api.get<CfetsPivotResponse>('/cfets/bond/pivot', {
      params: {
        trade_date: query.tradeDate,
        indicator: query.indicator ?? 'netbuy_amount',
        start: query.start,
        end: query.end,
        industry_mode: query.industryMode,
      },
    }),
  getDrilldown: (query: CfetsDrilldownQuery) =>
    api.get<CfetsDrilldownResponse>('/cfets/bond/drilldown', {
      params: {
        industry: query.industry,
        symbol: query.symbol,
        indicator: query.indicator ?? 'netbuy_amount',
        start: query.start,
        end: query.end,
        industry_mode: query.industryMode,
      },
    }),
  getGrid: (query: CfetsGridQuery) =>
    api.get<CfetsGridResponse>('/cfets/bond/grid', {
      params: {
        indicator: query.indicator ?? 'netbuy_amount',
        industry: query.industry ?? undefined,
        start: query.start,
        end: query.end,
        cumulative: query.cumulative === false ? 0 : 1,
        limit: query.limit,
        industry_mode: query.industryMode,
      },
    }),
};
