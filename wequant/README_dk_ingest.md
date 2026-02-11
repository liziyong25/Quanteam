# DK Ingest（dk_ingest.py）

## 功能概述

`dk_ingest.py` 是一个将 DK 相关 Excel 批量解析并写入 MongoDB 的工程化脚本，支持：

- `full`：全量读取所有文件并写库（幂等 upsert）
- `incremental`：增量读取（跳过已成功处理且文件未变化的文件）
- `sample`：按年份抽样试读（不写 MongoDB），输出 Markdown 报告，汇总失败原因与 sheet_names 供人工判定
- `--dry-run`：只解析不写数据表（full/incremental 下可用；仍可写入 ingest_log，且不会影响增量跳过判定）
- `--trade-date`：只处理某一天（文件名最后一个 8 位数字匹配的日期，如 `20260202`）

## 三类文件识别规则与入库映射

脚本会在 `--root` 目录下扫描 `*.xlsx`，并按文件名识别类别：

1) 中国DK（china）
- 规则：文件名包含 `【V】奇衡DK` 且不包含 `全球`
- 写入 collection：`china_dk_data`
  - 字段口径：最终以 `code1` 替代 `code`（即：写入时 `code=code1`，原始 `code` 不保留）

2) DK强弱转换（star / strength）
- 示例：`奇衡DK星球指数学习材料20241009.xlsx`
- 规则：文件名包含 `奇衡DK星球` 且包含 `指数` 或 `数据`，并且不包含 `【V】奇衡DK`
- 写入 collection：`dk_strength`

3) 全球DK（global）
- 规则：文件名包含 `【V】奇衡DK全球`
- 写入 collection：`gobal_dk_data`（注意拼写就是 `gobal`）

额外：每个文件处理过程会写入日志 collection：
- `dk_ingest_log`

## trade_date 提取规则

`trade_date` 从文件名提取：**抓取文件名中所有 8 位数字，取最后一个**，作为 `YYYYMMDD`。

例如：
- `812251521512552_【V】奇衡DK星球学习材料20260202.xlsx` -> `20260202`

## 中国DK：sheet 自适应匹配规则

中国DK文件（china）会读取多个 sheet 并合并。sheet 名可能变化，脚本使用如下“兼容升级版”匹配：

- `sheet_name1`：包含 `矩形`
- `sheet_name2`：包含 `UBW`
- `sheet_name3`：优先包含 `原共享池`；否则匹配包含 `原共享`
- `sheet_name4`：优先包含 `原共享池主连`；否则匹配包含 `主连`

额外（按 notebook）：
- 必选：包含 `情绪数据库` 的 sheet
- 可选：包含 `2023` 的 sheet（取第一个命中）
- 可选：包含 `指数数据库` 的 sheet（取第一个命中）

如果匹配不到目标 sheet，会在：
- `dk_ingest_log.sheet_names` 记录该文件实际读取到的 sheet 列表（失败时尤其重要）
- `sample` 模式的报告中列出 `sheet_names` 与失败原因，便于人工判定

## 增量判定规则（incremental）

`incremental` 模式会跳过“已成功处理且文件未变化”的文件。未变化判定基于：

- `file_size`
- `mtime`
- `content_hash`（sha1）

当且仅当 `dk_ingest_log` 中存在同一路径 `file_path` 的 `status=success` 且 `dry_run=false` 记录，并且上述三个字段全部一致时，才会跳过。

## 幂等写入（去重/唯一性）

脚本使用 `bulk_write + UpdateOne(upsert=True)` 写入，避免重复插入。唯一性（unique）建议/默认策略：

- `china_dk_data`：`(trade_date, code)`（其中 `code` 为“写入后的 code1”）
- `dk_strength`：`(trade_date, code, type)`（weak/strong 需要保留）
- `gobal_dk_data`：`(trade_date, code, source_sheet)`（避免多 sheet 覆盖）

## Windows 运行示例命令

全量：

```bash
python dk_ingest.py --mode full --root D:\zxxq_xlsx
```

增量：

```bash
python dk_ingest.py --mode incremental --root D:\zxxq_xlsx
```

抽样：

```bash
python dk_ingest.py --mode sample --root D:\zxxq_xlsx --sample-per-year 2
```

只跑某类：

```bash
python dk_ingest.py --mode full --root D:\zxxq_xlsx --categories china
python dk_ingest.py --mode full --root D:\zxxq_xlsx --categories china,star
```

干跑（只解析不写数据表）：

```bash
python dk_ingest.py --mode full --root D:\zxxq_xlsx --dry-run
python dk_ingest.py --mode incremental --root D:\zxxq_xlsx --dry-run
```

只跑某一天：

```bash
python dk_ingest.py --mode full --root D:\zxxq_xlsx --trade-date 20260202
```

## 人工判定模板（Issue 模板）

将 sample 报告中的失败项复制出来，按下列模板反馈，便于快速定位：

```text
Title: [DK Ingest] Parse failure - {file_name}

file_name:
trade_date:
category:  # china / star / global
sheet_names:  # paste list from report/log

expected_keywords:  # 例如：矩形/UBW/原共享池/原共享池主连/情绪数据库/指数数据库
what_matched:       # 实际匹配到的 sheet（如有）

error:
  error_type:
  error_message:

screenshot_needed:  # yes/no（如 yes，请说明需要哪几行/哪几列的截图）
notes:
```
