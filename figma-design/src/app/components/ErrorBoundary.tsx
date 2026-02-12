import React from 'react';

type Props = {
  children: React.ReactNode;
};

type State = {
  hasError: boolean;
  message?: string;
};

export class ErrorBoundary extends React.Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(error: any) {
    return { hasError: true, message: error?.message || String(error) };
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="min-h-screen bg-background text-foreground flex items-center justify-center p-6">
          <div className="max-w-xl w-full rounded-xl border border-border bg-card p-6">
            <div className="text-lg font-semibold">页面渲染失败</div>
            <div className="mt-2 text-sm text-muted-foreground break-words">{this.state.message || '未知错误'}</div>
            <button
              className="mt-4 inline-flex items-center justify-center rounded-md border border-border bg-background px-4 py-2 text-sm font-medium"
              onClick={() => window.location.reload()}
            >
              刷新页面
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}

