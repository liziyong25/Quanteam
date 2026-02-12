# 金融数据分析平台 - 机构行为分析模块

## 项目概述

这是一个专业的金融数据分析平台，目前已实现**机构行为分析**模块。采用深色专业主题（类似Bloomberg），支持响应式设计。

## 已实现功能

### 机构行为分析模块 ✅
- **总览仪表盘**：关键指标卡片、净买入趋势图
- **多维度分析**：
  - 按机构类型分布（柱状图）
  - 按期限分布（柱状图）
  - 期限×行业热力图
- **排行榜**：
  - Top 10 净买入债券
  - Top 10 净买入机构
- **交互功能**：
  - 图表缩放、拖拽
  - 数据点悬停显示详情
  - 热力图悬停提示

### 其他模块（已有）
- 策略回测分析（显示为"已有模块"）
- 市场日报（显示为"已有模块"）
- 收益测算（显示为"已有模块"）

## API对接说明

### 当前状态
目前使用**模拟数据**进行展示，所有API调用逻辑已在 `/src/services/institutional-flow.ts` 中准备好。

### 对接真实API的步骤

#### 1. 配置API地址
创建 `.env.local` 文件（参考 `.env.example`）：

```bash
VITE_API_BASE_URL=http://your-api-domain.com/api
```

#### 2. 修改API Service
打开 `/src/services/institutional-flow.ts`，取消注释真实API调用代码：

```typescript
export async function fetchInstitutionalFlowData(
  filters?: Partial<FilterOptions>
): Promise<InstitutionalFlowData> {
  try {
    // 取消注释以下代码：
    const response = await fetch(`${API_BASE_URL}/institutional-flow/overview`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(filters),
    });
    return await response.json();

    // 删除或注释掉模拟数据代码
    // await new Promise(resolve => setTimeout(resolve, 500));
    // return generateMockData(filters);
  } catch (error) {
    console.error('Failed to fetch institutional flow data:', error);
    throw error;
  }
}
```

#### 3. API接口定义

您的后端需要提供以下接口：

**GET/POST `/institutional-flow/overview`**
- 请求参数：FilterOptions（可选）
- 返回数据：InstitutionalFlowData

数据结构参考 `/src/types/institutional-flow.ts`

**示例响应：**

```json
{
  "overview": [
    {
      "date": "2026-01-18",
      "netBuy": 1234.56,
      "buyVolume": 8765.43,
      "sellVolume": 7530.87,
      "turnover": 16296.30
    }
  ],
  "byInstitutionType": [
    {
      "type": "商业银行",
      "netBuy": 2345.67,
      "buyVolume": 6789.01,
      "sellVolume": 4443.34,
      "concentration": 0.23,
      "trend": "up"
    }
  ],
  "byMaturity": [...],
  "heatmap": [...],
  "topBonds": [...],
  "topInstitutions": [...]
}
```

**GET `/institutional-flow/filters`**
- 返回筛选选项（机构类型、行业、期限、评级等）

## 技术栈

- **框架**：React 18 + TypeScript
- **构建工具**：Vite
- **样式**：Tailwind CSS v4（深色主题）
- **图表库**：Recharts
- **图标**：Lucide React
- **状态管理**：React Hooks

## 本地开发

```bash
# 安装依赖
npm install

# 启动开发服务器
npm run dev

# 构建生产版本
npm run build
```

## 文件结构

```
/src
  /app
    /components
      - InstitutionalFlowDashboard.tsx  # 机构行为分析主页面
      - ModuleCard.tsx                   # 首页模块卡片
      - StatCard.tsx                     # 统计卡片组件
      - Heatmap.tsx                      # 热力图组件
    - App.tsx                            # 主入口
  /services
    - institutional-flow.ts              # API服务层 ⭐
  /types
    - institutional-flow.ts              # 数据类型定义 ⭐
  /styles
    - theme.css                          # 主题配置（深色模式）
```

⭐ 标记的文件是对接API时需要修改的核心文件

## 设计特点

- **Bloomberg风格**：专业深色主题，适合金融专业人士
- **响应式布局**：支持桌面、平板、手机
- **交互丰富**：图表支持缩放、悬停、图例切换
- **视觉清晰**：使用绿色（买入/涨）、红色（卖出/跌）、蓝色（中性）的配色方案

## 下一步开发建议

1. **筛选功能**：实现顶部筛选按钮的功能面板
2. **导出功能**：实现数据导出为Excel/PDF
3. **钻取详情**：点击表格行跳转到详情页
4. **实时更新**：WebSocket或轮询自动更新数据
5. **用户权限**：根据用户角色显示不同数据

## 联系方式

如有问题，请联系开发团队。
