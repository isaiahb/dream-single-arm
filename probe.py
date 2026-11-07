"""Probe Dream-1 with a schedule of short prompts on ONE Metal arm, and keep everything the run recorded.

One continuous run of Dream's runner (single_arm.py: the other arm is never opened, its wrist is black). Each step
hands the loop a new prompt with ControlLoop.set_task(), which starts a fresh model episode at the next safe point,
holds it for its seconds, then moves on; no homing between steps. At the end the run stops (the arm homes and switches
off) and the run's records are copied into ~/probe_runs/<time>-<name>/:

- last-run.csv: every control tick, measured and commanded joints and grippers, end-effector speed, clamps (Dream's)
- inputs/: the frames each camera sent the model, and inputs.jsonl (Dream's)
- steps.json: each step's prompt and its start and end on the same monotonic clock as last-run.csv's t_s
- run.log: the runner's log

"{side}" in a prompt becomes the arm's side ("left" or "right").

    ~/dream-env/bin/python probe.py --arm right steps/stack-green-on-blue.json --dry-run
    ~/dream-env/bin/python probe.py --arm right steps/stack-green-on-blue.json        # the arm moves
"""

import argparse
import asyncio
import json
import logging
import pathlib
import shutil
import time

import single_arm
from robots import arms_lock, control, errors, run

DREAM_HOME = pathlib.Path.home() / ".dreamlabs"
RUNS = pathlib.Path.home() / "probe_runs"
_log = logging.getLogger("probe")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--arm", choices=["left", "right"], required=True)
    p.add_argument("steps", type=pathlib.Path, help='a JSON list of {"prompt": ..., "seconds": ...}')
    p.add_argument("--checkpoint", default="dreamlabs/dream-1-beta")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--view-port", type=int, default=8093)
    a = p.parse_args()
    steps = [dict(s, prompt=s["prompt"].replace("{side}", a.arm)) for s in json.loads(a.steps.read_text())]
    out = RUNS / f"{time.strftime('%Y%m%d-%H%M%S')}-{a.arm}-{a.steps.stem}{'-dry' if a.dry_run else ''}"
    out.mkdir(parents=True)
    log_file = logging.FileHandler(out / "run.log")
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s",
                        handlers=[logging.StreamHandler(), log_file])

    app = single_arm.prepare(a.arm, steps[0]["prompt"])

    # Catch the loop the runner builds, to change its prompt.
    loops: list[control.ControlLoop] = []
    original_init = control.ControlLoop.__init__

    def init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        loops.append(self)

    control.ControlLoop.__init__ = init
    record: list[dict] = []

    async def schedule(stop: asyncio.Event) -> None:
        while not loops and not stop.is_set():
            await asyncio.sleep(0.1)
        loop = loops[0]
        while loop.chunk_count == 0 and not stop.is_set():  # motion starts with the first chunk
            await asyncio.sleep(0.1)
        for i, step in enumerate(steps):
            if stop.is_set():
                break
            if i > 0:
                loop.set_task(step["prompt"])
            start = time.monotonic()
            _log.info("STEP %d/%d start: %r for %.0f s", i + 1, len(steps), step["prompt"], step["seconds"])
            entry = {"step": i + 1, "prompt": step["prompt"], "seconds": step["seconds"], "start_t": start}
            record.append(entry)
            try:
                await asyncio.wait_for(stop.wait(), timeout=step["seconds"])
            except asyncio.TimeoutError:
                pass
            entry["end_t"] = time.monotonic()
        _log.info("schedule done: stopping (the arm homes and switches off)")
        stop.set()

    async def go() -> None:
        stop = asyncio.Event()
        import signal

        for signum in (signal.SIGINT, signal.SIGTERM, signal.SIGHUP):
            asyncio.get_running_loop().add_signal_handler(signum, stop.set)
        sched = asyncio.create_task(schedule(stop))
        try:
            await run.main(app, a.checkpoint, dry_run=a.dry_run, stop=stop, view_port=a.view_port)
        finally:
            sched.cancel()

    print(f"DRY RUN: nothing is written to the {a.arm} arm" if a.dry_run else f"REAL RUN: the {a.arm.upper()} arm moves; Ctrl-C homes it and switches it off")
    try:
        lock = arms_lock.acquire(DREAM_HOME / arms_lock.LOCK_NAME, arms_lock.ROBOT_RUN)
    except errors.StationError as exc:
        raise SystemExit(f"the arms are held: {exc}") from None
    try:
        asyncio.run(go())
    finally:
        lock.close()
        (out / "steps.json").write_text(json.dumps({"dry_run": a.dry_run, "checkpoint": a.checkpoint, "steps": record}, indent=1))
        if (DREAM_HOME / "last-run.csv").exists():
            shutil.copy2(DREAM_HOME / "last-run.csv", out / "last-run.csv")
        if (DREAM_HOME / "last-run_inputs").exists():
            shutil.copytree(DREAM_HOME / "last-run_inputs", out / "inputs")
        print(f"saved: {out}")


if __name__ == "__main__":
    main()
