# 《当代量化交易系统的原理与实现》第二讲

对应 [aslan9/pku_quantllm#2](https://github.com/aslan9/pku_quantllm/issues/2)。
本仓库从初始空项目实现作业，不把外部报告中的历史成绩当作本次已完成证据。

## 交付与状态

| 要求 | 本次交付 | 状态 |
|---|---|---|
| 学习 Wiki | [索引](wiki/index.md)、[维护日志](wiki/log.md) | 已建立；课程 `llm-wiki.md` 未提供，待对照 |
| 下载并阅读三个模块 | 本地 `raw` 源码、[提交记录](reports/source_commits.json)、[源码摘要](wiki/sources/vnpy.md) | 已下载并阅读作业相关链路 |
| 底层 CTP 演示 | [程序与说明](projects/ctp_demo/README.md) | 已实现、离线测试通过；原生扩展和联网未验证 |
| 系统架构与三类策略 | [架构](wiki/concepts/architecture.md)、[策略比较](wiki/concepts/strategy-types.md) | 已整理 |
| 突破价格后下单 | [待审核方案](wiki/code/order-plan.md) | 只交方案；未实现发单、未下单 |
| 一轮 10–20 个跳空因子 | [16 个因子程序](projects/gap_research/README.md)、[事前方案](reports/gap_round_01/protocol.md) | 已实现、合成流程验证；真实数据待提供 |

## 安装与离线测试

终端 Python 3.11+；本次离线验证使用 Python 3.14.3。CTP 原生依赖请使用有相应发行包或完整编译环境的解释器，不保证 Python 3.14 可安装。

```powershell
python -m pip install -e .
python -m unittest discover -s tests -v
python -m compileall -q projects tests
```

### 行情演示

```powershell
python -m pip install -e ".[ctp]"
Copy-Item projects\ctp_demo\config.example.json projects\ctp_demo\config.local.json
# 用自己的仿真账号、当前前端和未到期合约填写本地配置。
python -m projects.ctp_demo.demo --config projects\ctp_demo\config.local.json
```

默认持续输出直到 `Ctrl+C`。认证、登录、订阅或请求错误明确输出并退出；初始连接超时默认 30 秒。断线由 CTP 自动重连，回调重新认证/登录/订阅。本程序没有发单或撤单逻辑，也不自动确认交易结算单。

### 因子研究

真实数据接口与完整指令见 [研究说明](projects/gap_research/README.md)。以下只验证软件，不是市场数据：

```powershell
python -m projects.gap_research.synthetic --output data\synthetic_new
python -m projects.gap_research.research --data data\synthetic_new\synthetic_prices.csv --calendar data\synthetic_new\synthetic_calendar.csv --protocol data\synthetic_new\synthetic_protocol.json --output reports\runs\synthetic_new --synthetic
```

目录必须是新目录，禁止覆盖已有实验。仓库保存 [本次合成冒烟证据](reports/synthetic_smoke/report.md)，不宣称因子有效。

## 交付边界

- 尚未拿到课程 `llm-wiki.md`、课程原始行情、复权和历史股票池。
- 没有本次 SimNow 登录或持续活跃合约的现场证据；配置中的合约仅为示例，需按运行日确认。
- 未执行任何交易，也不包含复杂表达式、XGBoost 或 AutoGluon 扩展。
- 一轮真实因子挖掘待数据到位；“最多四轮”不是必须四轮，本次不自动扩展搜索。
- `raw`、`data`、账号、CTP 流文件及本地运行结果默认忽略，公开交付仅含原创摘要、代码和明确标注的证据。