# API接口文档 - 机构行为分析模块

## 概述
本文档定义了机构行为分析模块所需的API接口格式。

## 基础信息

**Base URL**: `${VITE_API_BASE_URL}` (从环境变量读取)

**通用请求头**:
```json
{
  "Content-Type": "application/json",
  "Authorization": "Bearer ${token}" // 如需要
}
```

---

## 1. 获取机构行为数据

### 接口地址
`POST /institutional-flow/overview`

### 请求参数

```typescript
{
  institutionTypes?: string[];      // 机构类型筛选，如 ["商业银行", "基金公司"]
  industries?: string[];            // 行业筛选，如 ["金融", "地产"]
  maturities?: string[];            // 期限筛选，如 ["0-1Y", "1-3Y"]
  ratings?: string[];               // 评级筛选，如 ["AAA", "AA+"]
  dateRange?: {
    start: string;                  // 开始日期 "YYYY-MM-DD"
    end: string;                    // 结束日期 "YYYY-MM-DD"
  }
}
```

### 响应数据结构

```typescript
{
  // 1. 时间序列概览数据（用于趋势图）
  overview: [
    {
      date: "2026-01-18",           // 日期
      netBuy: 1234.56,              // 净买入额（亿元）
      buyVolume: 8765.43,           // 买入总额（亿元）
      sellVolume: 7530.87,          // 卖出总额（亿元）
      turnover: 16296.30            // 成交额（亿元）
    },
    // ... 更多日期数据
  ],

  // 2. 按机构类型分布
  byInstitutionType: [
    {
      type: "商业银行",              // 机构类型
      netBuy: 2345.67,              // 净买入（亿元）
      buyVolume: 6789.01,           // 买入量（亿元）
      sellVolume: 4443.34,          // 卖出量（亿元）
      concentration: 0.23,          // 集中度 (0-1)
      trend: "up"                   // 趋势: "up" | "down" | "stable"
    },
    // ... 其他机构类型
  ],

  // 3. 按期限分布
  byMaturity: [
    {
      maturity: "0-1Y",             // 期限段
      netBuy: 1234.56,              // 净买入（亿元）
      buyVolume: 3456.78,           // 买入量（亿元）
      sellVolume: 2222.22           // 卖出量（亿元）
    },
    // ... 其他期限
  ],

  // 4. 热力图数据（期限 × 行业）
  heatmap: [
    {
      maturity: "0-1Y",             // 期限
      industry: "金融",              // 行业
      value: 234.56                 // 净买入值（亿元），可正可负
    },
    {
      maturity: "0-1Y",
      industry: "地产",
      value: -123.45
    },
    // ... 所有期限×行业组合
  ],

  // 5. Top债券排行
  topBonds: [
    {
      bondCode: "100001.IB",        // 债券代码
      bondName: "国开20",            // 债券名称
      netBuy: 567.89,               // 净买入（亿元）
      price: 98.56,                 // 价格
      yield: 2.85,                  // 收益率(%)
      rating: "AAA"                 // 评级
    },
    // ... Top 10
  ],

  // 6. Top机构排行
  topInstitutions: [
    {
      institutionName: "工商银行",   // 机构名称
      institutionType: "商业银行",   // 机构类型
      netBuy: 1234.56,              // 净买入（亿元）
      buyVolume: 3456.78,           // 买入量（亿元）
      sellVolume: 2222.22,          // 卖出量（亿元）
      continuousDays: 5             // 连续净买入天数
    },
    // ... Top 10
  ]
}
```

---

## 2. 获取筛选选项

### 接口地址
`GET /institutional-flow/filters`

### 响应数据

```typescript
{
  institutionTypes: [
    "商业银行",
    "基金公司",
    "证券公司",
    "保险公司",
    "理财公司",
    "其他"
  ],
  industries: [
    "金融",
    "地产",
    "城投",
    "工业",
    "公用事业",
    "消费"
  ],
  maturities: [
    "0-1Y",
    "1-3Y",
    "3-5Y",
    "5-7Y",
    "7-10Y",
    "10Y+"
  ],
  ratings: [
    "AAA",
    "AA+",
    "AA",
    "AA-",
    "A+",
    "A"
  ],
  dateRange: {
    start: "2025-10-20",            // 可查询的最早日期
    end: "2026-01-18"               // 可查询的最晚日期（通常是昨天或今天）
  }
}
```

---

## 数据要求

### 时间范围
- `overview`: 建议返回最近30-90天的数据
- 所有时间序列数据按日期升序排列

### 数值精度
- 金额单位：**亿元**
- 保留2位小数
- 收益率：百分比形式，如 2.85 表示 2.85%

### 热力图数据
- 必须包含所有期限×行业的组合
- 如果某个组合没有数据，value 设为 0

### 排行榜
- Top 10 即可
- 按净买入额降序排列

---

## 错误处理

### 错误响应格式

```typescript
{
  error: {
    code: "INVALID_PARAMS",        // 错误代码
    message: "无效的日期范围",      // 错误信息
    details?: any                  // 详细信息（可选）
  }
}
```

### 常见错误代码

| 错误代码 | HTTP状态码 | 说明 |
|---------|-----------|------|
| INVALID_PARAMS | 400 | 请求参数不合法 |
| UNAUTHORIZED | 401 | 未授权 |
| NOT_FOUND | 404 | 数据不存在 |
| INTERNAL_ERROR | 500 | 服务器内部错误 |

---

## 对接步骤

1. **配置环境变量**
   - 在项目根目录创建 `.env.local`
   - 设置 `VITE_API_BASE_URL=http://your-api-domain.com/api`

2. **修改API Service**
   - 打开 `/src/services/institutional-flow.ts`
   - 取消注释真实API调用代码
   - 注释或删除模拟数据生成代码

3. **测试接口**
   - 使用Postman或curl测试接口
   - 确保数据格式符合本文档定义

4. **错误处理**
   - 在 `fetchInstitutionalFlowData` 中添加具体的错误处理逻辑
   - 考虑添加重试机制

---

## 示例请求

### cURL示例

```bash
# 获取筛选选项
curl -X GET http://localhost:8000/api/institutional-flow/filters

# 获取机构行为数据
curl -X POST http://localhost:8000/api/institutional-flow/overview \
  -H "Content-Type: application/json" \
  -d '{
    "institutionTypes": ["商业银行", "基金公司"],
    "dateRange": {
      "start": "2026-01-01",
      "end": "2026-01-18"
    }
  }'
```

### JavaScript示例

```javascript
// 使用fetch调用
const response = await fetch('http://localhost:8000/api/institutional-flow/overview', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
  },
  body: JSON.stringify({
    institutionTypes: ['商业银行'],
    dateRange: {
      start: '2026-01-01',
      end: '2026-01-18',
    },
  }),
});

const data = await response.json();
console.log(data);
```

---

## 性能建议

1. **缓存策略**
   - 建议对筛选选项接口做客户端缓存（1小时）
   - 对数据接口可考虑缓存5-10分钟

2. **分页**
   - 如果数据量很大，考虑在 topBonds 和 topInstitutions 上实现分页

3. **增量更新**
   - 可增加一个接口只返回最新的增量数据
   - 例如：`GET /institutional-flow/latest` 只返回最新一天的数据

---

## 联系方式

如有接口相关问题，请联系：
- 前端开发：[您的联系方式]
- 后端开发：[后端联系方式]
