import pathlib
src = pathlib.Path(r'D:\\WEQUANT1\\QUANTAXIS\\QAData\\financial_mean.py').read_text(encoding='utf-8', errors='ignore')
path = pathlib.Path(r'd:\\WEQUANT\\wequant\\utils\\financial_mean.py')
path.write_text(src, encoding='utf-8')
print('WROTE', path)
