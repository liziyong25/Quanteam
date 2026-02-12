import type {
  InstitutionalFlowData,
  FilterOptions,
} from '@/types/institutional-flow';

// API Base URL - 后续替换为真实API地址
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api';

// 模拟数据生成函数
function generateMockData(filters?: Partial<FilterOptions>): InstitutionalFlowData {
  // 时间序列数据（最近30天）
  const overview = Array.from({ length: 30 }, (_, i) => {
    const date = new Date();
    date.setDate(date.getDate() - (29 - i));
    return {
      date: date.toISOString().split('T')[0],
      netBuy: (Math.random() - 0.5) * 5000 + 1000,
      buyVolume: Math.random() * 10000 + 5000,
      sellVolume: Math.random() * 8000 + 4000,
      turnover: Math.random() * 15000 + 10000,
    };
  });

  // 按机构类型
  const institutionTypes = ['商业银行', '基金公司', '证券公司', '保险公司', '理财公司', '其他'];
  const byInstitutionType = institutionTypes.map(type => ({
    type,
    netBuy: (Math.random() - 0.5) * 3000,
    buyVolume: Math.random() * 8000 + 2000,
    sellVolume: Math.random() * 7000 + 2000,
    concentration: Math.random() * 0.3 + 0.1,
    trend: ['up', 'down', 'stable'][Math.floor(Math.random() * 3)] as 'up' | 'down' | 'stable',
  }));

  // 按期限分布
  const maturities = ['0-1Y', '1-3Y', '3-5Y', '5-7Y', '7-10Y', '10Y+'];
  const byMaturity = maturities.map(maturity => ({
    maturity,
    netBuy: (Math.random() - 0.5) * 2000,
    buyVolume: Math.random() * 5000 + 1000,
    sellVolume: Math.random() * 4500 + 1000,
  }));

  // 热力图数据（期限 × 行业）
  const industries = ['金融', '地产', '城投', '工业', '公用事业', '消费'];
  const heatmap = maturities.flatMap(maturity =>
    industries.map(industry => ({
      maturity,
      industry,
      value: (Math.random() - 0.5) * 1000,
    }))
  );

  // Top债券
  const topBonds = Array.from({ length: 10 }, (_, i) => ({
    bondCode: `${(100000 + i).toString()}.IB`,
    bondName: `${['国开', '进出口', '农发', '国债', '地方债'][Math.floor(Math.random() * 5)]}${(20 + i).toString()}`,
    netBuy: Math.random() * 1000 + 500,
    price: 98 + Math.random() * 4,
    yield: 2.5 + Math.random() * 1.5,
    rating: ['AAA', 'AA+', 'AA', 'AA-'][Math.floor(Math.random() * 4)],
  })).sort((a, b) => b.netBuy - a.netBuy);

  // Top机构
  const topInstitutions = Array.from({ length: 10 }, (_, i) => ({
    institutionName: `${['工商银行', '建设银行', '农业银行', '中国银行', '交通银行', '招商银行', '浦发银行', '中信银行', '光大银行', '民生银行'][i]}`,
    institutionType: institutionTypes[Math.floor(Math.random() * institutionTypes.length)],
    netBuy: Math.random() * 2000 + 1000,
    buyVolume: Math.random() * 5000 + 2000,
    sellVolume: Math.random() * 4000 + 1000,
    continuousDays: Math.floor(Math.random() * 10) + 1,
  })).sort((a, b) => b.netBuy - a.netBuy);

  return {
    overview,
    byInstitutionType,
    byMaturity,
    heatmap,
    topBonds,
    topInstitutions,
  };
}

// API函数
export async function fetchInstitutionalFlowData(
  filters?: Partial<FilterOptions>
): Promise<InstitutionalFlowData> {
  try {
    // TODO: 替换为真实API调用
    // const response = await fetch(`${API_BASE_URL}/institutional-flow/overview`, {
    //   method: 'POST',
    //   headers: { 'Content-Type': 'application/json' },
    //   body: JSON.stringify(filters),
    // });
    // return await response.json();

    // 模拟API延迟
    await new Promise(resolve => setTimeout(resolve, 500));
    return generateMockData(filters);
  } catch (error) {
    console.error('Failed to fetch institutional flow data:', error);
    throw error;
  }
}

export async function fetchFilterOptions(): Promise<FilterOptions> {
  try {
    // TODO: 替换为真实API调用
    // const response = await fetch(`${API_BASE_URL}/institutional-flow/filters`);
    // return await response.json();

    await new Promise(resolve => setTimeout(resolve, 200));
    return {
      institutionTypes: ['商业银行', '基金公司', '证券公司', '保险公司', '理财公司', '其他'],
      industries: ['金融', '地产', '城投', '工业', '公用事业', '消费'],
      maturities: ['0-1Y', '1-3Y', '3-5Y', '5-7Y', '7-10Y', '10Y+'],
      ratings: ['AAA', 'AA+', 'AA', 'AA-', 'A+', 'A'],
      dateRange: {
        start: new Date(Date.now() - 90 * 24 * 60 * 60 * 1000).toISOString().split('T')[0],
        end: new Date().toISOString().split('T')[0],
      },
    };
  } catch (error) {
    console.error('Failed to fetch filter options:', error);
    throw error;
  }
}
