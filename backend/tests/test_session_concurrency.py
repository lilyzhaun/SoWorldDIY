import json

import pytest
from pytest import MonkeyPatch

from app import main
from app.cache_store import MemoryCache, profile_cache_key
from app.session_store import (
    _CREATE_SCRIPT,
    _ROTATE_SCRIPT,
    RedisSessionStore,
    SessionConflictError,
)
from tests.contract_support import (
    FakeResponse,
    _authed_session,
    _install_fake_store,
    invoke,
)
from tests.test_redis_migrate import disposable_redis_pair as disposable_redis_pair


class ScriptRedis:
    """Faithful snapshots for unit tests; Lua is also exercised by live Redis tests."""

    def __init__(self):
        self.data = {}

    def get(self, name):
        return self.data.get(name)

    def setex(self, name, ttl, value):
        self.data[name] = value

    def delete(self, *names):
        count = sum(name in self.data for name in names)
        for name in names:
            self.data.pop(name, None)
        return count

    def eval(self, script, numkeys, *args):
        keys, values = args[:numkeys], args[numkeys:]
        if script == _CREATE_SCRIPT:
            if keys[0] in self.data:
                return 0
            self.data[keys[0]] = values[0]
            return 1
        old = self.data.get(keys[0])
        if old is None or json.loads(old).get("_revision", 0) != int(values[0]):
            return 0
        if script == _ROTATE_SCRIPT:
            if keys[1] in self.data:
                return 0
            self.data[keys[1]] = values[1]
            del self.data[keys[0]]
        else:
            self.data[keys[0]] = values[1]
        return 1


def test_stale_writes_cannot_restore_revoked_or_removed_accounts():
    redis = ScriptRedis()
    store = RedisSessionStore(redis, "session:", 60, "audit_")
    ctx = store.create({"accounts": {"first": {}, "second": {}}})
    stale = store.load(ctx.sid)
    del ctx.data["accounts"]["first"]
    store.save(ctx.sid, ctx.data)
    with pytest.raises(SessionConflictError):
        store.save(ctx.sid, stale)
    assert "first" not in store.load(ctx.sid)["accounts"]
    stale = store.load(ctx.sid)
    store.delete(ctx.sid)
    with pytest.raises(SessionConflictError):
        store.save(ctx.sid, stale)
    assert store.load(ctx.sid) is None


def test_legacy_sessions_upgrade_and_rotation_revokes_old_sid():
    redis = ScriptRedis()
    redis.data["session:legacy"] = '{"accounts":{"account":{}}}'
    store = RedisSessionStore(redis, "session:", 60, "audit_")
    data = store.load("legacy")
    store.save("legacy", data)
    assert data["_revision"] == 1
    rotated = store.rotate("legacy", data)
    assert store.load("legacy") is None
    assert store.load(rotated.sid)["accounts"] == {"account": {}}
    with pytest.raises(SessionConflictError):
        store.rotate("legacy", data)


def test_shared_account_profile_does_not_leak_session_accounts(
    monkeypatch: MonkeyPatch,
):
    store = _install_fake_store(monkeypatch)
    cache = MemoryCache()
    monkeypatch.setattr(main, "get_cache", cache.get)
    monkeypatch.setattr(main, "set_cache", cache.set)
    monkeypatch.setattr(
        main,
        "make_3hk_request",
        lambda **kwargs: FakeResponse(
            200,
            {"subscriptions": [{"primaryMsisdn": "10000000", "subscriptionId": "s"}]},
        ),
    )
    first, _ = _authed_session(
        store,
        sid="first",
        accounts={"shared": {"cookies": {}}, "private": {"cookies": {}}},
    )
    second, _ = _authed_session(
        store, sid="second", accounts={"shared": {"cookies": {}}}
    )
    a = invoke("/api/profile?account_id=shared", headers={"cookie": f"session={first}"})
    b = invoke(
        "/api/profile?account_id=shared", headers={"cookie": f"session={second}"}
    )
    assert len(a.json["data"]["available_accounts"]) == 2
    assert b.json["data"]["available_accounts"] == [
        {"identifier": "shared", "active": True, "subBrand": "THREE"}
    ]
    assert (
        "available_accounts"
        not in cache.get(profile_cache_key(first, "shared"))["data"]
    )
    assert store.load(first) is not store.sessions[first]


