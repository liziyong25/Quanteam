import React from 'react';
import Plot from 'react-plotly.js';

import { Card, CardContent, CardHeader, CardTitle } from '@/app/components/ui/card';
import type { LinePoint, OhlcPoint } from '@/lib/api/daily';

function getThemeColors() {
  if (typeof window === 'undefined') {
    return { foreground: '#94a3b8', grid: '#334155' };
  }
  const style = getComputedStyle(document.documentElement);
  const fg = style.getPropertyValue('--muted-foreground')?.trim() || '#94a3b8';
  const border = style.getPropertyValue('--border')?.trim() || '#334155';
  return { foreground: fg, grid: border };
}

function toAxis(values: Array<number | null>) {
  return values.map((v) => (typeof v === 'number' && Number.isFinite(v) ? v : null));
}

export function KlineChartCard({
  title,
  ohlc,
  valuation,
  valuationLabel,
  layoutMode = 'fixed',
}: {
  title: string;
  ohlc: OhlcPoint[];
  valuation: LinePoint[];
  valuationLabel: string;
  layoutMode?: 'fixed' | 'aspect' | 'fill';
}) {
  const colors = getThemeColors();

  const x = ohlc.map((p) => p.trade_date);
  const open = toAxis(ohlc.map((p) => p.open));
  const high = toAxis(ohlc.map((p) => p.high));
  const low = toAxis(ohlc.map((p) => p.low));
  const close = toAxis(ohlc.map((p) => p.close));
  const vol = toAxis(ohlc.map((p) => p.vol));

  const valX = valuation.map((p) => p.trade_date);
  const valY = toAxis(valuation.map((p) => p.value));

  return (
    <Card className={layoutMode === 'fill' ? 'h-full overflow-hidden' : 'overflow-hidden'}>
      <CardHeader className="pb-2">
        <CardTitle className="text-sm">{title}</CardTitle>
      </CardHeader>
      <CardContent className={layoutMode === 'fixed' ? 'h-[340px] p-2' : layoutMode === 'aspect' ? 'p-2' : 'p-2 h-full'}>
        <div className={layoutMode === 'aspect' ? 'aspect-video w-full' : 'h-full w-full'}>
          <Plot
            data={[
              {
                type: 'candlestick',
                x,
                open,
                high,
                low,
                close,
                name: title,
                increasing: { line: { color: 'rgb(34,197,94)' } },
                decreasing: { line: { color: 'rgb(239,68,68)' } },
                yaxis: 'y',
              } as any,
              {
                type: 'bar',
                x,
                y: vol,
                name: 'Vol',
                marker: { color: 'rgba(148,163,184,0.35)' },
                yaxis: 'y2',
              } as any,
              {
                type: 'scatter',
                mode: 'lines',
                x: valX,
                y: valY,
                name: valuationLabel,
                line: { color: 'rgb(59,130,246)', width: 1.5 },
                yaxis: 'y',
              } as any,
            ]}
            layout={{
              autosize: true,
              margin: { l: 50, r: 20, t: 18, b: 32 },
              paper_bgcolor: 'rgba(0,0,0,0)',
              plot_bgcolor: 'rgba(0,0,0,0)',
              font: { color: colors.foreground },
              xaxis: { gridcolor: colors.grid, showgrid: true, type: 'date' },
              yaxis: { gridcolor: colors.grid, showgrid: true, domain: [0.23, 1] },
              yaxis2: {
                gridcolor: colors.grid,
                showgrid: false,
                domain: [0, 0.18],
                rangemode: 'tozero',
              },
              showlegend: true,
              legend: { orientation: 'h', y: 1.08 },
            }}
            useResizeHandler
            style={{ width: '100%', height: '100%' }}
            config={{ displayModeBar: false, responsive: true }}
          />
        </div>
      </CardContent>
    </Card>
  );
}
