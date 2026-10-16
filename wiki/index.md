# 第二讲学习 Wiki

这是来源 → 概念 → 本次实现的双向可追溯学习项目。2026-10-16 已收到用户提供的 LLM Wiki 指南，并据此补齐本项目的维护规则；来源身份和保存边界见 [指南摘要](sources/llm-wiki.md)。

## 维护入口

- [维护规范](schema.md)：目录、证据约定，以及接收、问答回写、核对流程。
- [维护日志](log.md)：按时间追加的资料接收、变更和核验记录。

## 来源

- [作业原题与核对表](sources/assignment.md)：课程要求、账户安全与本次执行授权边界。
- [LLM Wiki 指南](sources/llm-wiki.md)：持久知识库、三层职责和三类维护操作。
- [课程材料状态](sources/course-materials.md)：已收到的指南与尚缺的真实数据。
- [vnpy 源码摘要](sources/vnpy.md)：标准对象、事件、OMS 与主引擎链路。
- [vnpy_ctp 源码摘要](sources/vnpy-ctp.md)：原生接口、认证登录、行情和交易回调。
- [vnpy_ctastrategy 源码摘要](sources/vnpy-ctastrategy.md)：CTA 生命周期与策略引擎。

## 概念

- [三层架构与委托链](concepts/architecture.md)：交易系统各层职责和委托传递路径。
- [标准数据与业务生命周期](concepts/standardization.md)：行情、委托、成交和持仓的统一表达。
- [事件总线、缓存与指令路由](concepts/event-oms-routing.md)：事件传播与指令路由的区别。
- [单标的、投组和价差策略](concepts/strategy-types.md)：三类策略的状态与执行需求。

## 本次实现

- [底层 CTP 演示](code/ctp-demo.md)：只读登录与行情、安全终止和离线验证边界。
- [突破下单待审核方案](code/order-plan.md)：尚未实现或执行的发单设计。
- [跳空因子与评价边界](code/gap-research.md)：冻结研究、历史测试开封和 IC 解释。

[维护日志](log.md)记录材料、变更及核验状态。仓库的源码克隆和行情不纳入版本管理；摘要不得用猜测填补未知事项，实验结果必须链接实际证据。
