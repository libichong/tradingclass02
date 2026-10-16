# 源码摘要：vnpy_ctastrategy

来源：[vnpy/vnpy_ctastrategy](https://github.com/vnpy/vnpy_ctastrategy)，固定提交 `7a8768de9784dda35a7b261a7ade1dbfbff50919`，见 [提交记录](../../reports/source_commits.json)。

阅读入口：

- [template.py](https://github.com/vnpy/vnpy_ctastrategy/blob/7a8768de9784dda35a7b261a7ade1dbfbff50919/vnpy_ctastrategy/template.py)：`CtaTemplate` 的 `inited`、`trading`、`pos`；初始化、启停、行情、委托和成交回调；买卖/开平辅助方法。
- [engine.py](https://github.com/vnpy/vnpy_ctastrategy/blob/7a8768de9784dda35a7b261a7ade1dbfbff50919/vnpy_ctastrategy/engine.py)：按合约分发行情，按订单标识映射策略；先成交去重和更新策略持仓，再回调；构造订单后经主引擎开平转换与网关路由；策略回调异常写日志并停止策略。

关键理解：初始化完成不等于允许交易；策略本地持仓不替代柜台对账；停止策略不必然意味着柜台委托全部撤销。订单映射、重复成交过滤和事件顺序属于引擎职责，信号/仓位规则属于策略职责。

本模块阅读覆盖单标的 CTA。投组与价差的差异是 [概念比较](../concepts/strategy-types.md)，没有声称安装或测试对应应用。
