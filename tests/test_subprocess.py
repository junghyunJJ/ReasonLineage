"""The shared plumbing for CLI backends."""

import asyncio
import os
import signal

import pytest

from reasonlineage.backends._subprocess import SubprocessBackend


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
