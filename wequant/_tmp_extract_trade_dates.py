import re, pathlib
src = pathlib.Path(r'D:\\WEQUANT1\\QUANTAXIS\\QAUtil\\QADate_trade.py').read_text(encoding='utf-8', errors='ignore')
match = re.search(r'trade_date_sse\s*=\s*\[(.*?)\]\n', src, re.S)
if not match:
    raise SystemExit('trade_date_sse not found')
list_body = match.group(1).strip()
content = "from __future__ import annotations\n\n# Auto-vendored from QUANTAXIS.QAUtil.QADate_trade.trade_date_sse\ntrade_date_sse = [\n" + list_body + "\n]\n"
path = pathlib.Path(r'd:\\WEQUANT\\wequant\\utils\\trade_dates.py')
path.write_text(content, encoding='utf-8')
print('WROTE', path)
