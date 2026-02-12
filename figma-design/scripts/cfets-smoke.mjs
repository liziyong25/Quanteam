const baseUrl = process.env.CFETS_SMOKE_BASE || 'http://localhost:3000/api';
const now = new Date();
const yyyy = now.getFullYear();
const mm = String(now.getMonth() + 1).padStart(2, '0');
const dd = String(now.getDate()).padStart(2, '0');
const today = `${yyyy}-${mm}-${dd}`;

const tradeDateEnv = process.env.CFETS_TRADE_DATE;
const endEnv = process.env.CFETS_END;
const start = process.env.CFETS_START || '2024-01-01';
const indicator = process.env.CFETS_INDICATOR || 'netbuy_amount';
const industryMode = process.env.CFETS_INDUSTRY_MODE || 'new';
const requestTimeoutMs = Number(process.env.CFETS_SMOKE_TIMEOUT_MS || 15000);

async function fetchJson(url, options) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), requestTimeoutMs);
  const res = await fetch(url, { ...options, signal: controller.signal }).finally(() => {
    clearTimeout(timer);
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${text}`);
  }
  return res.json();
}

async function main() {
  console.log(`[smoke] base=${baseUrl}`);
  console.log(`[smoke] timeout=${requestTimeoutMs}ms`);
  let latestTradeDate = null;
  if (!tradeDateEnv || !endEnv) {
    try {
      const meta = await fetchJson(`${baseUrl}/cfets/bond/meta`);
      latestTradeDate = meta?.latest_trade_date || null;
      if (latestTradeDate) {
        console.log(`[smoke] latest_trade_date=${latestTradeDate}`);
      }
    } catch (error) {
      const message = error?.message || String(error);
      console.warn(`[smoke] meta fetch failed: ${message}`);
    }
  }
  const tradeDate = tradeDateEnv || latestTradeDate || today;
  const end = endEnv || latestTradeDate || today;
  const pivotUrl = new URL(`${baseUrl}/cfets/bond/pivot`);
  pivotUrl.searchParams.set('trade_date', tradeDate);
  pivotUrl.searchParams.set('start', start);
  pivotUrl.searchParams.set('end', end);
  pivotUrl.searchParams.set('indicator', indicator);
  if (industryMode) {
    pivotUrl.searchParams.set('industry_mode', industryMode);
  }
  const pivot = await fetchJson(pivotUrl.toString());
  if (!Array.isArray(pivot.rows) || pivot.rows.length === 0) {
    throw new Error('pivot rows is empty');
  }
  if (!Array.isArray(pivot.industries) || pivot.industries.length === 0) {
    throw new Error('pivot industries is empty');
  }
  const symbol = pivot.rows[0]?.symbol;
  const industry = pivot.industries[0];
  console.log(`[smoke] pivot_rows=${pivot.rows.length} industries=${pivot.industries.length}`);

  if (symbol && industry) {
    const drilldownUrl = new URL(`${baseUrl}/cfets/bond/drilldown`);
    drilldownUrl.searchParams.set('industry', String(industry));
    drilldownUrl.searchParams.set('symbol', String(symbol));
    drilldownUrl.searchParams.set('indicator', indicator);
    drilldownUrl.searchParams.set('start', start);
    drilldownUrl.searchParams.set('end', end);
    if (industryMode) {
      drilldownUrl.searchParams.set('industry_mode', industryMode);
    }
    const drilldown = await fetchJson(drilldownUrl.toString());
    if (!Array.isArray(drilldown.dates)) {
      throw new Error('drilldown dates missing');
    }
    console.log(`[smoke] drilldown_dates=${drilldown.dates.length}`);
  } else {
    console.log('[smoke] skip drilldown: missing symbol/industry');
  }

  const gridUrl = new URL(`${baseUrl}/cfets/bond/grid`);
  gridUrl.searchParams.set('indicator', indicator);
  gridUrl.searchParams.set('start', start);
  gridUrl.searchParams.set('end', end);
  gridUrl.searchParams.set('cumulative', '1');
  gridUrl.searchParams.set('limit', '12');
  if (industryMode) {
    gridUrl.searchParams.set('industry_mode', industryMode);
  }
  if (industry) {
    gridUrl.searchParams.set('industry', String(industry));
  }
  const grid = await fetchJson(gridUrl.toString());
  if (!Array.isArray(grid.symbols)) {
    throw new Error('grid symbols missing');
  }
  console.log(`[smoke] grid_symbols=${grid.symbols.length}`);

  console.log('[smoke] cfets ok');
}

main().catch((err) => {
  console.error(`[smoke] failed: ${err.message}`);
  process.exit(1);
});
