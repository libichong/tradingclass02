"""Native CTP callbacks, authentication and quotes only; no order entry."""

from __future__ import annotations

import argparse
from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import re
from threading import Event, RLock
import time
from typing import Mapping, Protocol, TextIO


class Api(Protocol):
    def reqUserLogin(self, request: dict[str, str], request_id: int) -> int: ...
    def reqAuthenticate(self, request: dict[str, str], request_id: int) -> int: ...
    def subscribeMarketData(self, symbol: str) -> int: ...
    def registerFront(self, address: str) -> None: ...
    def init(self) -> None: ...
    def exit(self) -> int: ...


@dataclass(frozen=True)
class Config:
    userid: str = field(repr=False)
    password: str = field(repr=False)
    brokerid: str
    md_address: str
    td_address: str
    appid: str
    auth_code: str = field(repr=False)
    symbols: tuple[str, ...]

    @classmethod
    def load(cls, path: Path) -> Config:
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid configuration JSON at line {exc.lineno}, column {exc.colno}") from None
        if not isinstance(value, dict):
            raise ValueError("Configuration must be a JSON object")
        keys = ("userid", "password", "brokerid", "md_address", "td_address", "appid", "auth_code")
        fields: dict[str, str] = {}
        for key in keys:
            item = value.get(key)
            if not isinstance(item, str) or not item.strip():
                raise ValueError(f"Missing or empty string field: {key}")
            fields[key] = item
        for key in ("md_address", "td_address"):
            if not re.fullmatch(r"tcp://[A-Za-z0-9.-]+:[0-9]{1,5}", fields[key]):
                raise ValueError(f"Invalid tcp address in {key}")
            port = int(fields[key].rsplit(":", 1)[1])
            if not 1 <= port <= 65535:
                raise ValueError(f"Invalid port in {key}")
        symbols = value.get("symbols")
        if not isinstance(symbols, list) or not symbols:
            raise ValueError("symbols must be a nonempty list of current contracts")
        if any(not isinstance(s, str) or not re.fullmatch(r"[A-Za-z]+[0-9]{3,4}", s) for s in symbols):
            raise ValueError("Invalid contract in symbols")
        if len(set(symbols)) != len(symbols):
            raise ValueError("Duplicate symbols")
        return cls(**fields, symbols=tuple(symbols))


class Recorder:
    def __init__(self, stream: TextIO | None = None) -> None:
        self.stream = stream
        self.lock = RLock()

    def emit(self, event: str, **values: object) -> None:
        record = {"received_at": datetime.now(timezone.utc).isoformat(), "event": event, **values}
        line = json.dumps(record, ensure_ascii=False, allow_nan=False)
        with self.lock:
            print(line, flush=True)
            if self.stream is not None:
                self.stream.write(line + "\n")
                self.stream.flush()


