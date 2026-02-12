import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Plot from 'react-plotly.js';
import { RefreshCw } from 'lucide-react';

import { Button } from '@/app/components/ui/button';
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from '@/app/components/ui/card';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/app/components/ui/dialog';
import { Input } from '@/app/components/ui/input';
import { repoApi, type RepoMode, type RepoPanelResponse, type RepoPivotResponse, type RepoSide } from '@/lib/api/repo';
import { cn } from '@/lib/utils';

interface RepoDashboardProps {
  onBack: () => void;
}

type PivotSelection = {
  industry: string;
  side: Exclude<RepoSide, 'both'>;
};

type PlotlyFigure = {
  data: Array<Record<string, unknown>>;
  layout: Record<string, unknown>;
};

const PANEL_SIZE_KEY = 'repo:panelModalSize:v1';

const DEFAULT_START = '2024-01-01';

const REPO_MODES: Array<{ key: RepoMode; label: string }> = [
  { key: 'buyback', label: '质押式' },
  { key: 'buyout', label: '买断式' },
  { key: 'credit', label: '拆借' },
  { key: 'sum', label: '总和' },
];

function formatCell(value: number | null | undefined) {
  if (value === null || value === undefined) return '-';
  if (!Number.isFinite(value)) return '-';
  return String(Math.round(value));
}

function formatRate(value: number | null | undefined) {
  if (value === null || value === undefined) return '-';
  if (!Number.isFinite(value)) return '-';
  return value.toFixed(2);
}

