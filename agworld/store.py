"""외부 키-값 저장 (Upstash Redis REST API) — room_config 영속화용.

무료 Render는 디스크가 휘발성이라 재배포/슬립 시 가구 배치가 날아간다.
AGWORLD_STORE_URL + AGWORLD_STORE_TOKEN이 설정돼 있으면 config를 Upstash에
저장해 재배포 후에도 복원된다. stdlib(urllib)만 사용 — 의존성 0 유지.

Upstash REST:
    GET  {url}/get/{key}   → {"result": "<value|null>"}
    POST {url}/set/{key}   (본문 = 값)  → {"result": "OK"}
"""

from __future__ import annotations

import json
import os
import urllib.request

STORE_URL_ENV = "AGWORLD_STORE_URL"
STORE_TOKEN_ENV = "AGWORLD_STORE_TOKEN"
CONFIG_KEY = "room_config"
TIMEOUT = 5  # 초 — 저장소 장애가 서버를 멈추지 않게


def configured() -> bool:
    """원격 저장이 켜져 있는가."""
    return bool(os.environ.get(STORE_URL_ENV) and os.environ.get(STORE_TOKEN_ENV))


def _request(method: str, path: str, body: bytes | None = None) -> dict:
    url = os.environ[STORE_URL_ENV].rstrip("/") + path
    req = urllib.request.Request(
        url, data=body, method=method,
        headers={"Authorization": "Bearer " + os.environ[STORE_TOKEN_ENV]},
    )
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return json.loads(r.read().decode("utf-8"))


def load_config() -> dict | None:
    """원격에서 config 로드. 없거나 실패하면 None (호출부가 폴백)."""
    try:
        result = _request("GET", f"/get/{CONFIG_KEY}").get("result")
        return json.loads(result) if result else None
    except Exception as e:
        print(f"[store] remote load failed: {e}", flush=True)
        return None


def save_config(config: dict) -> bool:
    """원격에 config 저장. 실패해도 서버는 계속 동작(로컬 파일이 1차)."""
    try:
        body = json.dumps(config, ensure_ascii=False).encode("utf-8")
        _request("POST", f"/set/{CONFIG_KEY}", body)
        return True
    except Exception as e:
        print(f"[store] remote save failed: {e}", flush=True)
        return False
