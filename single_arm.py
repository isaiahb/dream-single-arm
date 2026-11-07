"""Dream-1 on ONE arm of a two-arm Metal Arm Station: `dreamcli robot run`, with the other arm never opened.

Everything is Dream's own runner (robots.run.main): homing, the loop, its speed cap and safety stops, the switch-off.
Two things differ:
- The other arm is a stand-in: never opened, its CAN adapter never touched. It reads as resting at its home pose with
  the gripper open and drops every target, so the model's moves for it go nowhere.
- The other arm's wrist camera is black (black.py): Dream's rule for a camera an arm does not have.

The station config is the station's own (~/.dreamlabs/station.yaml, written by `dreamcli setup`), copied with the other
wrist camera swapped for black frames, so nothing station-specific lives in this repo.

    ~/dream-env/bin/python single_arm.py --arm right --task "..." --check      # build the config only, open nothing
    ~/dream-env/bin/python single_arm.py --arm right --task "..." --dry-run    # nothing is written to the arm
    ~/dream-env/bin/python single_arm.py --arm right --task "..."              # the arm moves; hand on the e-stop
"""

import argparse
import asyncio
import dataclasses
import logging
import pathlib

import numpy as np
import yaml

from robots import arms_lock, bodies, config, errors, followers, run

DREAM_HOME = pathlib.Path.home() / ".dreamlabs"
STATION = DREAM_HOME / "station.yaml"
LOCK = DREAM_HOME / arms_lock.LOCK_NAME  # the station's one-holder lock, as dreamcli and dhk-collect take it
BLACK = pathlib.Path(__file__).resolve().with_name("black.py")


def station_config(arm: str) -> pathlib.Path:
    """The station's config with the other arm's wrist camera black, written beside this file."""
    other = "right" if arm == "left" else "left"
    cfg = yaml.safe_load(STATION.read_text())
    wrist = f"wrist_{other[0]}"
    for cam in cfg.get("cameras", []):
        if cam.get("name") == wrist:
            cam.pop("device", None)
            cam["source"] = f"{BLACK}:BlackSource"
    out = pathlib.Path(__file__).resolve().with_name(f"station-{arm}-only.yaml")
    out.write_text(f"# single_arm.py --arm {arm}: {STATION} with the {other} wrist camera black; the {other} arm is never opened.\n"
                   + yaml.safe_dump(cfg, sort_keys=False))
    return out


class StandIn(followers.Driver):
    """The unused arm, never opened: reads as resting at home with the gripper open, drops every target."""

    def __init__(self, home_rad) -> None:
        self._home = np.asarray(home_rad, dtype=np.float64)

    def read(self) -> followers.Reading:
        return followers.Reading(self._home.copy(), np.zeros_like(self._home), 1.0)

    def write(self, positions_rad, gripper) -> None:
        pass

    def close(self) -> None:
        pass

    def torque_off(self) -> None:
        pass


def only(arm: str):
    """A bodies.for_config that opens `arm` as usual and gives the other a stand-in."""
    other = "right" if arm == "left" else "left"
    for_config = bodies.for_config

    def patched(app):
        body = for_config(app)

        def stand_in(cfg):
            return followers.FollowerArm(other, StandIn(cfg.home), home_rad=cfg.home)

        def open_arm(cfg, name):
            return stand_in(cfg) if name == other else body.open_arm(cfg, name)

        def open_arm_read_only(cfg, name):
            if name == other:
                return stand_in(cfg)
            return (body.open_arm_read_only or body.open_arm)(cfg, name)

        return dataclasses.replace(body, open_arm=open_arm, open_arm_read_only=open_arm_read_only)

    return patched


def prepare(arm: str, task: str):
    """Dream's app for a run on `arm` alone, with the tool-point check Dream does before every run."""
    bodies.for_config = only(arm)  # robots.run looks it up per call
    app = run.with_action_space(run.with_task(config.load(station_config(arm)), task), None)
    run.check_tool_point(app, skip=False)
    return app


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("--arm", choices=["left", "right"], required=True)
    p.add_argument("--task", required=True)
    p.add_argument("--checkpoint", default="dreamlabs/dream-1-beta")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--check", action="store_true", help="build the config and stop: no lock, no arm, no model")
    p.add_argument("--view-port", type=int, default=8093)
    a = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    other = "right" if a.arm == "left" else "left"
    if a.check:
        print(f"config: {station_config(a.arm)}")
        return
    app = prepare(a.arm, a.task)
    print(f"what the model sees: http://127.0.0.1:{a.view_port}")
    print(f"DRY RUN: nothing is written to the {a.arm} arm" if a.dry_run
          else f"REAL RUN: the {a.arm.upper()} arm moves home, then plays Dream's moves; Ctrl-C homes it and switches it off")
    print(f"the {other} arm is never opened")
    try:
        lock = arms_lock.acquire(LOCK, arms_lock.ROBOT_RUN)
    except errors.StationError as exc:
        raise SystemExit(f"the arms are held: {exc}") from None
    try:
        asyncio.run(run.main(app, a.checkpoint, dry_run=a.dry_run, view_port=a.view_port))
    finally:
        lock.close()


if __name__ == "__main__":
    main()