function readPanelSize(): { w: number; h: number } | null {
  try {
    const raw = localStorage.getItem(PANEL_SIZE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as { w?: number; h?: number };
    if (!parsed?.w || !parsed?.h) return null;
    return { w: parsed.w, h: parsed.h };
  } catch {
    return null;
  }
}

function writePanelSize(size: { w: number; h: number }) {
  try {
    localStorage.setItem(PANEL_SIZE_KEY, JSON.stringify(size));
  } catch {
    // ignore
  }
}

function buildPanelFigure(panel: RepoPanelResponse, col: string): PlotlyFigure {
  const dates = panel.dates;
  const remaining = panel.remaining?.[col] ?? [];
  const rate = panel.rate?.[col] ?? [];
  return {
    data: [
      {
        x: dates,
        y: remaining,
        type: 'scatter',
        mode: 'lines',
        name: 'remaining',
        line: { color: 'hsl(var(--primary))', width: 2 },
        hovertemplate: '%{x}<br>remaining=%{y:.2f}<extra></extra>',
      },
      {
        x: dates,
        y: rate,
        type: 'scatter',
        mode: 'lines',
        name: 'rate',
        yaxis: 'y2',
        line: { color: 'hsl(var(--muted-foreground))', width: 2, dash: 'dot' },
        hovertemplate: '%{x}<br>rate=%{y:.2f}<extra></extra>',
      },
    ],
    layout: {
      margin: { l: 42, r: 42, t: 10, b: 30 },
      paper_bgcolor: 'rgba(0,0,0,0)',
      plot_bgcolor: 'rgba(0,0,0,0)',
      xaxis: { type: 'date', tickfont: { size: 10 } },
      yaxis: { tickfont: { size: 10 }, zeroline: false },
      yaxis2: { overlaying: 'y', side: 'right', tickfont: { size: 10 }, zeroline: false },
      showlegend: false,
    },
  };
}

export function RepoDashboard({ onBack }: RepoDashboardProps) {
  const [start, setStart] = useState(DEFAULT_START);
  const [end, setEnd] = useState('');
  const [tradeDate, setTradeDate] = useState('');
  const [repoMode, setRepoMode] = useState<RepoMode>('buyback');

  const [pivot, setPivot] = useState<RepoPivotResponse | null>(null);
  const [pivotLoading, setPivotLoading] = useState(false);
  const [pivotError, setPivotError] = useState<string | null>(null);

  const [selection, setSelection] = useState<PivotSelection | null>(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [panel, setPanel] = useState<RepoPanelResponse | null>(null);
  const [panelLoading, setPanelLoading] = useState(false);
  const [panelError, setPanelError] = useState<string | null>(null);

  const [panelSize, setPanelSize] = useState<{ w: number; h: number } | null>(() => readPanelSize() ?? { w: 1200, h: 675 });
  const resizeRef = useRef<{ startX: number; startY: number; startW: number; startH: number } | null>(null);

  useEffect(() => {
    function onMove(e: PointerEvent) {
      if (!resizeRef.current || !panelSize) return;
      const dx = e.clientX - resizeRef.current.startX;
      const dy = e.clientY - resizeRef.current.startY;
      const w = Math.max(720, resizeRef.current.startW + dx);
      const h = Math.max(405, resizeRef.current.startH + dy);
      const next = { w, h };
      setPanelSize(next);
      writePanelSize(next);
    }
    function onUp() {
      resizeRef.current = null;
    }
    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerup', onUp);
    return () => {
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerup', onUp);
    };
  }, [panelSize]);

  const effectiveEnd = end || pivot?.meta?.end || '';
  const effectiveTradeDate = tradeDate || pivot?.meta?.trade_date || '';

  const requestPivot = useCallback(async () => {
    setPivotLoading(true);
    setPivotError(null);
    try {
      const res = await repoApi.getPivot({
        start,
        end: end || undefined,
        tradeDate: tradeDate || undefined,
        repoMode,
      });
      setPivot(res);
      if (!end) setEnd(res.meta.end);
      if (!tradeDate) setTradeDate(res.meta.trade_date);
    } catch (err: any) {
      setPivotError(err?.message || String(err));
    } finally {
      setPivotLoading(false);
    }
  }, [start, end, tradeDate, repoMode]);

  const requestPanel = useCallback(async () => {
    if (!selection) return;
    setPanelLoading(true);
    setPanelError(null);
    try {
      const res = await repoApi.getPanel({
        industry: selection.industry,
        side: selection.side,
        start,
        end: effectiveEnd || undefined,
        repoMode,
      });
      setPanel(res);
    } catch (err: any) {
      setPanelError(err?.message || String(err));
    } finally {
      setPanelLoading(false);
    }
  }, [selection, start, effectiveEnd, repoMode]);

  useEffect(() => {
    requestPivot();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    requestPivot();
  }, [repoMode, requestPivot]);

  useEffect(() => {
    if (!modalOpen) {
      setPanel(null);
      setPanelError(null);
      setPanelLoading(false);
      return;
    }
    requestPanel();
  }, [modalOpen, requestPanel]);

  useEffect(() => {
    if (!modalOpen) return;
    requestPanel();
  }, [repoMode, modalOpen, requestPanel]);

  const industries = pivot?.industries ?? [];
  const ageOrder = pivot?.age_order ?? [];
  const rows = pivot?.rows ?? [];
  const rowsByAge = useMemo(() => {
    const mapping: Record<string, RepoPivotResponse['rows'][number]> = {};
    rows.forEach((row) => {
      mapping[String(row.new_age)] = row;
    });
    return mapping;
  }, [rows]);

  const panelCols = useMemo(() => {
    const cols = panel?.columns ?? [];
    return cols.slice(0, 5);
  }, [panel]);

  const renderTable = (tableSide: Exclude<RepoSide, 'both'>, title: string) => {
    return (
      <div className="mt-4">
        <div className="mb-2 text-sm font-semibold text-foreground">{title}</div>
        <div className="overflow-auto rounded-lg border border-border/60 bg-card/40">
          <table className="w-full table-fixed border-collapse text-sm">
            <thead className="sticky top-0 z-10 bg-card/90 text-xs text-muted-foreground backdrop-blur">
              <tr>
                <th className="w-[120px] border border-border/50 px-2 py-2 text-left">期限</th>
                {industries.map((ind) => (
                  <th key={ind} className="min-w-[140px] border border-border/50 px-2 py-2 text-left">
                    {ind}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {ageOrder.map((age) => {
                const row = rowsByAge[age];
                return (
                  <tr key={age} className="hover:bg-accent/10">
                    <td className="border border-border/50 px-2 py-2 font-medium text-foreground">{age}</td>
                    {industries.map((ind) => {
                      const cell = tableSide === 'repo' ? row?.repo?.[ind] : row?.rev_repo?.[ind];
                      const amount = cell?.amount ?? null;
                      const rate = cell?.rate ?? null;
                      return (
                        <td
                          key={`${age}-${ind}-${tableSide}`}
                          className={cn(
                            'border border-border/50 px-2 py-2 align-top text-foreground cursor-pointer',
                            'hover:bg-accent/20'
                          )}
                          onClick={() => {
                            setSelection({ industry: ind, side: tableSide });
                            setModalOpen(true);
                          }}
                        >
                          <div className="font-semibold">{formatCell(amount)}</div>
                          <div className="text-xs text-muted-foreground">{formatRate(rate)}</div>
                        </td>
                      );
                    })}
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-6">
      <Card className="w-full">
        <CardHeader>
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <CardTitle>机构行为-货币</CardTitle>
              <CardDescription>CFETS Repo Dashboard</CardDescription>
            </div>
            <CardAction className="flex items-center gap-2">
              <Button variant="outline" size="sm" onClick={onBack}>
                返回
              </Button>
              <Button variant="outline" size="sm" disabled={pivotLoading} onClick={requestPivot}>
                <RefreshCw className={cn('mr-2 size-4', pivotLoading ? 'animate-spin' : '')} />
                刷新
              </Button>
            </CardAction>
          </div>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 gap-4 lg:grid-cols-5">
            <div className="lg:col-span-2">
              <div className="text-xs text-muted-foreground mb-1">Start</div>
              <Input type="date" value={start} onChange={(e) => setStart(e.target.value)} />
            </div>
            <div className="lg:col-span-2">
              <div className="text-xs text-muted-foreground mb-1">End</div>
              <Input type="date" value={effectiveEnd} onChange={(e) => setEnd(e.target.value)} />
            </div>
            <div>
              <div className="text-xs text-muted-foreground mb-1">Trade Date</div>
              <Input type="date" value={effectiveTradeDate} onChange={(e) => setTradeDate(e.target.value)} />
            </div>
          </div>

          <div className="mt-4 flex flex-wrap items-center gap-2">
            {REPO_MODES.map((mode) => (
              <Button
                key={mode.key}
                variant={repoMode === mode.key ? 'default' : 'outline'}
                size="sm"
                onClick={() => setRepoMode(mode.key)}
              >
                {mode.label}
              </Button>
            ))}
          </div>

          {pivotError ? (
            <div className="mt-4 rounded-md border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">{pivotError}</div>
          ) : null}

          {!pivotLoading && pivot ? (
            <div className="mt-4 text-xs text-muted-foreground">
              数据区间：{pivot.meta.start} ~ {pivot.meta.end} · 单日：{pivot.meta.trade_date}
            </div>
          ) : null}

          {pivotLoading ? (
            <div className="mt-6 flex h-[240px] items-center justify-center text-sm text-muted-foreground">加载中...</div>
          ) : pivot ? (
            <div>
              {renderTable('repo', '正回购')}
              {renderTable('rev_repo', '逆回购')}
            </div>
          ) : (
            <div className="mt-6 flex h-[240px] items-center justify-center text-sm text-muted-foreground">暂无数据</div>
          )}
        </CardContent>
      </Card>

      <Dialog open={modalOpen} onOpenChange={setModalOpen}>
        <DialogContent
          className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 p-0 flex flex-col overflow-hidden"
          style={
            panelSize
              ? {
                  width: panelSize.w,
                  height: panelSize.h,
                  maxWidth: '96vw',
                  maxHeight: '92vh',
                }
              : undefined
          }
        >
          <DialogHeader className="px-6 pt-6">
            <DialogTitle>Repo 面板（弹窗）</DialogTitle>
            {selection ? (
              <div className="text-xs text-muted-foreground">
                {selection.industry} · {selection.side} · {start}~{effectiveEnd}
              </div>
            ) : null}
          </DialogHeader>

          <div className="flex-1 min-h-0 px-6 pb-6 overflow-auto">
            <div className="mt-2 flex items-center justify-end">
              <Button variant="outline" size="sm" disabled={!selection || panelLoading} onClick={requestPanel}>
                刷新
              </Button>
            </div>

            {panelError ? (
              <div className="mt-4 rounded-md border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">{panelError}</div>
            ) : null}

            <div className="mt-4">
              {panelLoading ? (
                <div className="flex h-[320px] items-center justify-center text-sm text-muted-foreground">加载面板中...</div>
              ) : panel && panelCols.length ? (
                <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
                  {panelCols.map((col) => {
                    const fig = buildPanelFigure(panel, col);
                    return (
                      <div key={col} className="rounded-md border border-border/60 bg-card/30 p-3">
                        <div className="text-xs font-semibold text-foreground mb-2">{col}</div>
                        <div className="h-[220px]">
                          <Plot
                            data={fig.data as any[]}
                            layout={{ ...fig.layout, autosize: true }}
                            useResizeHandler
                            style={{ width: '100%', height: '100%' }}
                            config={{ displayModeBar: false, responsive: true }}
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
              ) : (
                <div className="flex h-[320px] items-center justify-center text-sm text-muted-foreground">暂无面板数据</div>
              )}
            </div>
          </div>

          <div
            className="absolute bottom-2 right-2 size-4 cursor-se-resize rounded-sm border border-border bg-background/70"
            onPointerDown={(e) => {
              if (!panelSize) return;
              e.preventDefault();
              resizeRef.current = {
                startX: e.clientX,
                startY: e.clientY,
                startW: panelSize.w,
                startH: panelSize.h,
              };
            }}
          />
        </DialogContent>
      </Dialog>
    </div>
  );
}
