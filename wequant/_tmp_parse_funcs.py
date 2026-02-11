import ast, json, pathlib
paths = [r'D:\\WEQUANT1\\QUANTAXIS\\QAFetch\\QAQuery.py', r'D:\\WEQUANT1\\QUANTAXIS\\QAFetch\\QAQuery_Advance.py']
result = []
for p in paths:
    src = pathlib.Path(p).read_text(encoding='utf-8', errors='ignore')
    tree = ast.parse(src)
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            result.append({"file": p, "name": node.name, "lineno": node.lineno})
print(json.dumps(result, ensure_ascii=False, indent=2))
