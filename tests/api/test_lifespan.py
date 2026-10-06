import asyncio
import signal
import threading

from fastapi.testclient import TestClient

from tests.fakes import FakeVehicle
from uav_gc.api import create_app


def test_supervisor_started_and_cancelled():
    started = threading.Event()
    cancelled = threading.Event()

    async def supervise():
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()

    vehicle = FakeVehicle()
    with TestClient(create_app(vehicle, supervise)):
        assert started.wait(timeout=2)

    assert cancelled.wait(timeout=2)
    assert vehicle.link.closed


def test_no_supervisor_leaves_app_working():
    vehicle = FakeVehicle()
    with TestClient(create_app(vehicle)) as client:
        assert client.get("/vehicle/state").status_code == 200

    assert vehicle.link.closed


def test_supervisor_crash_signals_shutdown(monkeypatch):
    signalled = threading.Event()
    monkeypatch.setattr(signal, "raise_signal", lambda sig: signalled.set())

    async def supervise():
        raise RuntimeError("bridge died")

    vehicle = FakeVehicle()
    with TestClient(create_app(vehicle, supervise)):
        assert signalled.wait(timeout=2)

    assert vehicle.link.closed
