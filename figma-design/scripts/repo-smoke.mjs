const baseUrl = process.env.REPO_SMOKE_BASE || 'http://localhost:3000/api';
const start = process.env.REPO_START || '2022-01-01';
const end = process.env.REPO_END || '';
const tradeDate = process.env.REPO_TRADE_DATE || '';
const side = process.env.REPO_SIDE || 'both';
const industry = process.env.REPO_INDUSTRY || '大型银行';
const requestTimeoutMs = Number(process.env.REPO_SMOKE_TIMEOUT_MS || 20000);

async function fetchJson(url, options) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), requestTimeoutMs);
  const res = await fetch(url, { ...options, signal: controller.signal }).finally(() => clearTimeout(timer));
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${text}`);
  }
  return res.json();
}

async function main() {
  console.log(`[smoke] base=${baseUrl}`);
  console.log(`[smoke] timeout=${requestTimeoutMs}ms`);

  const pivotUrl = new URL(`${baseUrl}/cfets/repo/pivot`);
  pivotUrl.searchParams.set('start', start);
  if (end) pivotUrl.searchParams.set('end', end);
  if (tradeDate) pivotUrl.searchParams.set('trade_date', tradeDate);
  if (side) pivotUrl.searchParams.set('side', side);

  const pivot = await fetchJson(pivotUrl.toString());
  if (!pivot?.rows?.length) throw new Error('pivot rows is empty');
  if (!pivot?.industries?.length) throw new Error('pivot industries is empty');
  if (!pivot?.age_order?.length) throw new Error('pivot age_order is empty');
  console.log(`[smoke] pivot_rows=${pivot.rows.length} industries=${pivot.industries.length} trade_date=${pivot.meta?.trade_date}`);

  const panelUrl = new URL(`${baseUrl}/cfets/repo/panel`);
  panelUrl.searchParams.set('industry', industry);
  panelUrl.searchParams.set('side', 'repo');
  panelUrl.searchParams.set('start', start);
  if (end) panelUrl.searchParams.set('end', end);
  const panel = await fetchJson(panelUrl.toString());
  if (!Array.isArray(panel.dates)) throw new Error('panel dates missing');
  if (!Array.isArray(panel.columns) || panel.columns.length === 0) throw new Error('panel columns missing');
  console.log(`[smoke] panel_dates=${panel.dates.length} columns=${panel.columns.length}`);

  console.log('[smoke] repo ok');
}

main().catch((err) => {
  console.error(`[smoke] failed: ${err.message}`);
  process.exit(1);
});

