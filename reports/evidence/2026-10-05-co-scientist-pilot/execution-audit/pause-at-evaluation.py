"""Stop our worker only after all generation statuses are durably written."""
import argparse
import json
import os
import signal
import time
from pathlib import Path


def pause(pid, directory, expected_script):
    directory = Path(directory)
    marker = directory / 'review-materials/analyst/mapping.json'
    proc = Path(f'/proc/{pid}')
    while not marker.exists():
        if not proc.exists():
            return {'status': 'worker_already_exited'}
        time.sleep(.001)
    argv = (proc / 'cmdline').read_bytes().split(b'\0')
    if str(Path(expected_script).resolve()).encode() not in argv:
        raise RuntimeError('worker identity mismatch; no signal sent')
    os.kill(pid, signal.SIGSTOP)
    statuses = list((directory / 'runs').glob('*/status.json'))
    if len(statuses) != 10:
        os.kill(pid, signal.SIGCONT)
        raise RuntimeError('generation statuses incomplete; worker resumed')
    independent_started = (directory / 'independent').exists()
    receipt = {'status': 'generation_boundary', 'monotonic': time.monotonic(),
               'generation_statuses': len(statuses), 'independent_directory_existed': independent_started,
               'reason': 'user approved initial/intermediate proposals in the bounded assessment corpus'}
    if independent_started:
        # Recover exact counters if evaluation admission raced with this monitor.
        os.kill(pid, signal.SIGCONT)
        os.kill(pid, signal.SIGTERM)
        deadline = time.monotonic() + 5
        while not (directory / 'study.json').exists() and time.monotonic() < deadline and proc.exists():
            time.sleep(.01)
    if proc.exists():
        os.kill(pid, signal.SIGKILL)
    (directory / 'scope-boundary.json').write_text(json.dumps(receipt, indent=2) + '\n')
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('pid', type=int)
    parser.add_argument('directory')
    parser.add_argument('expected_script')
    args = parser.parse_args()
    print(json.dumps(pause(args.pid, args.directory, args.expected_script)), flush=True)
