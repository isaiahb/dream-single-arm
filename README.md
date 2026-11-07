# Dream-1 on one arm of a Metal Arm Station

Runs Dream Labs' Dream-1 on **one** arm of a two-arm MakerMods Metal Arm Station, with the other arm never opened.
Use it when only one arm is yours (a teammate has the other), or to try the model on one arm first.

It is Dream's own runner (`dreamcli robot run`'s `robots.run.main`): homing, the control loop, its speed cap and
safety stops, the switch-off. Two things change:

- **The other arm is a stand-in.** It is never opened and its CAN adapter is never touched. It reads as resting at
  its home pose with the gripper open and drops every target, so the model's moves for it go nowhere.
- **The other wrist camera is black** (`black.py`), Dream's rule for a camera an arm does not have.

The config is your station's own `~/.dreamlabs/station.yaml` (from `dreamcli setup`), copied at run time with the
other wrist camera swapped for black frames. Nothing station-specific is in this repo, and no keys: Dream's
credentials stay in `~/.dreamlabs/credentials` on the station.

## Run it

On the station, with Dream's environment (`~/dream-env` on ours):

```bash
git clone <this repo> ~/dream-single-arm && cd ~/dream-single-arm

# 1. build the config only: no lock, no arm, no model
~/dream-env/bin/python single_arm.py --arm right --task "pick up the green cube" --check

# 2. dry run: the model runs, nothing is written to the arm
~/dream-env/bin/python single_arm.py --arm right --task "pick up the green cube" --dry-run

# 3. real run: the arm homes, then plays Dream's moves. Hand on the e-stop. Ctrl-C homes it and switches it off
~/dream-env/bin/python single_arm.py --arm right --task "pick up the green cube"
```

`http://127.0.0.1:8093` on the station shows what the model sees (`--view-port` to change it).

### A schedule of prompts

`probe.py` runs one continuous episode and hands the model a new prompt every few seconds, with no homing between
steps. Afterwards everything Dream recorded is copied to `~/probe_runs/<time>-<arm>-<name>/`: every control tick
(`last-run.csv`), the frames the model saw (`inputs/`), the step times (`steps.json`) and the log.

```bash
~/dream-env/bin/python probe.py --arm right steps/stack-green-on-blue.json --dry-run
~/dream-env/bin/python probe.py --arm right steps/stack-green-on-blue.json
```

`{side}` in a step's prompt becomes `left` or `right`.

## Sharing the station

- Both scripts take the station's one-holder arms lock (`~/.dreamlabs/arms.lock`), as `dreamcli` and `dhk-collect`
  do, and refuse to start while anyone holds it. The lock covers both arms, so two people cannot run one arm each at
  the same time, even with this.
- A USB camera streams to one program at a time. While a run has the overhead camera, nobody else gets it.
- If Dream's driver says an arm "is still powered from an earlier session, holding the arm with nothing driving it",
  a previous run's switch-off did not reach every motor. Support the arm, switch its power off and on, then run again.

## Status

- Left arm: real runs of Dream-1 (`dreamlabs/dream-1-beta`) on our station, Nov 7 2026.
- Right arm: the same code with the sides swapped. Its config build is checked; it has not been run on the right arm yet.
