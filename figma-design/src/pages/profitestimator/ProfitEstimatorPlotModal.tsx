import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import Plot from 'react-plotly.js';

import { Button } from '@/app/components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/app/components/ui/dialog';
import { cn } from '@/lib/utils';
import { profitEstimatorApi, ProfitEstimatorPlotResponse } from '@/lib/api/profitestimator';

export type ProfitEstimatorQuery = {
  tradeDate: string;
  bondType: string;
  holdingDays: number;
  ageLimitMin?: number;
  ageLimitMax?: number;
};

export type ProfitEstimatorMetaItem = {
  label: string;
  value: string;
};

const PLOT_MODAL_SIZE_KEY = 'profitestimator:plotModalSize:v1';

export function ProfitEstimatorPlotModal({
  open,
  onOpenChange,
  symbol,
  query,
  meta,
}: {
  open: boolean;
  onOpenChange: (next: boolean) => void;
  symbol: string | null;
  query: ProfitEstimatorQuery | null;
  meta?: ProfitEstimatorMetaItem[];
}) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [plotly, setPlotly] = useState<ProfitEstimatorPlotResponse['plotly']>(null);
  const abortRef = useRef<AbortController | null>(null);
  const [size, setSize] = useState<{ w: number; h: number } | null>(null);
  const resizeRef = useRef<{
    startX: number;
    startY: number;
    startW: number;
    startH: number;
  } | null>(null);

  useEffect(() => {
    if (!open) return;
    setError(null);
    setPlotly(null);
    try {
      const raw = localStorage.getItem(PLOT_MODAL_SIZE_KEY);
      if (raw) {
        const parsed = JSON.parse(raw);
        const w = Number(parsed?.w);
        const h = Number(parsed?.h);
        if (Number.isFinite(w) && Number.isFinite(h) && w > 300 && h > 200) {
          setSize({ w, h });
        } else {
          setSize(null);
        }
      } else {
        setSize(null);
      }
    } catch {
      setSize(null);
    }
  }, [open, symbol]);

  useEffect(() => {
    if (!open) return;
    if (size) return;
    const vw = Math.floor(window.innerWidth * 0.96);
    const vh = Math.floor(window.innerHeight * 0.92);
    const maxW = Math.min(vw, 1770);
    let w = maxW;
    let h = Math.floor((w * 9) / 16);
    if (h > vh) {
      h = vh;
      w = Math.floor((h * 16) / 9);
    }
    setSize({ w, h });
  }, [open, size]);

  useEffect(() => {
    if (!open) return;
    const onMove = (e: PointerEvent) => {
      const snap = resizeRef.current;
      if (!snap) return;
      const dx = e.clientX - snap.startX;
      const dy = e.clientY - snap.startY;
      const intent = Math.max(dx, dy);

      const vw = window.innerWidth * 0.96;
      const vh = window.innerHeight * 0.92;
      const minW = 640;
      const maxW = Math.min(vw, 2400);

      let nextW = snap.startW + intent;
      nextW = Math.max(minW, Math.min(maxW, nextW));
      let nextH = (nextW * 9) / 16;

      if (nextH > vh) {
        nextH = vh;
        nextW = (nextH * 16) / 9;
      }

      setSize({ w: Math.round(nextW), h: Math.round(nextH) });
    };

    const onUp = () => {
      if (!resizeRef.current) return;
      resizeRef.current = null;
      setSize((cur) => {
        if (cur) {
          try {
            localStorage.setItem(PLOT_MODAL_SIZE_KEY, JSON.stringify(cur));
          } catch {
            return cur;
          }
        }
        return cur;
      });
    };

    window.addEventListener('pointermove', onMove);
    window.addEventListener('pointerup', onUp);
    return () => {
      window.removeEventListener('pointermove', onMove);
      window.removeEventListener('pointerup', onUp);
    };
  }, [open]);

  const requestPlot = useCallback(
    async () => {
      if (!query || !symbol) return;
      abortRef.current?.abort();
      const controller = new AbortController();
      abortRef.current = controller;
      setLoading(true);
      setError(null);
      try {
        const res = await profitEstimatorApi.plot(
          {
            trade_date: query.tradeDate,
            bond_type: query.bondType,
            holding_days: query.holdingDays,
            age_limit_min: query.ageLimitMin,
            age_limit_max: query.ageLimitMax,
            symbol,
          },
          { signal: controller.signal }
        );
        if (!controller.signal.aborted) {
          setPlotly(res.plotly ?? null);
        }
      } catch (e: any) {
        if (!controller.signal.aborted) {
          setError(e?.response?.data?.detail || e?.message || '加载失败');
        }
      } finally {
        if (!controller.signal.aborted) {
          setLoading(false);
        }
      }
    },
    [query, symbol]
  );

  useEffect(() => {
    if (!open) return;
    if (!symbol || !query) return;
    requestPlot();
  }, [open, symbol, query, requestPlot]);

  const title = useMemo(() => (symbol ? `收益测算图 - ${symbol}` : '收益测算图'), [symbol]);

  const plotLayout = useMemo(() => {
    if (!plotly?.layout) return null;
    const { width, height, ...layoutBase } = plotly.layout as Record<string, unknown>;
    return { ...layoutBase, autosize: true };
  }, [plotly]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className="fixed left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 p-0 flex flex-col overflow-hidden"
        style={
          size
            ? {
                width: size.w,
                height: size.h,
                maxWidth: '96vw',
                maxHeight: '92vh',
              }
            : undefined
        }
      >
        <DialogHeader className="px-6 pt-6">
          <DialogTitle>{title}</DialogTitle>
          {meta && meta.length > 0 ? (
            <div className="mt-3 rounded-md border border-border/50 bg-card/40 px-4 py-3">
              <div className="grid grid-cols-4 grid-rows-2 gap-x-6 gap-y-2 text-xs text-muted-foreground">
                {meta.map((item) => (
                  <div key={item.label}>
                    <span className="mr-2 text-foreground">{item.label}</span>
                    <span>{item.value || '-'}</span>
                  </div>
                ))}
              </div>
            </div>
          ) : null}
        </DialogHeader>

        <div className="flex-1 min-h-0 px-6 pb-6 overflow-auto">
          <div className="mt-2 flex items-center justify-end">
            <Button variant="outline" size="sm" disabled={!symbol || loading} onClick={requestPlot}>
              刷新
            </Button>
          </div>

          {error ? <div className="mt-4 rounded-md border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">{error}</div> : null}

          <div className={cn('mt-4 flex h-full flex-col gap-3', loading ? 'opacity-70' : '')}>
            <div className="flex-1 min-h-0 rounded-md border border-border/60 bg-card/30">
              {loading ? (
                <div className="flex h-full min-h-[320px] items-center justify-center text-sm text-muted-foreground">加载中…</div>
              ) : plotly && plotly.data && plotLayout ? (
                <div className="h-full w-full min-h-[320px]">
                  <Plot
                    data={plotly.data as any[]}
                    layout={plotLayout}
                    frames={plotly.frames as any}
                    useResizeHandler
                    style={{ width: '100%', height: '100%' }}
                    config={{ displayModeBar: 'hover', responsive: true }}
                  />
                </div>
              ) : (
                <div className="flex h-full min-h-[320px] items-center justify-center text-sm text-muted-foreground">暂无图表数据</div>
              )}
            </div>
          </div>
        </div>

        <div
          className="absolute bottom-2 right-2 size-4 cursor-se-resize rounded-sm border border-border bg-background/70"
          onPointerDown={(e) => {
            if (!size) return;
            e.preventDefault();
            resizeRef.current = {
              startX: e.clientX,
              startY: e.clientY,
              startW: size.w,
              startH: size.h,
            };
          }}
        />
      </DialogContent>
    </Dialog>
  );
}
