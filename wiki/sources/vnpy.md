# 源码摘要：vnpy

来源：[vnpy/vnpy](https://github.com/vnpy/vnpy)，固定提交 `c6e231caf32b7fc97e6459817fff66458cf7e7c4`。本地下载位置与日期见 [提交记录](../../reports/source_commits.json)。

阅读入口：

- [event/engine.py](https://github.com/vnpy/vnpy/blob/c6e231caf32b7fc97e6459817fff66458cf7e7c4/vnpy/event/engine.py)：`Event` 保存类型和载荷，`EventEngine` 用队列和独立线程分发；定时线程产生 `eTimer`。按类型处理器先运行，再运行通用处理器。
- [trader/object.py](https://github.com/vnpy/vnpy/blob/c6e231caf32b7fc97e6459817fff66458cf7e7c4/vnpy/trader/object.py)：行情、订单、成交、持仓、账户对象；跨网关标识与活跃订单判定。
- [trader/engine.py](https://github.com/vnpy/vnpy/blob/c6e231caf32b7fc97e6459817fff66458cf7e7c4/vnpy/trader/engine.py)：`MainEngine` 装配网关/应用/引擎，按网关名路由；`OmsEngine` 缓存最新回报并维护活跃订单和开平转换器。

关键理解：事件总线不是持久消息队列，也不自动提供处理器异常隔离。OMS 是内存最新状态，不是完整审计账本。`send_order` 返回标识不等于成交；未找到网关时为空串，调用方不能当成功。

消化：[架构](../concepts/architecture.md)、[标准化](../concepts/standardization.md)、[事件与 OMS](../concepts/event-oms-routing.md)。本次不安装完整 GUI 框架，不声称通读整个仓库。
