# 数据结构与业务流程标准化

数据标准化：`TickData` 统一报价和成交统计，`OrderData` 统一委托状态，`TradeData` 描述每次实际成交，`PositionData` 表示方向/今昨/冻结持仓，`AccountData` 表示资金。`OrderRequest` 与回报对象分离。

全局标识：合约 `symbol.exchange`、订单 `gateway.orderid`、成交 `gateway.tradeid`，避免不同柜台局部编号冲突。一个订单可对应多次成交，不能用订单数替代成交手数。

业务标准化：连接 →（认证）→ 登录 → 查询/订阅 → 请求 → 回报。断线只清除会话就绪状态，不证明未成交；重连需恢复订阅和交易对账。生产系统还须处理结算确认、查询节流、合约规格和开平转换。

时间与价格：夜盘交易日可能不是自然日；时间要保留交易所时刻和本地接收时刻。缺失哨兵不得当报价；精度、最小变动单位、涨跌停、乘数应取合约资料而非硬编码。

来源：[标准对象](../sources/vnpy.md)、[柜台转换](../sources/vnpy-ctp.md)。使用：[架构](architecture.md)、[下单方案](../code/order-plan.md)。