def valid_price(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        return None
    number = float(value)
    # CTP uses DBL_MAX for unavailable prices.
    return number if math.isfinite(number) and 0 < number < 1e100 else None


class Session:
    def __init__(self, config: Config, recorder: Recorder) -> None:
        self.config = config
        self.recorder = recorder
        self.lock = RLock()
        self.stop = Event()
        self.failed = False
        self.closed = False
        self.connected = {"md": False, "td": False}
        self.logged_in = {"md": False, "td": False}
        self.authenticated = False
        self.request_ids = {"md": 0, "td": 0}
        self.subscribed: set[str] = set()
        self.tick_counts: dict[str, int] = {}
        self.valid_tick_counts: dict[str, int] = {}
        self.started = time.monotonic()
        self.last_valid_tick: dict[str, float] = {}
        self.apis: dict[str, Api] = {}

    def fail(self, operation: str, code: object) -> None:
        with self.lock:
            self.failed = True
            self.recorder.emit("error", operation=operation, code=code)
            self.stop.set()

    def request(self, channel: str, operation: str) -> None:
        with self.lock:
            if self.stop.is_set() or self.closed:
                return
            self.request_ids[channel] += 1
            request_id = self.request_ids[channel]
            config = self.config
            payload = {"UserID": config.userid, "BrokerID": config.brokerid}
            api = self.apis[channel]
            if operation == "authenticate":
                payload.update(AppID=config.appid, AuthCode=config.auth_code)
                result = api.reqAuthenticate(payload, request_id)
            else:
                payload["Password"] = config.password
                result = api.reqUserLogin(payload, request_id)
            self.recorder.emit("request", channel=channel, operation=operation, request_id=request_id, code=result)
            if result != 0:
                self.fail(f"{channel}.{operation}.send", result)

    def front_connected(self, channel: str) -> None:
        with self.lock:
            if self.closed or self.stop.is_set():
                return
            self.connected[channel] = True
            self.recorder.emit("connected", channel=channel)
            self.request(channel, "authenticate" if channel == "td" else "login")

    def front_disconnected(self, channel: str, reason: int) -> None:
        with self.lock:
            if self.closed:
                return
            self.connected[channel] = False
            self.logged_in[channel] = False
            if channel == "md":
                self.subscribed.clear()
            else:
                self.authenticated = False
            self.recorder.emit("disconnected", channel=channel, reason=reason)
            self.fail(f"{channel}.disconnected", reason)

    def response(self, channel: str, operation: str, error: Mapping[str, object], request_id: int) -> None:
        with self.lock:
            if self.closed or self.stop.is_set():
                return
            if not self.connected[channel] or request_id != self.request_ids[channel]:
                self.recorder.emit("ignored_response", channel=channel, request_id=request_id)
                return
            code = error.get("ErrorID", 0)
            if code != 0:
                self.fail(f"{channel}.{operation}.response", code)
                return
            self.recorder.emit("response", channel=channel, operation=operation, code=code)
            if operation == "authenticate":
                self.authenticated = True
                self.request("td", "login")
            else:
                self.logged_in[channel] = True
                if channel == "md":
                    for symbol in self.config.symbols:
                        result = self.apis["md"].subscribeMarketData(symbol)
                        self.recorder.emit("subscription_request", symbol=symbol, code=result)
                        if result != 0:
                            self.fail("md.subscribe.send", result)
                            break

    def subscription(self, data: Mapping[str, object], error: Mapping[str, object]) -> None:
        with self.lock:
            if self.closed or self.stop.is_set() or not self.logged_in["md"]:
                return
            code = error.get("ErrorID", 0)
            if code != 0:
                self.fail("md.subscribe.response", code)
                return
            symbol = data.get("InstrumentID")
            if isinstance(symbol, str) and symbol in self.config.symbols:
                self.subscribed.add(symbol)
                self.recorder.emit("subscribed", symbol=symbol)
            else:
                self.fail("md.subscribe.unexpected_symbol", "invalid")

    def tick(self, data: Mapping[str, object]) -> None:
        with self.lock:
            if self.closed or self.stop.is_set() or not self.logged_in["md"]:
                return
            symbol = data.get("InstrumentID")
            if not isinstance(symbol, str) or symbol not in self.config.symbols:
                self.fail("md.tick.unexpected_symbol", "invalid")
                return
            self.tick_counts[symbol] = self.tick_counts.get(symbol, 0) + 1
            price = valid_price(data.get("LastPrice"))
            if price is None or not data.get("UpdateTime"):
                self.recorder.emit("invalid_tick", symbol=symbol, reason="invalid last price or missing time")
                return
            self.valid_tick_counts[symbol] = self.valid_tick_counts.get(symbol, 0) + 1
            self.last_valid_tick[symbol] = time.monotonic()
            self.recorder.emit(
                "tick", symbol=symbol, last_price=price,
                bid_price=valid_price(data.get("BidPrice1")),
                ask_price=valid_price(data.get("AskPrice1")),
                trading_day=data.get("TradingDay"), action_day=data.get("ActionDay"),
                exchange_time=data.get("UpdateTime"), milliseconds=data.get("UpdateMillisec"),
                volume=data.get("Volume"),
            )

    def ready(self) -> bool:
        with self.lock:
            return (not self.failed and all(self.connected.values()) and all(self.logged_in.values())
                    and self.authenticated and self.subscribed == set(self.config.symbols))

    def check_health(self, now: float, startup_timeout: float, quote_timeout: float) -> None:
        with self.lock:
            if not self.ready() and now - self.started >= startup_timeout:
                self.fail("startup_timeout", startup_timeout)
            for symbol in self.config.symbols:
                if now - self.last_valid_tick.get(symbol, self.started) >= quote_timeout:
                    self.fail("quote_timeout", symbol)
                    break

    def has_all_quotes(self) -> bool:
        with self.lock:
            return all(self.valid_tick_counts.get(symbol, 0) > 0 for symbol in self.config.symbols)

    def summary(self) -> dict[str, object]:
        with self.lock:
            return {
                "failed": self.failed, "connected": dict(self.connected),
                "logged_in": dict(self.logged_in), "authenticated": self.authenticated,
                "subscribed": sorted(self.subscribed), "tick_counts": dict(self.tick_counts),
                "valid_tick_counts": dict(self.valid_tick_counts), "orders_sent": 0,
            }


def run(config: Config, recorder: Recorder, duration: float | None, startup_timeout: float,
        quote_timeout: float = 60.0) -> int:
    if any(not math.isfinite(value) or value <= 0 for value in (startup_timeout, quote_timeout)) or (
        duration is not None and (not math.isfinite(duration) or duration <= 0)
    ):
        raise ValueError("Timeouts and duration must be finite positive seconds")
    try:
        from vnpy_ctp.api import MdApi, TdApi
    except ImportError as exc:
        raise RuntimeError("Native CTP dependency unavailable; install .[ctp] in a compatible Python environment") from exc

    session = Session(config, recorder)

    class QuoteApi(MdApi):
        def onFrontConnected(self) -> None:
            session.front_connected("md")

        def onFrontDisconnected(self, reason: int) -> None:
            session.front_disconnected("md", reason)

        def onRspUserLogin(self, data: dict, error: dict, reqid: int, last: bool) -> None:
            session.response("md", "login", error, reqid)

        def onRspSubMarketData(self, data: dict, error: dict, reqid: int, last: bool) -> None:
            session.subscription(data, error)

        def onRspError(self, error: dict, reqid: int, last: bool) -> None:
            session.fail("md.callback", error.get("ErrorID", "unknown"))

        def onRtnDepthMarketData(self, data: dict) -> None:
            session.tick(data)

    class TradeApi(TdApi):
        def onFrontConnected(self) -> None:
            session.front_connected("td")

        def onFrontDisconnected(self, reason: int) -> None:
            session.front_disconnected("td", reason)

        def onRspAuthenticate(self, data: dict, error: dict, reqid: int, last: bool) -> None:
            session.response("td", "authenticate", error, reqid)

        def onRspUserLogin(self, data: dict, error: dict, reqid: int, last: bool) -> None:
            session.response("td", "login", error, reqid)

        def onRspError(self, error: dict, reqid: int, last: bool) -> None:
            session.fail("td.callback", error.get("ErrorID", "unknown"))

    created: list[Api] = []
    started = session.started
    try:
        md, td = QuoteApi(), TradeApi()
        session.apis.update(md=md, td=td)
        for channel in ("md", "td"):
            Path(".ctp-flow", channel).mkdir(parents=True, exist_ok=True)
        md.createFtdcMdApi(str(Path(".ctp-flow", "md").resolve()).encode("GBK") + b"\\", False)
        created.append(md)
        td.createFtdcTraderApi(str(Path(".ctp-flow", "td").resolve()).encode("GBK") + b"\\", False)
        created.append(td)
        td.subscribePrivateTopic(2)
        td.subscribePublicTopic(2)
        md.registerFront(config.md_address)
        td.registerFront(config.td_address)
        md.init()
        td.init()
        while not session.stop.wait(0.2):
            now = time.monotonic()
            elapsed = now - started
            session.check_health(now, startup_timeout, quote_timeout)
            if duration is not None and elapsed >= duration:
                if not session.ready() or not session.has_all_quotes():
                    session.fail("duration_ended_without_ready_session_and_quotes", duration)
                break
    except KeyboardInterrupt:
        recorder.emit("stopping", reason="Ctrl+C")
        if not session.ready() or not session.has_all_quotes():
            session.fail("interrupted_without_ready_session_and_quotes", "incomplete")
    except (OSError, RuntimeError, ValueError) as exc:
        session.fail("native_initialization_or_run", type(exc).__name__)
        raise
    finally:
        with session.lock:
            snapshot = session.summary()
            session.closed = True
            session.stop.set()
        for api in reversed(created):
            try:
                result = api.exit()
                if result != 0:
                    session.fail("native_exit", result)
            except (OSError, RuntimeError) as exc:
                session.fail("native_exit", type(exc).__name__)
        snapshot["failed"] = session.failed
        recorder.emit("summary", **snapshot)
    return 1 if session.failed else 0


def positive_seconds(value: str) -> float:
    result = float(value)
    if not math.isfinite(result) or result <= 0:
        raise argparse.ArgumentTypeError("Expected finite positive seconds")
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--duration", type=positive_seconds, help="Default: run until Ctrl+C")
    parser.add_argument("--startup-timeout", type=positive_seconds, default=30.0)
    parser.add_argument("--quote-timeout", type=positive_seconds, default=60.0,
                        help="Maximum seconds without a valid tick for each configured contract")
    parser.add_argument("--live", action="store_true", help="Explicitly allow network login; never enables orders")
    parser.add_argument("--events", type=Path, help="New JSONL file, not overwritten")
    args = parser.parse_args()
    if not args.live:
        parser.error("Network access disabled by default; use --live only with your SimNow configuration")
    recorder = Recorder()
    try:
        config = Config.load(args.config)
        if args.events:
            args.events.parent.mkdir(parents=True, exist_ok=True)
            with args.events.open("x", encoding="utf-8") as stream:
                return run(config, Recorder(stream), args.duration, args.startup_timeout, args.quote_timeout)
        return run(config, recorder, args.duration, args.startup_timeout, args.quote_timeout)
    except (OSError, ValueError, RuntimeError) as exc:
        recorder.emit("error", operation="main", error_type=type(exc).__name__,
                      detail="Check local configuration, paths and native dependency; raw exception suppressed")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
