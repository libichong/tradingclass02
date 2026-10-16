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
# 准备 data\prices.csv 与 data\calendar.csv 后，按下方冻结流程执行。
python -m projects.gap_research.research --help
```

真实研究必须按下面流程提供 `--freeze`，不再允许直接生成测试期结果。

事前规则见 [protocol.md](../../reports/gap_round_01/protocol.md)，机器配置见 [protocol.json](../../reports/gap_round_01/protocol.json)。模板中的 `research_contract.universe`、`adjustment`、`future_holdout` 留空，必须根据实际数据填写，不能凭空声称已审计。其余字段固定信号/成交时点、停止规则、成本边界和已看历史。修改协议意味着新实验，必须在看结果之前修改并保留旧版本。

### 冻结、开发与显式开封

```powershell
# 复制协议到本地并补全 research_contract；不要覆盖已运行实验的协议。
Copy-Item reports\gap_round_01\protocol.json data\protocol.local.json
# 只计算指纹并登记协议，不计算因子、IC 或选择结果。
python -m projects.gap_research.research --data data\prices.csv --calendar data\calendar.csv --protocol data\protocol.local.json --freeze reports\freezes\round_01 --freeze-only
# 开发：只输出全部候选的 train / validation；不生成 test 指标或 daily_test.csv。
python -m projects.gap_research.research --data data\prices.csv --calendar data\calendar.csv --protocol data\protocol.local.json --freeze reports\freezes\round_01 --output reports\runs\round_01_dev
# 仅在开发完成且冻结的验证门槛通过后，由人工明确决定开封。
python -m projects.gap_research.research --data data\prices.csv --calendar data\calendar.csv --protocol data\protocol.local.json --freeze reports\freezes\round_01 --open-test --output reports\runs\round_01_test
$LASTEXITCODE
```

冻结记录绑定数据、日历、协议、实现、依赖锁的 SHA256 和 Python/NumPy/pandas 版本。文件或运行版本改变即拒绝执行。每个冻结目录的开发/测试阶段均独占创建单次登记，失败也保留并消耗次数；不要删除登记再试。失败后的新实验应保留旧证据、解释失败原因，并重新事前登记。新输出目录本身不是允许重复查看的凭据。

测试开封时只计算训练选中候选的测试指标，不展示全部测试排名；会按完全相同的冻结输入确定性重算开发结果，不允许重新调参。训练未选中、开发未完成或验证未通过，不允许开封。所有开发候选和失败结果仍保留。成功登记与结果包含命令、环境和退出码；启动后的可捕获输入/文件异常会将状态标记为 `failed`，进程被强制终止则可能保留 `started`，必须按未完成处理。

**这是本地研究纪律，不是防篡改保险箱。** 原始 CSV 仍可直接读取，创建另一个冻结目录也不能抹去先前查看行为。整份 CSV 的冻结哈希只能证明已有历史文件身份，不能证明未来数据未被看过。真正的未来区间必须先在独立、带时间戳的登记中锁定规则，待数据自然产生后按预先规定的追加数据流程验收；当前实现不支持在同一冻结目录追加未来数据。不要把历史测试、合成数据或 `--freeze-only` 时间戳当作真正未来样本证据。

输出新目录：冻结协议、输入及实现 SHA256、运行命令与版本、数据审计、全部 16 候选开发期指标、逐日 IC、选中规则和报告；测试指标只在开封时保存选中候选。禁止覆盖原目录。没有合格正向训练候选或已评估分段样本不足时仍保留完整结果，返回码 2，`status=insufficient_evidence`；解析/输入/冻结不匹配或重复执行返回 1。返回 0 只代表软件阶段完成且样本量达标，不保证验证通过，更不代表可交易。

## 软件冒烟测试

```powershell
python -m projects.gap_research.synthetic --output data\synthetic_new
python -m projects.gap_research.research --data data\synthetic_new\synthetic_prices.csv --calendar data\synthetic_new\synthetic_calendar.csv --protocol data\synthetic_new\synthetic_protocol.json --output reports\runs\synthetic_new --synthetic
```

[synthetic.py](synthetic.py) 使用固定种子、40 个虚构标的、360 个工作日。`--synthetic` 可以在一次冒烟运行中输出选中候选的测试结果，不走真实冻结注册流程；不得用它规避真实研究约束。工作日不是实际交易日历；标的具有人工构造的持续差异，只证明流程可以运行，不能证明现实预测能力。[已有合成结果](../../reports/synthetic_smoke/report.md) 是旧版本记录，不是当前代码的复验，未覆盖或重写。

## 评价边界

信号 T 收盘后可见，标签是 T+1 收盘至 T+3 收盘收益，不是 T 收盘立即成交。只按训练平均正向 IC 选因子；验证门槛决定是否通过；测试不反向改规则。截面 IC 按同一有效标的集合处理并列排序；不足 30 个或常数截面记缺失。HAC 区间保留缺失日历间隔；协议滞后不得小于 2，默认 5，以覆盖标签重叠。它不是扣费净收益，不校正候选选择的多重检验，也不把重叠两日收益直接乘以 252 年化。

未独立审计复权、历史股票池、退市、涨跌停、成交约束与成本。真正可交易结论需未来新数据、预先固定组合构建和执行规则。
