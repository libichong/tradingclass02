# 底层 CTP 行情与交易登录演示

[demo.py](demo.py) 直接继承 `vnpy_ctp.api.MdApi` / `TdApi`，没有经由 `MainEngine` 或 `CtpGateway`。

## 配置与运行

1. 在兼容的 Python 环境安装 `python -m pip install -e ".[ctp]"`。依赖固定到阅读过的 `vnpy_ctp 6.7.11.5`；其 API 创建方法需要流目录和仿真模式两个参数。
2. 复制 [占位配置](config.example.json) 为 `config.local.json`，填写自己的 SimNow 配置。不要使用公共示例账号，不要提交密码和授权码。
3. 从仓库根目录运行：

```powershell
python -m projects.ctp_demo.demo --config projects\ctp_demo\config.local.json
```

程序默认前台持续运行，`Ctrl+C` 释放接口。输出每条有效行情的本地 UTC 接收时刻、合约、交易日、自然日、柜台时间、最新价、买卖价及累计成交量。缺失报价显示 `null`，无效最新价记录为 `invalid_tick`，不会伪装成正常行情。

限时现场复验：

```powershell
python -m projects.ctp_demo.demo --config projects\ctp_demo\config.local.json --duration 60 --startup-timeout 30 --events reports\runs\ctp_live_01\events.jsonl
```

事件文件以独占创建模式打开，已有文件会报错。只有两个通道登录、交易认证、全部订阅成功且至少一条有效行情时，限时运行才成功退出。汇总记录逐合约回调数、有效数、当前连接状态和 `orders_sent=0`。订阅成功或仅一条快照不等于合约持续活跃；应检查多个交易所时间点与累计成交量变化。

## 生命周期与错误

- MD 连接 → 登录 → 逐合约订阅 → 行情。
- TD 连接 → 终端认证 → 登录；不查询账户，不自动确认结算，不发单、不撤单。
- CTP SDK 负责连接恢复；断线清除对应登录状态，MD 清除订阅确认，TD 清除认证。重连回调再次走完整流程。
- SDK 请求返回非零、柜台返回错误、订阅失败都会输出错误码并停止。原始响应与请求载荷不写日志，避免账号信息泄露。
- 初始就绪超时退出；成功连接后的断线默认等待 SDK 重连，持续运行模式不保证无限等待期间有行情。
- API 流目录在忽略的 `.ctp-flow` 中；不要并发启动多个实例共用此目录。

示例 `au2612`、`ag2612`、`cu2611`、`rb2701` 只展示跨品种订阅格式，**没有经过当日成交量排名核验**，且会到期。运行前按 SimNow 当前合约和时段选择。

## 已验证与未验证

[离线测试](../../tests/test_ctp_demo.py) 验证认证顺序、返回码、断线重订阅、价格过滤、默认持续运行逻辑和清理流程。不使用真实账户。

本次尚未验证原生发行包可安装、真实前端可连接、回调 ABI、真实行情活跃度和长时间稳定性。不能把离线替身测试称为联网成功。
