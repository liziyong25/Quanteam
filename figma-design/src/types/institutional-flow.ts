// 机构行为分析数据类型定义

export interface InstitutionalFlowOverview {
  date: string;
  netBuy: number;
  buyVolume: number;
  sellVolume: number;
  turnover: number;
}

export interface InstitutionTypeData {
  type: string;
  netBuy: number;
  buyVolume: number;
  sellVolume: number;
  concentration: number;
  trend: 'up' | 'down' | 'stable';
}

export interface MaturityDistribution {
  maturity: string;
  netBuy: number;
  buyVolume: number;
  sellVolume: number;
}

export interface HeatmapData {
  maturity: string;
  industry: string;
  value: number;
}

export interface TopBond {
  bondCode: string;
  bondName: string;
  netBuy: number;
  price: number;
  yield: number;
  rating: string;
}

export interface TopInstitution {
  institutionName: string;
  institutionType: string;
  netBuy: number;
  buyVolume: number;
  sellVolume: number;
  continuousDays: number;
}

export interface FilterOptions {
  institutionTypes: string[];
  industries: string[];
  maturities: string[];
  ratings: string[];
  dateRange: {
    start: string;
    end: string;
  };
}

export interface InstitutionalFlowData {
  overview: InstitutionalFlowOverview[];
  byInstitutionType: InstitutionTypeData[];
  byMaturity: MaturityDistribution[];
  heatmap: HeatmapData[];
  topBonds: TopBond[];
  topInstitutions: TopInstitution[];
}
