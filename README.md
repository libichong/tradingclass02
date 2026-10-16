# 《当代量化交易系统的原理与实现》第二讲

对应 [aslan9/pku_quantllm#2](https://github.com/aslan9/pku_quantllm/issues/2)。
本仓库从初始空项目实现作业，不把外部报告中的历史成绩当作本次已完成证据。

## 交付与状态

| 要求 | 本次交付 | 状态 |
|---|---|---|
| 学习 Wiki | [索引](wiki/index.md)、[维护规范](wiki/schema.md)、[维护日志](wiki/log.md) | 已接收用户提供的 LLM Wiki 指南，并补齐来源追溯与维护流程 |
| 下载并阅读三个模块 | 本地 `raw` 源码、[提交记录](reports/source_commits.json)、[源码摘要](wiki/sources/vnpy.md) | 已下载并阅读作业相关链路 |
| 底层 CTP 演示 | [程序与说明](projects/ctp_demo/README.md) | 只读登录/行情、显式联网和故障终止；原生扩展和联网未验证 |
| 系统架构与三类策略 | [架构](wiki/concepts/architecture.md)、[策略比较](wiki/concepts/strategy-types.md) | 已整理 |
| 突破价格后下单 | [待审核方案](wiki/code/order-plan.md) | 只交方案；未实现发单、未下单 |
| 一轮 10–20 个跳空因子 | [16 个因子程序](projects/gap_research/README.md)、[事前方案](reports/gap_round_01/protocol.md) | 已实现冻结登记、分离开发与测试开封；真实数据与未来样本待提供 |

### LLM Wiki 如何落地

已收到用户提供的 `LLM Wiki` 原文，并建立[来源摘要与 SHA256 记录](wiki/sources/llm-wiki.md)。指南的重点是持续维护可累积的知识库，而不是每次问答都重新拼接原始材料。

- **原始来源**：上游源码、原始数据和用户只读附件保持原样，记录版本或哈希；本次附件不复制全文入库，新克隆也不包含该附件。
- **Wiki**：以[索引](wiki/index.md)串联来源摘要、概念和本次实现，引用证据、保留冲突并修正过时状态；可复用的问答回写到相关页面。
- **Schema**：[维护规范](wiki/schema.md)约定目录、页面与证据边界，以及 Ingest（接收）、Query（问答回写）、Lint（核对）流程；它是项目说明，不声称所有 Agent 会自动加载。
- **索引与日志分工**：索引按内容导航，[日志](wiki/log.md)按时间追加，历史记录不因当前状态变化而重写。当前规模无需额外安装 Obsidian、qmd 或向量检索服务。

“指南已收到并完成首次对照”不等于真实数据或交易验收完成；剩余资料见[课程材料状态](wiki/sources/course-materials.md)。

## 对本轮反馈的处理

本次按确认后的范围**保持只读行情，不接入任何真实发单接口**。不能把“登录成功”“发出平仓单”或 `orders_sent=0` 写成交易闭环成功；其他同学仓库的凭据或成绩也不是本仓库的证据。

| 反馈 | 本次修改 | 仍不能宣称完成 |
|---|---|---|
| 账户安全 | 配置样例的 UserID/密码/AppID/AuthCode 无值；敏感字段不进入配置对象 `repr`；入口错误不输出原始异常正文 | 未代替账户所有者轮换凭据，也未重写任何 Git 历史 |
| 默认安全、状态未知 | 不传 `--live` 不联网；任一通道断线立即失败，忽略后续重连/成功回调；启动和逐合约行情均有超时 | 只读状态管理不是交易委托对账、持久化防重或平仓风控 |
| 行情证据一致 | 逐合约分别统计全部 Tick 与有效 Tick；每个配置合约均须有有效行情；无效 Tick 不刷新静默计时 | 未证明当日活跃度、真实行情连通或原生 ABI |
| 反复查看测试集 | 真实研究先独立冻结；默认只算训练/验证，验证通过后单次显式开封，测试只评价训练选中项 | 本地文件可被人为篡改；旧年份不是新的未来样本 |
| 重叠收益与乐观成本 | HAC 保留日历间隔、滞后至少 2；继续只报告 IC，不把重叠收益直接年化，不生成虚构净收益 | 未实现可成交组合、真实费用、容量与融券模型 |
| 可复现 | 增加[离线依赖锁](requirements-lock.txt)、命令/环境指纹、失败状态与回归测试 | 依赖快照不等于所有平台兼容，编译检查不等于运行成功 |

### 安全操作与凭据泄露处置

- 只在本地使用自己的仿真账号；UserID 也是账户标识，不应进入源码、截图、报告、命令行参数或公开日志。
- [本地忽略规则](.gitignore) 包含 `*.local.json`、`.env`、`.ctp-flow`、原始数据、运行输出和冻结登记。**忽略规则不删除已经跟踪的文件，也不清除历史记录。**
- 若任何凭据曾公开：先通过服务方停用/轮换；再由仓库所有者审核历史清理方案、协调协作者处理分支/标签/克隆及缓存。仅删当前文件或把仓库设为私有不能恢复凭据安全。本次不擅自改写历史或强推，也不复述凭据。
- 程序不查询账户资金，因此没有生成资金快照；不要手工补交完整账户响应。公开证据仅保留必要行情、时间、错误码、状态与计数；发布前仍需人工检查脱敏。忽略目录不是加密存储。
- `--live` 是**联网许可**，不是交易许可或 SimNow 地址认证。请核对官方当前仿真前端，禁止使用实盘账户。程序本身没有下单、撤单、持仓/资金查询和结算确认。

## 安装与离线测试

终端 Python 3.11+；本次离线验证使用 Python 3.14.3。CTP 原生依赖请使用有相应发行包或完整编译环境的解释器，不保证 Python 3.14 可安装。

```powershell
python -m pip install -r requirements-lock.txt
python -m pip install -e .
python -m pip check
python -m unittest discover -s tests -v
$LASTEXITCODE
python -m compileall -q projects tests
```

[依赖锁](requirements-lock.txt) 固定本次 Windows / Python 3.14.3 离线环境的运行依赖（含传递依赖），不含未安装的原生 CTP 扩展，也不是跨平台、带包哈希的构建锁。其他解释器需重新验证，不承诺该快照能覆盖所有 Python 3.11+ 环境。最新离线复验摘要保存在 [validation.json](reports/validation.json)；历史合成报告保留原样，不冒充当前版本产物。

### 行情演示

```powershell
python -m pip install -e ".[ctp]"
Copy-Item projects\ctp_demo\config.example.json projects\ctp_demo\config.local.json
# 用自己的仿真账号、当前前端和未到期合约填写本地配置。
python -m projects.ctp_demo.demo --config projects\ctp_demo\config.local.json --live --duration 60 --startup-timeout 30 --quote-timeout 30 --events reports\runs\ctp_live_01\events.jsonl
$LASTEXITCODE
```

不传 `--live` 直接拒绝联网；不传 `--duration` 则持续到 `Ctrl+C` 或安全边界触发。认证、登录、订阅、请求错误及任一通道断线均失败退出，不再自动重登录。默认启动超时 30 秒、逐合约有效 Tick 静默超时 60 秒；参数按交易时段记录，非交易时段也会触发超时。每个合约至少收到一条有效行情且仍就绪，才允许限时成功退出。完整退出码和证据解释见 [行情说明](projects/ctp_demo/README.md)。

### 因子研究

真实数据接口与完整指令见 [研究说明](projects/gap_research/README.md)。当前本地合成数据位于 `data\review_20261016_synthetic`，包含 `synthetic_prices.csv`、`synthetic_calendar.csv` 和 `synthetic_protocol.json`，无需重新生成。以下从仓库根目录使用现有数据复验软件，不是市场实证：

```powershell
python -m projects.gap_research.research --data data\review_20261016_synthetic\synthetic_prices.csv --calendar data\review_20261016_synthetic\synthetic_calendar.csv --protocol data\review_20261016_synthetic\synthetic_protocol.json --output reports\runs\review_20261016_synthetic_rerun_01 --synthetic
$LASTEXITCODE
```

输入目录可复用，**输出目录必须是新目录**；若示例的 `rerun_01` 已存在，请更换编号，禁止覆盖已有实验。现有本地结果位于 `reports\runs\review_20261016_synthetic`，其 `status.json` 记录 `completed`、退出码 0；本地输入与结果目录均被 Git 忽略，不会随克隆自动提供。若在新环境缺少样本，可先用 `python -m projects.gap_research.synthetic --output data\review_20261016_synthetic` 生成固定种子的合成数据，该生成命令也要求目标目录尚不存在。

仓库保存[早期合成冒烟证据](reports/synthetic_smoke/report.md)，不宣称因子有效。当前版本的 `--synthetic` 只为软件复验，可输出选中候选测试统计；不得对真实数据使用该标志来绕过冻结。

真实研究必须先补全[协议模板](reports/gap_round_01/protocol.json)中的股票池、复权口径和未来样本说明，再分开执行 `--freeze-only`、开发运行、`--open-test`。完整命令见[研究说明](projects/gap_research/README.md)。数据/协议/实现/依赖锁/运行版本改变会拒绝执行；同一登记的开发和测试各只允许一次，失败也保留。开发期保留全部 16 候选，测试只报告训练选中的项，不再输出全候选测试排名。

**研究数字的含义**：Rank IC 是截面排序相关，不是资金收益率。HAC 区间只处理相关性估计，不能替代扣费收益、最大回撤、容量和多重检验。由于没有组合与执行模型，本仓库不报告“净年化/最大回撤”，也不拿 IC 区间冒充收益置信区间。未来若增加可交易研究，需先冻结组合构建和成交规则，再报告毛/净收益、换手、最大回撤及区块/HAC 置信区间，并纳入双边费用、印花税、滑点、涨跌停/停牌、容量和融券约束。

### 下一轮补交验收清单

- **真实行情（未完成）**：兼容原生环境、实际命令、版本、退出码、逐合约持续行情及计数一致的脱敏原始 JSONL；订阅成功不能替代 Tick 证据。
- **交易闭环（未实现）**：仅限 SimNow 1 手；开仓意图先持久化，建立跨会话委托/成交归属及防重，验证保证金与重启对账；必须是开仓成交 → 平仓成交 → 查询目标持仓为 0 → 无活动委托。断线、拒单、超时及状态未知都必须 fail-closed。需另行设计和现场验收，不能在当前只读程序上勾选完成。
- **真正未来样本（未完成）**：先在独立、带时间戳的记录中冻结规则与未来区间，再等待数据自然产生。本地历史 CSV 指纹不证明“未查看”；当前冻结机制也不支持在同一实验中追加未来数据。已看历史只作探索证据。
- **公开提交证据**：保留所有成功、失败与不足样本尝试；记录程序真实执行，不把 `compileall`、替身测试或退出码 0 写成真实交易成功。

## 交付边界

- 已收到用户提供的 LLM Wiki 指南并完成首次对照；课程原始行情、复权资料和历史股票池仍未取得。
- 没有本次 SimNow 登录或持续活跃合约的现场证据；配置中的合约仅为示例，需按运行日确认。
- 未执行任何交易，也不包含复杂表达式、XGBoost 或 AutoGluon 扩展。
- 一轮真实因子挖掘待数据到位；“最多四轮”不是必须四轮，本次不自动扩展搜索。
- `raw`、`data`、账号、CTP 流文件及本地运行结果默认忽略，公开交付仅含原创摘要、代码和明确标注的证据。