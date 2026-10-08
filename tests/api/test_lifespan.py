import asyncio
import signal
import sqlite3
import threading

import pytest

from tests.fakes import FakeVehicle


def _assert_store_closed(client):
    with pytest.raises(sqlite3.ProgrammingError):
        client.store.count()


def test_supervisor_started_and_cancelled(make_client):
    started = threading.Event()
    cancelled = threading.Event()

    async def supervise():
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    vehicle = FakeVehicle()
    client, _ = make_client(vehicle, supervise)
    with client:
        assert started.wait(timeout=2)

    assert cancelled.wait(timeout=2)
    assert vehicle.link.closed
    _assert_store_closed(client)


def test_no_supervisor_leaves_app_working(make_client):
    vehicle = FakeVehicle()
    client, _ = make_client(vehicle)
    with client:
        assert client.get("/vehicle/state").status_code == 200

    assert vehicle.link.closed
    _assert_store_closed(client)


def test_supervisor_crash_signals_shutdown(make_client, monkeypatch):
    signalled = threading.Event()
    monkeypatch.setattr(signal, "raise_signal", lambda sig: signalled.set())

    async def supervise():
        raise RuntimeError("bridge died")

    vehicle = FakeVehicle()
    client, _ = make_client(vehicle, supervise)
    with client:
        assert signalled.wait(timeout=2)

    assert vehicle.link.closed
    _assert_store_closed(client)
