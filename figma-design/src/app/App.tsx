import React from 'react';
import { BarChart3, FileText, Calculator, Building2, Repeat2 } from 'lucide-react';
import { ModuleCard } from '@/app/components/ModuleCard';
import { InstitutionalFlowDashboard } from '@/app/components/InstitutionalFlowDashboard';
import { RepoDashboard } from '@/app/components/RepoDashboard';
import { ErrorBoundary } from '@/app/components/ErrorBoundary';
import { StrategyPage } from '@/pages/strategy/StrategyPage';
import { DailyReportPage } from '@/pages/daily-report/DailyReportPage';
import { ProfitEstimatorPage } from '@/pages/profitestimator/ProfitEstimatorPage';
import { MainLayout } from '@/layouts/MainLayout';
import { BrowserRouter, Routes, Route, useNavigate } from 'react-router-dom';

function Home() {
  const navigate = useNavigate();
  return (
    <MainLayout showSidebar={false}>
      <div className="mb-8">
        <h2 className="text-xl font-semibold text-foreground mb-2">功能模块</h2>
        <p className="text-sm text-muted-foreground">选择您需要访问的分析模块</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <ModuleCard
          title="策略回测分析"
          description="Strategy Backtest Dashboard"
          icon={BarChart3}
          status="active"
          stats={[
            { label: '活跃策略', value: '12' },
            { label: '今日回测', value: '3' },
          ]}
          onClick={() => navigate('/strategy')}
        />

        <ModuleCard
          title="市场日报"
          description="Daily Report"
          icon={FileText}
          status="existing"
          stats={[
            { label: '最新日报', value: new Date().toLocaleDateString('zh-CN') },
            { label: '异常提示', value: '2' },
          ]}
          onClick={() => navigate('/daily-report')}
        />

        <ModuleCard
          title="收益测算"
          description="Carry & Roll / Return Decomposition"
          icon={Calculator}
          status="existing"
          stats={[
            { label: '历史测算', value: '156' },
            { label: '常用债券', value: '8' },
          ]}
          onClick={() => navigate('/profitestimator')}
        />

        <ModuleCard
          title="机构行为-债券"
          description="Institutional Flow Analysis"
          icon={Building2}
          status="active"
          stats={[
            { label: '覆盖机构', value: '1,200+' },
            { label: '数据更新', value: 'T+1' },
          ]}
          onClick={() => navigate('/institutional-flow')}
        />

        <ModuleCard
          title="机构行为-货币"
          description="CFETS Repo Dashboard"
          icon={Repeat2}
          status="active"
          stats={[
            { label: '数据来源', value: 'CFETS' },
            { label: '更新频率', value: 'T+1' },
          ]}
          onClick={() => navigate('/repo')}
        />
      </div>

      <div className="mt-12 grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="bg-card border border-border rounded-lg p-6">
          <div className="text-sm text-muted-foreground mb-2">系统状态</div>
          <div className="flex items-center gap-2">
            <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
            <span className="text-foreground font-medium">所有服务正常</span>
          </div>
        </div>

        <div className="bg-card border border-border rounded-lg p-6">
          <div className="text-sm text-muted-foreground mb-2">数据更新频率</div>
          <div className="text-foreground font-medium">实时 / T+1</div>
        </div>

        <div className="bg-card border border-border rounded-lg p-6">
          <div className="text-sm text-muted-foreground mb-2">API 状态</div>
          <div className="text-foreground font-medium">连接正常</div>
        </div>
      </div>
    </MainLayout>
  );
}

export default function App() {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route 
            path="/strategy" 
            element={
              <MainLayout>
                <StrategyPage />
              </MainLayout>
            } 
          />
          <Route
            path="/daily-report"
            element={
              <MainLayout>
                <DailyReportPage />
              </MainLayout>
            }
          />
          <Route
            path="/reports/daily"
            element={
              <MainLayout>
                <DailyReportPage />
              </MainLayout>
            }
          />
          <Route
            path="/profitestimator"
            element={
              <MainLayout>
                <ProfitEstimatorPage />
              </MainLayout>
            }
          />
          <Route 
            path="/institutional-flow" 
            element={
              <MainLayout contentFullWidth>
                <InstitutionalFlowDashboard onBack={() => window.history.back()} />
              </MainLayout>
            } 
          />
          <Route
            path="/repo"
            element={
              <MainLayout contentFullWidth>
                <RepoDashboard onBack={() => window.history.back()} />
              </MainLayout>
            }
          />
        </Routes>
      </BrowserRouter>
    </ErrorBoundary>
  );
}
