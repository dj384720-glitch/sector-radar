# 板块雷达 Sector Radar

开源的 A 股主题板块长期表现看板。每个板块绑定可复核公开基准，并计算 10 年、5 年、3 年、1 年、6 个月、3 个月、1 个月、1 周涨跌。

## 口径

- 收益 = 最近可用交易日收盘价 / 起点收盘价 - 1。
- 未绑定可靠基准的主题显示「待绑定」，不展示臆造收益。
- `scripts/update_data.py` 是每日更新入口，`.github/workflows/update-data.yml` 可在公开 GitHub 仓库每日运行。

在 `data/sectors.json` 填写每个主题的 `benchmark` 与 `source` 后即可接入行情。仅供研究，不构成投资建议。
