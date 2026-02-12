import api from '@/lib/api';

export type RepoSide = 'repo' | 'rev_repo' | 'both';
export type RepoMode = 'buyback' | 'buyout' | 'credit' | 'sum';

export type RepoCell = {
  amount: number | null;
  rate: number | null;
};

export type RepoPivotRow = {
  new_age: string;
  repo: Record<string, RepoCell | null>;
  rev_repo: Record<string, RepoCell | null>;
};

export type RepoPivotResponse = {
  meta: {
    start: string;
    end: string;
    trade_date: string;
    repo_mode: RepoMode;
  };
  industries: string[];
  age_order: string[];
  rows: RepoPivotRow[];
};

export type RepoPanelResponse = {
  meta: {
    industry: string;
    side: Exclude<RepoSide, 'both'>;
    start: string;
    end: string;
    repo_mode: RepoMode;
  };
  dates: string[];
  columns: string[];
  remaining: Record<string, Array<number | null>>;
  rate: Record<string, Array<number | null>>;
};

export type RepoPivotQuery = {
  start?: string;
  end?: string;
  tradeDate?: string;
  repoMode?: RepoMode;
};

export type RepoPanelQuery = {
  industry: string;
  side: Exclude<RepoSide, 'both'>;
  start?: string;
  end?: string;
  repoMode?: RepoMode;
};

export const repoApi = {
  getPivot: (query: RepoPivotQuery) =>
    api.get<RepoPivotResponse>('/cfets/repo/pivot', {
      params: {
        start: query.start,
        end: query.end,
        trade_date: query.tradeDate,
        repo_mode: query.repoMode,
      },
    }),
  getPanel: (query: RepoPanelQuery) =>
    api.get<RepoPanelResponse>('/cfets/repo/panel', {
      params: {
        industry: query.industry,
        side: query.side,
        start: query.start,
        end: query.end,
        repo_mode: query.repoMode,
      },
    }),
};