def test_cache_expiration_cleanup_and_capacity():
    cache = MemoryCache(max_entries=2)
    cache.set("expired", {"secret": "synthetic"}, timeout=0)
    cache.set("a", {})
    assert "expired" not in cache._store
    cache.set("b", {})
    cache.set("c", {})
    assert len(cache._store) == 2
    assert cache.get("a") is None


def test_live_redis_cas_rotation_and_acl(disposable_redis_pair):
    import redis

    cfg = disposable_redis_pair
    client = redis.Redis(
        host="127.0.0.1",
        port=cfg["dst_port"],
        username="3hk-app",
        password=cfg["acl_password"],
        decode_responses=True,
    )
    store = RedisSessionStore(client, "session:", 60, "audit_")
    ctx = store.create({"accounts": {"first": {}, "second": {}}})
    stale = store.load(ctx.sid)
    del ctx.data["accounts"]["first"]
    store.save(ctx.sid, ctx.data)
    with pytest.raises(SessionConflictError):
        store.save(ctx.sid, stale)
    rotated = store.rotate(ctx.sid, ctx.data)
    assert store.load(ctx.sid) is None
    assert store.load(rotated.sid)["accounts"] == {"second": {}}
    store.delete(rotated.sid)
    with pytest.raises(SessionConflictError):
        store.save(rotated.sid, rotated.data)
    client.close()


def test_live_redis_only_one_concurrent_rotation_succeeds(disposable_redis_pair):
    import threading
    from concurrent.futures import ThreadPoolExecutor

    import redis

    cfg = disposable_redis_pair
    client = redis.Redis(
        host="127.0.0.1",
        port=cfg["dst_port"],
        username="3hk-app",
        password=cfg["acl_password"],
        decode_responses=True,
    )
    store = RedisSessionStore(client, "session:", 60, "audit_")
    original = store.create({"accounts": {"original": {}}})
    barrier = threading.Barrier(2, timeout=3)

    def rotate(account):
        data = store.load(original.sid)
        data["accounts"][account] = {}
        barrier.wait()
        try:
            return store.rotate(original.sid, data)
        except SessionConflictError:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(rotate, ["first", "second"]))
    successes = [ctx for ctx in results if ctx is not None]
    assert len(successes) == 1
    assert store.load(original.sid) is None
    assert len(store.load(successes[0].sid)["accounts"]) == 2
    client.close()


def test_slow_prelogin_response_cannot_overwrite_new_session(monkeypatch):
    import asyncio
    import time

    import anyio
    import httpx

    from tests.contract_support import isolated_sessions

    store = _install_fake_store(monkeypatch)
    ctx = store.create(
        {
            "csrf_token": "tok",
            "accounts": {"old@example.test": {"cookies": {}, "sub_brand": "THREE"}},
            "last_session_refresh": time.time(),
        }
    )
    monkeypatch.setattr(main, "verify_auth_code", lambda *_: (True, "OK"))
    monkeypatch.setattr(
        main,
        "get_isolated_session",
        isolated_sessions(
            [FakeResponse(200, {"subBrand": "THREE"}), FakeResponse(204)]
        ),
    )

    async def scenario():
        app = main.create_app()
        started, release = asyncio.Event(), asyncio.Event()

        @app.get("/test-slow")
        async def slow():
            started.set()
            await asyncio.wait_for(release.wait(), 3)
            return {"status": "success"}

        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test.local"
        ) as client:
            client.cookies.set("session", ctx.sid, domain="test.local", path="/")
            pending = asyncio.create_task(client.get("/test-slow"))
            await asyncio.wait_for(started.wait(), 3)
            login = await client.post(
                "/login",
                headers={"x-csrf-token": "tok"},
                data={
                    "login_type": "password",
                    "identifier": "new+tag@example.test",
                    "password": "synthetic",
                    "auth_code": "synthetic",
                },
            )
            assert login.status_code == 200
            assert login.json()["redirect"] == "/main/new%2Btag@example.test"
            new_sid = client.cookies.get("session")
            release.set()
            stale = await pending
            assert not stale.headers.get_list("set-cookie")
            assert client.cookies.get("session") == new_sid != ctx.sid
            assert store.load(new_sid)["accounts"]["new+tag@example.test"]

    anyio.run(scenario)
