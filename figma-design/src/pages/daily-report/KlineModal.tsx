import React, { useEffect, useMemo, useRef, useState } from 'react';

import { Button } from '@/app/components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/app/components/ui/dialog';
import { cn } from '@/lib/utils';
import { dailyApi, KlineResponse } from '@/lib/api/daily';
import { KlineChartCard } from './KlineCharts';

type KlinePanel = 'broker_yield' | 'broker_price' | 'settlement_yield' | 'settlement_price';

const KLINE_MODAL_SIZE_KEY = 'daily:klineModalSize:v1';

function formatDate(d: Date) {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

function addMonths(value: string, deltaMonths: number) {
  const d = new Date(`${value}T00:00:00`);
  if (Number.isNaN(d.getTime())) return value;
  d.setMonth(d.getMonth() + deltaMonths);
  return formatDate(d);
}

export function KlineModal({
  open,
  onOpenChange,
  symbol,
  endDate,
  meta,
}: {
  open: boolean;
  onOpenChange: (next: boolean) => void;
  symbol: string | null;
  endDate: string | null;
  meta?: {
    short_name?: string | null;
    age_limit?: number | string | null;
    close_yield?: number | string | null;
    zz_val?: number | string | null;
    pct_ytm?: number | string | null;
    bias_bp?: number | string | null;
    delist_date?: string | null;
    actual_yield?: number | string | null;
  };
}) {
  const defaultEnd = endDate || formatDate(new Date());
  const [start, setStart] = useState(addMonths(defaultEnd, -3));
  const [end, setEnd] = useState(defaultEnd);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fullData, setFullData] = useState<KlineResponse | null>(null);
  const [viewData, setViewData] = useState<KlineResponse | null>(null);
  const [panel, setPanel] = useState<KlinePanel>('broker_yield');
  const abortRef = useRef<AbortController | null>(null);
  const extraAbortRef = useRef<AbortController | null>(null);
  const [size, setSize] = useState<{ w: number; h: number } | null>(null);
  const resizeRef = useRef<{
    startX: number;
    startY: number;
    startW: number;
    startH: number;
  } | null>(null);

  const canQuery = Boolean(symbol && start && end);

  useEffect(() => {
    if (!open) return;
    const nextEnd = endDate || formatDate(new Date());
    const nextStart = addMonths(nextEnd, -3);
    setEnd(nextEnd);
    setStart(nextStart);
    setPanel('broker_yield');
    setError(null);
    setFullData(null);
    setViewData(null);
    try {
      const raw = localStorage.getItem(KLINE_MODAL_SIZE_KEY);
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
    if (symbol) {
      requestBroker('2000-01-01', nextEnd);
    }
  }, [open, endDate, symbol]);

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
            localStorage.setItem(KLINE_MODAL_SIZE_KEY, JSON.stringify(cur));
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

  const requestBroker = async (nextStart: string, nextEnd: string) => {
    if (!symbol) return;
    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;
    setLoading(true);
    setError(null);
    try {
      const res = await dailyApi.postKline(
        { symbol, start: nextStart, end: nextEnd, include_broker: true, include_settlement: false, include_valuation: false },
        { signal: controller.signal },
      );
      if (!controller.signal.aborted) {
        setFullData(res);
        setPanel('broker_yield');
        requestExtras(nextStart, nextEnd);
      }
    } catch (e: any) {
      if (!controller.signal.aborted) {
        setError(e?.response?.data?.detail || e?.message || '加载失败');
      }
    } finally {
      setLoading(false);
    }
  };

  const requestExtras = async (nextStart: string, nextEnd: string) => {
    if (!symbol) return;
    extraAbortRef.current?.abort();
    const controller = new AbortController();
    extraAbortRef.current = controller;
    try {
      const res = await dailyApi.postKline(
        { symbol, start: nextStart, end: nextEnd, include_broker: false, include_settlement: true, include_valuation: true },
        { signal: controller.signal },
      );
      if (!controller.signal.aborted) {
        setFullData((prev) => mergeKline(prev, res));
      }
    } catch {
      return;
    }
  };

  useEffect(() => {
    if (!fullData) return;
    const filtered = filterByDate(fullData, start, end);
    setViewData(filtered);
  }, [fullData, start, end]);

  const title = useMemo(() => (symbol ? `K线 - ${symbol}` : 'K线'), [symbol]);

  const activeChart = useMemo(() => {
    const broker = viewData?.broker;
    const settlement = viewData?.settlement;
    const valuation = viewData?.valuation;
    if (panel === 'broker_yield') {
      return {
        title: '中介 - 收益率',
        ohlc: broker?.yield_ohlc ?? [],
        valuation: valuation?.yield_line ?? [],
        valuationLabel: '估值收益率',
      };
    }
    if (panel === 'broker_price') {
      return {
        title: '中介 - 净价',
        ohlc: broker?.price_ohlc ?? [],
        valuation: valuation?.price_line ?? [],
        valuationLabel: '估值净价',
      };
    }
    if (panel === 'settlement_yield') {
      return {
        title: '前台 - 收益率',
        ohlc: settlement?.yield_ohlc ?? [],
        valuation: valuation?.yield_line ?? [],
        valuationLabel: '估值收益率',
      };
    }
    return {
      title: '前台 - 净价',
      ohlc: settlement?.price_ohlc ?? [],
      valuation: valuation?.price_line ?? [],
      valuationLabel: '估值净价',
    };
  }, [viewData, panel]);

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
          <div className="mt-3 rounded-md border border-border/50 bg-card/40 px-4 py-3">
            <div className="grid grid-cols-4 grid-rows-2 gap-x-6 gap-y-2 text-xs text-muted-foreground">
              {symbol ? (
                <div>
                  <span className="mr-2 text-foreground">债券代码</span>
                  <span>{symbol}</span>
                </div>
              ) : null}
            {meta?.short_name ? (
              <div>
                <span className="mr-2 text-foreground">债券名称</span>
                <span>{meta.short_name}</span>
              </div>
            ) : null}
            {meta?.age_limit !== undefined ? (
              <div>
                <span className="mr-2 text-foreground">剩余年限</span>
                <span>{String(meta.age_limit ?? '-')}</span>
              </div>
            ) : null}
            {meta?.close_yield !== undefined ? (
              <div>
                <span className="mr-2 text-foreground">收盘收益率</span>
                <span>{String(meta.close_yield ?? '-')}</span>
              </div>
            ) : null}
            {meta?.zz_val !== undefined ? (
              <div>
                <span className="mr-2 text-foreground">估值</span>
                <span>{String(meta.zz_val ?? '-')}</span>
              </div>
            ) : null}
            {meta?.pct_ytm !== undefined ? (
              <div>
                <span className="mr-2 text-foreground">收益率涨幅/BP</span>
                <span>{String(meta.pct_ytm ?? '-')}</span>
              </div>
            ) : null}
            {meta?.bias_bp !== undefined ? (
              <div>
                <span className="mr-2 text-foreground">成交偏离(BP)</span>
                <span>{String(meta.bias_bp ?? '-')}</span>
              </div>
            ) : null}
            {meta?.delist_date ? (
              <div>
                <span className="mr-2 text-foreground">到期日</span>
                <span>{meta.delist_date}</span>
              </div>
            ) : null}
            {meta?.actual_yield !== undefined ? (
              <div>
                <span className="mr-2 text-foreground">税后收益</span>
                <span>{String(meta.actual_yield ?? '-')}</span>
              </div>
            ) : null}
            </div>
          </div>
        </DialogHeader>

        <div className="flex-1 min-h-0 px-6 pb-6 overflow-auto">
          <div className="mt-2 flex flex-col gap-3 md:flex-row md:items-end md:justify-between">
            <div className="flex flex-wrap items-end gap-3">
              <div>
                <div className="mb-1 text-xs text-muted-foreground">开始日期</div>
                <input
                  type="date"
                  value={start}
                  onChange={(e) => {
                    const v = e.target.value;
                    setStart(v);
                  }}
                  className="h-9 rounded-md border border-border bg-background px-3 text-sm"
                />
              </div>
              <div>
                <div className="mb-1 text-xs text-muted-foreground">结束日期</div>
                <input
                  type="date"
                  value={end}
                  onChange={(e) => {
                    const v = e.target.value;
                    setEnd(v);
                  }}
                  className="h-9 rounded-md border border-border bg-background px-3 text-sm"
                />
              </div>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    const nextEnd = endDate || formatDate(new Date());
                    const nextStart = addMonths(nextEnd, -3);
                    setEnd(nextEnd);
                    setStart(nextStart);
                  }}
                >
                  3M
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    const nextEnd = endDate || formatDate(new Date());
                    const nextStart = addMonths(nextEnd, -6);
                    setEnd(nextEnd);
                    setStart(nextStart);
                  }}
                >
                  6M
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    const nextEnd = endDate || formatDate(new Date());
                    const nextStart = addMonths(nextEnd, -12);
                    setEnd(nextEnd);
                    setStart(nextStart);
                  }}
                >
                  1Y
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    const nextEnd = endDate || formatDate(new Date());
                    const nextStart = '2000-01-01';
                    setEnd(nextEnd);
                    setStart(nextStart);
                  }}
                >
                  ALL
                </Button>
              </div>
            </div>

            <div className="flex items-center justify-end gap-2">
              {fullData?.meta?.timings_ms ? (
                <div className="text-xs text-muted-foreground">{formatTimings(fullData.meta.timings_ms)}</div>
              ) : null}
              <Button
                variant="outline"
                size="sm"
                disabled={!symbol || loading}
                onClick={() => {
                  requestBroker('2000-01-01', end);
                }}
              >
                刷新
              </Button>
            </div>
          </div>

          {error ? <div className="mt-4 rounded-md border border-destructive/30 bg-destructive/5 px-4 py-3 text-sm text-destructive">{error}</div> : null}

          <div className={cn('mt-4 flex h-full flex-col gap-3', loading ? 'opacity-70' : '')}>
            <div className="grid grid-cols-4 gap-2 md:max-w-[720px] justify-start">
              <Button variant={panel === 'broker_yield' ? 'default' : 'outline'} size="sm" onClick={() => setPanel('broker_yield')}>
                中介-收益率
              </Button>
              <Button variant={panel === 'broker_price' ? 'default' : 'outline'} size="sm" onClick={() => setPanel('broker_price')}>
                中介-净价
              </Button>
              <Button variant={panel === 'settlement_yield' ? 'default' : 'outline'} size="sm" onClick={() => setPanel('settlement_yield')}>
                前台-收益率
              </Button>
              <Button variant={panel === 'settlement_price' ? 'default' : 'outline'} size="sm" onClick={() => setPanel('settlement_price')}>
                前台-净价
              </Button>
            </div>

            <div className="flex-1 min-h-0">
              <KlineChartCard
                title={activeChart.title}
                ohlc={activeChart.ohlc}
                valuation={activeChart.valuation}
                valuationLabel={activeChart.valuationLabel}
                layoutMode="fill"
              />
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

