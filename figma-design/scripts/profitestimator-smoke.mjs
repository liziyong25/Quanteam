const baseUrl = process.env.PROFITESTIMATOR_SMOKE_BASE || 'http://localhost:3000/api';
const tradeDate = process.env.PROFITESTIMATOR_TRADE_DATE || new Date().toISOString().slice(0, 10);
const requestTimeoutMs = Number(process.env.PROFITESTIMATOR_SMOKE_TIMEOUT_MS || 15000);

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
  const bondTypes = await fetchJson(`${baseUrl}/profitestimator/bond_types`);
  if (!Array.isArray(bondTypes.items) || bondTypes.items.length === 0) {
    throw new Error('bond_types items is empty');
  }
  const bondType = bondTypes.items[0].bond_type;
  console.log(`[smoke] bond_type=${bondType}`);

  const issuers = await fetchJson(`${baseUrl}/profitestimator/issuers?bond_type=${encodeURIComponent(bondType)}`);
  if (!Array.isArray(issuers.items)) {
    throw new Error('issuers items is invalid');
  }
  console.log(`[smoke] issuers=${issuers.items.length}`);

  const compute = await fetchJson(`${baseUrl}/profitestimator/compute`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      trade_date: tradeDate,
      bond_type: bondType,
      holding_days: 180,
      age_limit_min: 0,
      age_limit_max: 10,
      results_page: 1,
      results_page_size: 1,
      curve_page: 1,
      curve_page_size: 1,
    }),
  });

  const results = compute?.results;
  if (!results?.columns || !Array.isArray(results.rows)) {
    throw new Error('compute results missing columns/rows');
  }
  const symbolIndex = results.columns.indexOf('symbol');
  const symbol = symbolIndex >= 0 ? results.rows?.[0]?.[symbolIndex] : null;
  console.log(`[smoke] results_rows=${results.rows.length}`);

  if (symbol) {
    const plot = await fetchJson(`${baseUrl}/profitestimator/plot`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        trade_date: tradeDate,
        bond_type: bondType,
        holding_days: 180,
        age_limit_min: 0,
        age_limit_max: 10,
        symbol: String(symbol),
      }),
    });
    const hasPlot = Boolean(plot?.plotly);
    console.log(`[smoke] plotly=${hasPlot ? 'ok' : 'empty'}`);
  } else {
    console.log('[smoke] no symbol available for plot');
  }

  console.log('[smoke] profitestimator ok');
}

main().catch((err) => {
  console.error(`[smoke] failed: ${err.message}`);
  process.exit(1);
});
