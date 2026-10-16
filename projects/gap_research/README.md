# 一轮 16 个跳空因子

[research.py](research.py) 只研究日线股票截面排序相关，不生成交易指令。默认作业轮次为第一轮，16 个候选；不自动运行第二至第四轮。

## 数据契约

提供 CSV：

```text
date,symbol,open,high,low,close,volume
2008-01-02,000001,10.0,10.5,9.8,10.2,123456
```

`date` 为 `YYYY-MM-DD`，`symbol` 字符串保留前导零。OHLC 需要同一复权口径，全部为有限正数，满足高低范围；量为有限非负数。同一日期/标的重复、缺失字段、无效价格直接报错，不静默修正。

另提供**独立的全市场交易日历 CSV**，唯一列 `date`，升序且不重复。程序先对齐此日历，不以“下一条该股票记录”替代下一交易日。缺失观测不前填；不自行构造真实交易日历。零量保留在审计中，尚未等价实现停牌/可交易性筛选。

## 真实数据指令

从仓库根目录运行（输入置于默认忽略的 `data`）：

```powershell
python -m projects.gap_research.research --data data\prices.csv --calendar data\calendar.csv --protocol reports\gap_round_01\protocol.json --output reports\runs\gap_round_01
```

事前规则见 [protocol.md](../../reports/gap_round_01/protocol.md)，机器配置见 [protocol.json](../../reports/gap_round_01/protocol.json)。修改协议意味着新实验，必须在看结果之前修改并保留旧版本。

输出新目录：冻结协议、输入及实现 SHA256、运行版本、数据审计、全部 16 候选的训练/验证/测试指标、逐日 IC、选中规则和报告。禁止覆盖原目录。没有合格正向训练候选或分段样本不足时仍保留完整结果，返回码 2，`status=insufficient_evidence`；解析/输入错误返回 1。

## 软件冒烟测试

```powershell
python -m projects.gap_research.synthetic --output data\synthetic_new
python -m projects.gap_research.research --data data\synthetic_new\synthetic_prices.csv --calendar data\synthetic_new\synthetic_calendar.csv --protocol data\synthetic_new\synthetic_protocol.json --output reports\runs\synthetic_new --synthetic
```

[synthetic.py](synthetic.py) 使用固定种子、40 个虚构标的、360 个工作日。工作日不是实际交易日历；标的具有人工构造的持续差异，只证明流程可以运行，不能证明现实预测能力。[现有合成结果](../../reports/synthetic_smoke/report.md) 已明确标记。

## 评价边界

信号 T 收盘后可见，标签是 T+1 收盘至 T+3 收盘收益，不是 T 收盘立即成交。只按训练平均正向 IC 选因子；验证门槛决定是否通过；测试不反向改规则。截面 IC 按同一有效标的集合处理并列排序；不足 30 个或常数截面记缺失。HAC 区间保留缺失日历间隔，不是扣费净收益，不校正候选选择的多重检验。

未独立审计复权、历史股票池、退市、涨跌停、成交约束与成本。真正可交易结论需未来新数据、预先固定组合构建和执行规则。
