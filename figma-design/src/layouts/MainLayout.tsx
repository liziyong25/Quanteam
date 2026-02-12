import React, { useEffect, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { BarChart3, FileText, Calculator, Building2, LayoutDashboard, ChevronLeft, Menu, PanelLeftClose, Moon, Sun, Repeat2 } from 'lucide-react';
import { cn } from '@/lib/utils';
import { Button } from '@/app/components/ui/button';

interface MainLayoutProps {
  children: React.ReactNode;
  showSidebar?: boolean;
  contentFullWidth?: boolean;
  contentClassName?: string;
}

export function MainLayout({
  children,
  showSidebar = true,
  contentFullWidth = false,
  contentClassName,
}: MainLayoutProps) {
  const navigate = useNavigate();
  const location = useLocation();
  const isHome = location.pathname === '/';
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const [theme, setTheme] = useState<'light' | 'dark'>(() => {
    try {
      const saved = window.localStorage.getItem('theme');
      if (saved === 'light' || saved === 'dark') return saved;
      return window.matchMedia?.('(prefers-color-scheme: dark)')?.matches ? 'dark' : 'light';
    } catch {
      return 'dark';
    }
  });

  useEffect(() => {
    const root = document.documentElement;
    if (theme === 'dark') {
      root.classList.add('dark');
    } else {
      root.classList.remove('dark');
    }
    try {
      window.localStorage.setItem('theme', theme);
    } catch {}
  }, [theme]);

  const navItems = [
    { icon: LayoutDashboard, label: '首页', path: '/' },
    { icon: BarChart3, label: '策略回测', path: '/strategy' },
    { icon: FileText, label: '市场日报', path: '/daily-report' },
    { icon: Calculator, label: '收益测算', path: '/profitestimator' },
    { icon: Building2, label: '机构行为-债券', path: '/institutional-flow' },
    { icon: Repeat2, label: '机构行为-货币', path: '/repo' },
  ];

  return (
    <div className="min-h-screen bg-background text-foreground flex flex-col">
      {/* Header */}
      <header className="border-b border-border bg-card/50 backdrop-blur-sm sticky top-0 z-20 h-16">
        <div className="container mx-auto px-6 h-full flex items-center justify-between">
          <div className="flex items-center gap-4">
            {!isHome && (
              <div className="flex items-center gap-2">
                <Button 
                  variant="ghost" 
                  size="icon" 
                  onClick={() => setIsSidebarOpen(!isSidebarOpen)}
                  className="mr-2 hidden lg:flex"
                  title={isSidebarOpen ? "收起导航" : "展开导航"}
                >
                  {isSidebarOpen ? <PanelLeftClose className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
                </Button>
                <Button 
                  variant="ghost" 
                  size="icon" 
                  onClick={() => navigate('/')}
                  className="mr-2 lg:hidden"
                >
                  <ChevronLeft className="w-5 h-5" />
                </Button>
              </div>
            )}
            <div className="flex items-center gap-3 cursor-pointer" onClick={() => navigate('/')}>
              <div className="w-8 h-8 bg-gradient-to-br from-blue-500 to-blue-600 rounded-lg flex items-center justify-center">
                <span className="text-white font-bold">F</span>
              </div>
              <h1 className="text-xl font-bold hidden md:block">金融数据分析平台</h1>
            </div>
          </div>
          
          <div className="flex items-center gap-4">
            <div className="text-right hidden sm:block">
              <div className="text-xs text-muted-foreground">市场状态</div>
              <div className="flex items-center justify-end gap-2">
                <div className="w-2 h-2 bg-green-500 rounded-full animate-pulse"></div>
                <div className="text-xs font-medium text-green-400">开盘中</div>
              </div>
            </div>
            <div className="text-right hidden sm:block">
              <div className="text-xs text-muted-foreground">更新时间</div>
              <div className="text-xs font-medium">
                {new Date().toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })}
              </div>
            </div>
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setTheme((prev) => (prev === 'dark' ? 'light' : 'dark'))}
              title={theme === 'dark' ? '切换到日间模式' : '切换到夜间模式'}
            >
              {theme === 'dark' ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
            </Button>
          </div>
        </div>
      </header>

      <div
        className={cn(
          "flex flex-1 gap-6 relative",
          contentFullWidth ? "w-full px-6 py-6" : "container mx-auto px-4 py-6",
          contentClassName
        )}
      >
        {/* Sidebar - Only show on non-home pages if requested */}
        {showSidebar && !isHome && (
          <aside 
            className={cn(
              "hidden lg:block shrink-0 transition-all duration-300 overflow-hidden",
              isSidebarOpen ? "w-64" : "w-0 opacity-0"
            )}
          >
            <nav className="flex flex-col gap-2 sticky top-24 w-64">
              {navItems.map((item) => (
                <button
                  key={item.path}
                  onClick={() => navigate(item.path)}
                  className={cn(
                    "flex items-center gap-3 px-4 py-3 rounded-lg text-sm font-medium transition-colors",
                    location.pathname === item.path 
                      ? "bg-primary/10 text-primary" 
                      : "text-muted-foreground hover:bg-muted hover:text-foreground"
                  )}
                >
                  <item.icon className="w-5 h-5" />
                  {item.label}
                </button>
              ))}
            </nav>
          </aside>
        )}

        {/* Main Content */}
        <main className="flex-1 min-w-0">
          {children}
        </main>
      </div>

      {/* Footer */}
      <footer className="border-t border-border mt-auto">
        <div className="container mx-auto px-6 py-6">
          <div className="text-center text-sm text-muted-foreground">
            <p>金融数据分析平台 © {new Date().getFullYear()}</p>
          </div>
        </div>
      </footer>
    </div>
  );
}
