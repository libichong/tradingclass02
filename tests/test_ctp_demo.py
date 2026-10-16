from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import tempfile
from types import ModuleType
import unittest
from unittest.mock import patch

from projects.ctp_demo.demo import Config, Recorder, Session, main, run, valid_price


class FakeApi:
    def __init__(self) -> None:
        self.calls: list[tuple[str, object]] = []
        self.result = 0

    def reqUserLogin(self, request: dict, request_id: int) -> int:
        self.calls.append(("login", request_id))
        return self.result

    def reqAuthenticate(self, request: dict, request_id: int) -> int:
        self.calls.append(("authenticate", request_id))
        return self.result

    def subscribeMarketData(self, symbol: str) -> int:
        self.calls.append(("subscribe", symbol))
        return self.result

    def registerFront(self, address: str) -> None:
        self.calls.append(("front", address))

    def init(self) -> None:
        self.calls.append(("init", None))

    def exit(self) -> int:
        self.calls.append(("exit", None))
        return 0


class SessionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.output = StringIO()
        self.redirect = redirect_stdout(self.output)
        self.redirect.__enter__()
        self.addCleanup(self.redirect.__exit__, None, None, None)
        self.config = Config("user", "private", "9999", "tcp://localhost:1", "tcp://localhost:2",
                             "app", "secret", ("au2612", "ag2612"))
        self.session = Session(self.config, Recorder(self.output))
        self.md, self.td = FakeApi(), FakeApi()
        self.session.apis.update(md=self.md, td=self.td)

    def login(self) -> None:
        self.session.front_connected("md")
        self.session.response("md", "login", {}, 1)
        self.session.front_connected("td")
        self.session.response("td", "authenticate", {"ErrorID": 0}, 1)
        self.session.response("td", "login", {}, 2)
        for symbol in self.config.symbols:
            self.session.subscription({"InstrumentID": symbol}, {})

    def test_auth_login_subscription_and_no_orders(self) -> None:
        self.login()
        self.assertTrue(self.session.ready())
        self.assertEqual(self.td.calls, [("authenticate", 1), ("login", 2)])
        self.assertEqual(self.md.calls, [("login", 1), ("subscribe", "au2612"), ("subscribe", "ag2612")])
        self.assertEqual(self.session.summary()["orders_sent"], 0)
        self.assertNotIn("private", self.output.getvalue())
        self.assertNotIn("secret", repr(self.config))

    def test_disconnect_is_terminal_and_never_relogs_in(self) -> None:
        self.login()
        self.session.front_disconnected("md", 4097)
        self.session.front_disconnected("td", 4097)
        self.assertFalse(self.session.ready())
        self.assertFalse(self.session.authenticated)
        self.assertEqual(self.session.subscribed, set())
        previous_md = list(self.md.calls)
        previous_td = list(self.td.calls)
        self.session.front_connected("md")
        self.session.response("md", "login", {}, 1)
        self.assertFalse(self.session.logged_in["md"])
        self.session.response("md", "login", {}, 2)
        self.assertFalse(self.session.logged_in["md"])
        self.session.front_connected("td")
        self.assertEqual(self.md.calls, previous_md)
        self.assertEqual(self.td.calls, previous_td)
        self.assertTrue(self.session.failed)
        self.assertTrue(self.session.stop.is_set())

    def test_quote_timeout_is_per_contract_and_invalid_ticks_do_not_refresh(self) -> None:
        self.login()
        self.session.started = 0
        with patch("projects.ctp_demo.demo.time.monotonic", return_value=9):
            self.session.tick({"InstrumentID": "au2612", "LastPrice": 900, "UpdateTime": "09:00:00"})
            self.session.tick({"InstrumentID": "ag2612", "LastPrice": 0, "UpdateTime": "09:00:00"})
        self.assertFalse(self.session.has_all_quotes())
        self.session.check_health(10, 30, 10)
        self.assertTrue(self.session.failed)
        self.assertIn('"operation": "quote_timeout"', self.output.getvalue())

    def test_startup_timeout_and_stale_quotes(self) -> None:
        self.session.check_health(self.session.started + 30, 30, 60)
        self.assertTrue(self.session.failed)
        self.assertIn('"operation": "startup_timeout"', self.output.getvalue())

    def test_previously_valid_quotes_expire_at_deadline(self) -> None:
        self.login()
        with patch("projects.ctp_demo.demo.time.monotonic", return_value=100):
            for symbol in self.config.symbols:
                self.session.tick({"InstrumentID": symbol, "LastPrice": 900, "UpdateTime": "09:00:00"})
        self.session.check_health(109, 30, 10)
        self.assertFalse(self.session.failed)
        self.session.check_health(110, 30, 10)
        self.assertTrue(self.session.failed)

    def test_disconnect_during_local_shutdown_does_not_report_failure(self) -> None:
        self.session.closed = True
        self.session.front_disconnected("md", 4097)
        self.assertFalse(self.session.failed)

    def test_userid_is_not_in_repr(self) -> None:
        self.assertNotIn("userid=", repr(self.config))

    def test_network_requires_explicit_live_flag(self) -> None:
        with patch("sys.argv", ["demo", "--config", "unused.local.json"]), \
                patch("projects.ctp_demo.demo.run") as execute, \
                patch("sys.stderr", StringIO()):
            with self.assertRaises(SystemExit) as error:
                main()
        self.assertEqual(error.exception.code, 2)
        execute.assert_not_called()

    def test_exception_details_do_not_leak_configuration(self) -> None:
        with patch("sys.argv", ["demo", "--config", "unused.local.json", "--live"]), \
                patch("projects.ctp_demo.demo.Config.load", side_effect=ValueError("private user secret")):
            self.assertEqual(main(), 1)
        self.assertNotIn("private", self.output.getvalue())
        self.assertNotIn("secret", self.output.getvalue())
        self.assertIn('"error_type": "ValueError"', self.output.getvalue())

    def test_immediate_and_callback_failures_stop(self) -> None:
        self.md.result = -1
        self.session.front_connected("md")
        self.assertTrue(self.session.failed)
        self.assertTrue(self.session.stop.is_set())
        self.session.front_connected("td")
        self.assertEqual(self.td.calls, [])

    def test_login_error_does_not_subscribe(self) -> None:
        self.session.front_connected("md")
        self.session.response("md", "login", {"ErrorID": 3}, 1)
        self.assertFalse(self.session.logged_in["md"])
        self.assertTrue(self.session.failed)
        self.assertEqual(len(self.md.calls), 1)

    def test_subscription_error_stops(self) -> None:
        self.login()
        self.session.subscription({}, {"ErrorID": 7})
        self.assertTrue(self.session.failed)

    def test_tick_filtering_and_counts(self) -> None:
        self.login()
        self.session.tick({"InstrumentID": "au2612", "LastPrice": 1.7976931348623157e308, "UpdateTime": "09:00:00"})
        self.session.tick({"InstrumentID": "au2612", "LastPrice": 900.0, "UpdateTime": "09:00:01", "Volume": 12})
        self.assertEqual(self.session.tick_counts, {"au2612": 2})
        self.assertEqual(self.session.valid_tick_counts, {"au2612": 1})
        self.assertIn('"event": "invalid_tick"', self.output.getvalue())

    def test_price_sentinels(self) -> None:
        for value in (0, -1, float("nan"), float("inf"), 1.797e308, None, True, "900"):
            self.assertIsNone(valid_price(value))
        self.assertEqual(valid_price(900), 900.0)

    def test_config_validation(self) -> None:
        value = dict(userid="u", password="p", brokerid="b", md_address="tcp://host:1",
                     td_address="tcp://host:2", appid="a", auth_code="c", symbols=["au2612"])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.local.json"
            path.write_text(json.dumps(value), encoding="utf-8")
            self.assertEqual(Config.load(path).symbols, ("au2612",))
            value["symbols"] = ["au2612", "au2612"]
            path.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Duplicate"):
                Config.load(path)
        with self.assertRaisesRegex(ValueError, "Missing or empty"):
            Config.load(Path("projects") / "ctp_demo" / "config.example.json")

    def test_malformed_config_does_not_include_raw_values_in_error(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.local.json"
            path.write_text('{"userid": "private", "password": "secret", BROKEN}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Invalid configuration JSON") as error:
                Config.load(path)
        self.assertNotIn("private", str(error.exception))
        self.assertNotIn("secret", str(error.exception))

    def native_module(self, fail_init: bool = False, bad_exit: bool = False,
                      missing_symbol: str | None = None) -> tuple[ModuleType, list]:
        instances: list = []

        class NativeBase(FakeApi):
            def __init__(self) -> None:
                super().__init__()
                instances.append(self)

            def createFtdcMdApi(self, path: bytes, production_mode: bool) -> None:
                self.calls.append(("create_md", production_mode))

            def createFtdcTraderApi(self, path: bytes, production_mode: bool) -> None:
                self.calls.append(("create_td", production_mode))

            def subscribePrivateTopic(self, mode: int) -> None:
                self.calls.append(("private", mode))

            def subscribePublicTopic(self, mode: int) -> None:
                self.calls.append(("public", mode))

            def init(self) -> None:
                if fail_init:
                    raise RuntimeError("fixture initialization failure")
                self.onFrontConnected()

            def reqAuthenticate(self, request: dict, request_id: int) -> int:
                self.onRspAuthenticate({}, {}, request_id, True)
                return 0

            def reqUserLogin(self, request: dict, request_id: int) -> int:
                self.onRspUserLogin({}, {}, request_id, True)
                return 0

            def subscribeMarketData(self, symbol: str) -> int:
                self.onRspSubMarketData({"InstrumentID": symbol}, {}, 0, True)
                if symbol != missing_symbol:
                    self.onRtnDepthMarketData({"InstrumentID": symbol, "LastPrice": 900, "UpdateTime": "09:00:00"})
                return 0

            def exit(self) -> int:
                super().exit()
                return -1 if bad_exit else 0

        module = ModuleType("vnpy_ctp.api")
        module.MdApi = NativeBase
        module.TdApi = NativeBase
        return module, instances

    def test_duration_run_and_cleanup(self) -> None:
        module, instances = self.native_module()
        with patch.dict("sys.modules", {"vnpy_ctp.api": module}), \
                patch("projects.ctp_demo.demo.Path.mkdir"), \
                patch("projects.ctp_demo.demo.time.monotonic", side_effect=[0, 0, 0, 1]), \
                patch("projects.ctp_demo.demo.Event.wait", return_value=False):
            self.assertEqual(run(self.config, Recorder(), 0.5, 30), 0)
        self.assertTrue(all(api.calls[-1] == ("exit", None) for api in instances))
        self.assertIn('"orders_sent": 0', self.output.getvalue())

    def test_duration_cannot_succeed_with_quotes_from_only_one_contract(self) -> None:
        module, _ = self.native_module(missing_symbol="ag2612")
        with patch.dict("sys.modules", {"vnpy_ctp.api": module}), \
                patch("projects.ctp_demo.demo.Path.mkdir"), \
                patch("projects.ctp_demo.demo.time.monotonic", side_effect=[0, 0, 1]), \
                patch("projects.ctp_demo.demo.Event.wait", return_value=False):
            self.assertEqual(run(self.config, Recorder(), 0.5, 30), 1)
        self.assertIn('"operation": "duration_ended_without_ready_session_and_quotes"', self.output.getvalue())

    def test_default_run_does_not_exit_when_ready(self) -> None:
        module, instances = self.native_module()
        with patch.dict("sys.modules", {"vnpy_ctp.api": module}), \
                patch("projects.ctp_demo.demo.Path.mkdir"), \
                patch("projects.ctp_demo.demo.time.monotonic", side_effect=[0, 90, 90, 100]), \
                patch("projects.ctp_demo.demo.Event.wait", side_effect=[False, KeyboardInterrupt]) as wait:
            self.assertEqual(run(self.config, Recorder(), None, 30), 0)
            self.assertEqual(wait.call_count, 2)
        self.assertTrue(all(api.calls[-1] == ("exit", None) for api in instances))
        self.assertIn("Ctrl+C", self.output.getvalue())

    def test_native_failure_is_not_success_shaped(self) -> None:
        module, instances = self.native_module(fail_init=True)
        with patch.dict("sys.modules", {"vnpy_ctp.api": module}), \
                patch("projects.ctp_demo.demo.Path.mkdir"):
            with self.assertRaisesRegex(RuntimeError, "fixture"):
                run(self.config, Recorder(), 1, 30)
        self.assertTrue(all(api.calls[-1] == ("exit", None) for api in instances))
        self.assertIn('"failed": true', self.output.getvalue())

    def test_native_exit_failure_returns_failure(self) -> None:
        module, _ = self.native_module(bad_exit=True)
        with patch.dict("sys.modules", {"vnpy_ctp.api": module}), \
                patch("projects.ctp_demo.demo.Path.mkdir"), \
                patch("projects.ctp_demo.demo.time.monotonic", side_effect=[0, 0, 0, 1]), \
                patch("projects.ctp_demo.demo.Event.wait", return_value=False):
            self.assertEqual(run(self.config, Recorder(), 0.5, 30), 1)
        self.assertIn('"operation": "native_exit"', self.output.getvalue())


if __name__ == "__main__":
    unittest.main()
