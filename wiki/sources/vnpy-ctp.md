# 源码摘要：vnpy_ctp

来源：[vnpy/vnpy_ctp](https://github.com/vnpy/vnpy_ctp)，固定提交 `1be9bfb5292208e5c258cc769c90be4abe83f9a9`，包版本 `6.7.11.5`。下载记录见 [提交号](../../reports/source_commits.json)。

阅读 [ctp_gateway.py](https://github.com/vnpy/vnpy_ctp/blob/1be9bfb5292208e5c258cc769c90be4abe83f9a9/vnpy_ctp/gateway/ctp_gateway.py) 中 `CtpMdApi` / `CtpTdApi` 和底层绑定：

- MD 前端连接后登录，登录成功重新订阅已请求合约；订阅回报和行情推送是两种回调。
- TD 前端连接后认证，再登录；网关登录成功会确认结算并继续查询。本次极简演示仅登录，不照搬后续交易流程。
- 网关根据合约信息将字段转换为 `TickData`，处理自然日/交易日差异和缺失价格。CTP 最大浮点数是缺失哨兵，不是实际价格。
- 发单本地返回码仅反映请求发送；后续订单、成交、拒单回报才决定柜台状态。当前源码用锁保证本地提交事件先于相关柜台回报入队。
- `createFtdcMdApi` / `createFtdcTraderApi` 的当前原生绑定需要流路径与模式两个参数；`subscribeMarketData` 支持单合约和列表。示例测试与绑定可能存在版本差异，不能只照抄旧脚本。

本次 [底层实现](../code/ctp-demo.md) 不依赖网关标准化，也不等待查询合约后才打印原生字段；时间字段原样记录，不把夜盘交易日冒充自然日。ABI 和现场回调仍待真实原生环境验证。
