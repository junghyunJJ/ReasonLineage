"""The shared plumbing for CLI backends."""

import asyncio
import os
import signal

import pytest

from reasonlineage.backends._subprocess import SubprocessBackend
from reasonlineage.backends.base import BackendError


def alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


def test_a_cancelled_call_kills_its_process(tmp_path):
    pidfile = tmp_path / "pid"
    backend = SubprocessBackend("x", "sh", max_concurrency=1, retries=0)

    async def cancel_mid_call() -> bool:
        call = asyncio.ensure_future(backend._exec(["sh", "-c", f"echo $$ > {pidfile}; exec sleep 30"], timeout_s=60))
        for _ in range(500):
            if pidfile.exists() and pidfile.read_text().strip():
                break
            await asyncio.sleep(0.01)
        call.cancel()
        with pytest.raises(asyncio.CancelledError):
            await call
        return alive(int(pidfile.read_text()))

    try:
        assert not asyncio.run(cancel_mid_call()), "the CLI process kept running after its call was cancelled"
    finally:
        pid = int(pidfile.read_text())
        if alive(pid):
            os.kill(pid, signal.SIGKILL)


GRANDCHILD = "sleep 30 & echo $! > {pidfile}; wait"  # like codex: a wrapper whose child holds stdout


@pytest.mark.parametrize("stop", ["timeout", "cancel"])
def test_a_stopped_call_kills_the_cli_and_its_children_at_once(tmp_path, stop):
    # Killing only the wrapper left its child holding stdout, so the call waited until that child finished:
    # a codex call with a 900 s limit ran for 44 minutes before it failed (synthetic calibration, 2026-10-01).
    pidfile = tmp_path / "pid"
    backend = SubprocessBackend("x", "sh", max_concurrency=1, retries=0)

    async def stop_mid_call() -> float:
        loop = asyncio.get_running_loop()
        started = loop.time()
        call = asyncio.ensure_future(backend._exec(["sh", "-c", GRANDCHILD.format(pidfile=pidfile)],
                                                   timeout_s=1 if stop == "timeout" else 60))
        if stop == "cancel":
            for _ in range(500):
                if pidfile.exists() and pidfile.read_text().strip():
                    break
                await asyncio.sleep(0.01)
            call.cancel()
        with pytest.raises((asyncio.CancelledError, BackendError)):
            await call
        return loop.time() - started

    try:
        elapsed = asyncio.run(stop_mid_call())
        assert elapsed < 10, f"the call returned after {elapsed:.0f}s, when its child exited, not when it was stopped"
        assert not alive(int(pidfile.read_text())), "the CLI's child kept running after the call was stopped"
    finally:
        pid = int(pidfile.read_text())
        if alive(pid):
            os.kill(pid, signal.SIGKILL)
