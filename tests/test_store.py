"""외부 저장(store) + room_config 원격 모드 테스트 — 네트워크는 mock."""

import os
import unittest
from unittest import mock

from agworld import room_config, store
from agworld.room_config import (
    _default_room_config,
    _reset_remote_cache,
    load_room_config,
    save_room_config,
)

STORE_ENV = {store.STORE_URL_ENV: "https://fake.upstash.io", store.STORE_TOKEN_ENV: "tok"}


class TestStoreConfigured(unittest.TestCase):
    def test_off_without_env(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertFalse(store.configured())

    def test_on_with_both_vars(self):
        with mock.patch.dict(os.environ, STORE_ENV):
            self.assertTrue(store.configured())

    def test_load_returns_none_on_error(self):
        with mock.patch.dict(os.environ, STORE_ENV), \
             mock.patch.object(store, "_request", side_effect=OSError("down")):
            self.assertIsNone(store.load_config())

    def test_save_returns_false_on_error(self):
        with mock.patch.dict(os.environ, STORE_ENV), \
             mock.patch.object(store, "_request", side_effect=OSError("down")):
            self.assertFalse(store.save_config({"rooms": []}))

    def test_load_parses_result(self):
        with mock.patch.dict(os.environ, STORE_ENV), \
             mock.patch.object(store, "_request", return_value={"result": '{"rooms": []}'}):
            self.assertEqual(store.load_config(), {"rooms": []})

    def test_load_empty_result_is_none(self):
        with mock.patch.dict(os.environ, STORE_ENV), \
             mock.patch.object(store, "_request", return_value={"result": None}):
            self.assertIsNone(store.load_config())


class TestRemoteRoomConfig(unittest.TestCase):
    """원격 모드에서 load/save가 store를 쓰고 캐시로 호출을 아끼는지."""

    def setUp(self):
        _reset_remote_cache()
        self._env = mock.patch.dict(os.environ, STORE_ENV)
        self._env.start()
        # 로컬 파일 폴백이 끼어들지 않게 임시 경로
        import tempfile
        from pathlib import Path
        self._tmp = tempfile.TemporaryDirectory()
        self._path = mock.patch.object(
            room_config, "DEFAULT_CONFIG_PATH", Path(self._tmp.name) / "config.json")
        self._path.start()

    def tearDown(self):
        self._path.stop()
        self._env.stop()
        self._tmp.cleanup()
        _reset_remote_cache()

    def test_load_uses_remote_and_caches(self):
        remote = _default_room_config()
        remote["rooms"][0]["title"] = "From Remote"
        with mock.patch.object(store, "load_config", return_value=remote) as m:
            c1 = load_room_config()
            c2 = load_room_config()
        self.assertEqual(c1["rooms"][0]["title"], "From Remote")
        self.assertEqual(m.call_count, 1)   # 두 번째는 캐시
        c1["rooms"][0]["title"] = "mutated"
        self.assertEqual(c2["rooms"][0]["title"], "From Remote")  # 사본이라 오염 없음

    def test_remote_empty_falls_back_to_default(self):
        with mock.patch.object(store, "load_config", return_value=None):
            c = load_room_config()
        self.assertIn("rooms", c)

    def test_save_writes_through(self):
        config = _default_room_config()
        config["rooms"][0]["items"] = [{"item": "sofa", "x": 1, "z": 1}]
        with mock.patch.object(store, "save_config", return_value=True) as m:
            save_room_config(config)
        m.assert_called_once()
        # 저장 직후 로드는 원격 호출 없이 캐시에서
        with mock.patch.object(store, "load_config", side_effect=AssertionError("should not be called")):
            c = load_room_config()
        self.assertEqual(c["rooms"][0]["items"][0]["item"], "sofa")

    def test_explicit_path_bypasses_remote(self):
        from pathlib import Path
        p = Path(self._tmp.name) / "explicit.json"
        with mock.patch.object(store, "load_config", side_effect=AssertionError("should not be called")), \
             mock.patch.object(store, "save_config", side_effect=AssertionError("should not be called")):
            save_room_config(_default_room_config(), p)
            c = load_room_config(p)
        self.assertIn("rooms", c)


if __name__ == "__main__":
    unittest.main()