function filterByDate(data: KlineResponse, start: string, end: string): KlineResponse {
  const inRange = (d: string) => {
    return (!start || d >= start) && (!end || d <= end);
  };
  return {
    ...data,
    broker: {
      yield_ohlc: (data.broker.yield_ohlc ?? []).filter((p) => inRange(p.trade_date)),
      price_ohlc: (data.broker.price_ohlc ?? []).filter((p) => inRange(p.trade_date)),
    },
    settlement: {
      yield_ohlc: (data.settlement.yield_ohlc ?? []).filter((p) => inRange(p.trade_date)),
      price_ohlc: (data.settlement.price_ohlc ?? []).filter((p) => inRange(p.trade_date)),
    },
    valuation: {
      yield_line: (data.valuation.yield_line ?? []).filter((p) => inRange(p.trade_date)),
      price_line: (data.valuation.price_line ?? []).filter((p) => inRange(p.trade_date)),
    },
  } as KlineResponse;
}

function formatTimings(timings?: Record<string, number>) {
  if (!timings) return '';
  const pick = (k: string) => {
    const v = timings[k];
    if (typeof v !== 'number' || Number.isNaN(v)) return null;
    return Math.round(v);
  };
  const broker = pick('broker_query_ms');
  const settlement = pick('settlement_query_ms');
  const valuation = pick('valuation_query_ms');
  const build = pick('build_series_ms');
  const total = pick('total_ms');
  const parts = [
    broker != null ? `broker ${broker}ms` : null,
    settlement != null ? `settlement ${settlement}ms` : null,
    valuation != null ? `valuation ${valuation}ms` : null,
    build != null ? `build ${build}ms` : null,
    total != null ? `total ${total}ms` : null,
  ].filter(Boolean) as string[];
  return parts.join(' · ');
}

function mergeKline(base: KlineResponse | null, patch: KlineResponse): KlineResponse {
  if (!base) return patch;
  const hasAny = (s: { yield_ohlc: any[]; price_ohlc: any[] }) => (s.yield_ohlc?.length ?? 0) + (s.price_ohlc?.length ?? 0) > 0;
  const hasAnyVal = (v: { yield_line: any[]; price_line: any[] }) => (v.yield_line?.length ?? 0) + (v.price_line?.length ?? 0) > 0;
  return {
    ...base,
    range: patch.range ?? base.range,
    broker: hasAny(patch.broker) ? patch.broker : base.broker,
    settlement: hasAny(patch.settlement) ? patch.settlement : base.settlement,
    valuation: hasAnyVal(patch.valuation) ? patch.valuation : base.valuation,
    meta: { ...base.meta, ...patch.meta },
  };
}
