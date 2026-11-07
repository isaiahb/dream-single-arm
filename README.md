# Dream-1 on one arm of a Metal Arm Station

Run Dream Labs' **Dream-1** world action model on **one** arm of a two-arm MakerMods Metal Arm Station, with the
other arm never opened.

Use it when only one arm is yours (a teammate has the other), when the other arm is broken or busy, or to try the
model on one arm before trusting it with two.

- `single_arm.py`: one task prompt, run until you stop it.
- `probe.py`: a schedule of prompts in one episode (for example pick, carry, place, release), with everything Dream
  recorded saved afterwards.

Both are Dream's own runner (`robots.run.main`, the same thing `dreamcli robot run` starts), with one arm swapped for
a stand-in. Homing, the control loop, Dream's speed cap and safety stops, and the switch-off at the end are all
Dream's code, unchanged.

## Handover: running it on the right arm

Everything happens on the station, in Dream's environment (`~/dream-env` on ours; use wherever `dreamcli` lives on
yours). Your Dream login must already be set up on the station (`~/.dreamlabs/credentials`); this repo holds no keys.

**1. Get the code**

```bash
git clone https://github.com/isaiahb/dream-single-arm ~/dream-single-arm
cd ~/dream-single-arm
```

**2. Check the config.** Opens nothing: no lock, no arm, no model.

```bash
~/dream-env/bin/python single_arm.py --arm right --task "pick up the green cube" --check
```

It writes `station-right-only.yaml` beside the script: your `~/.dreamlabs/station.yaml` with `wrist_l` swapped for
black frames. Open it and check that `wrist_r` still points at the right wrist camera.

**3. Dry run.** The model runs and you can watch what it sees, but nothing is written to the arm.

```bash
~/dream-env/bin/python single_arm.py --arm right --task "pick up the green cube" --dry-run
```

Open `http://127.0.0.1:8093` on the station (or tunnel it: `ssh -L 8093:127.0.0.1:8093 <station>`) to see the
cameras the model gets: overhead, your wrist, and the black one.

**4. Real run.** Clear the table around the arm and keep a hand on the e-stop.

```bash
~/dream-env/bin/python single_arm.py --arm right --task "pick up the green cube"
```

The arm moves to its home pose, then plays Dream's actions until you press **Ctrl-C**. It then homes again and
switches its motors off.

**5. A schedule of prompts (optional)**

```bash
~/dream-env/bin/python probe.py --arm right steps/stack-green-on-blue.json --dry-run
~/dream-env/bin/python probe.py --arm right steps/stack-green-on-blue.json
```

A steps file is a JSON list of `{"prompt": ..., "seconds": ...}`; `{side}` in a prompt becomes `left` or `right`.
Each step hands the running loop a new prompt (a fresh model episode at the next safe point, no homing between steps).
When the schedule ends, or on Ctrl-C, the run stops and its records are copied to
`~/probe_runs/<time>-<arm>-<steps name>/`:

| file | what |
| --- | --- |
| `last-run.csv` | every control tick: measured and commanded joints and grippers, end-effector speed, clamps |
| `inputs/` | the frames each camera sent the model, and `inputs.jsonl` |
| `steps.json` | each step's prompt, and its start and end on the same clock as `last-run.csv`'s `t_s` |
| `run.log` | the runner's log |

Options for both scripts: `--checkpoint` (default `dreamlabs/dream-1-beta`), `--view-port` (default 8093),
`--dry-run`. `single_arm.py` also has `--check`.

## How it works

- **The other arm is a stand-in** (`StandIn` in `single_arm.py`). Dream's runner asks for both arms. For the one
  you did not pick, it gets a driver that is never connected to anything: it reads as resting at that arm's home pose
  with the gripper open, and drops every command. That arm's CAN adapter is never opened, so the model's actions for
  it go nowhere.
- **The other wrist camera is black** (`black.py`). The model still gets three cameras; the missing arm's wrist
  shows black frames at the configured size and rate, which is what Dream does for a camera an arm does not have.
- **The config comes from your station.** At run time, `single_arm.py` copies `~/.dreamlabs/station.yaml` (from
  `dreamcli setup`) and replaces the other wrist camera's `device` with `source: black.py:BlackSource`. CAN adapters,
  home poses, gripper ends, cameras and robot id stay your station's own, and none of them are in this repo.
- **Dream's tool-point check** (`run.check_tool_point`) runs before every run, as in `dreamcli robot run`.

## Sharing the station

- **One run at a time.** Both scripts take the station's arms lock (`~/.dreamlabs/arms.lock`), as `dreamcli` and
  `dhk-collect` do, and refuse to start while anyone holds it. The lock covers both arms, so two people cannot each
  run one arm at the same time, even with this.
- **Cameras.** A USB camera streams to one program at a time. While a run has the overhead camera, nothing else gets
  it, and a recorder that opens it per episode will fail.

## When something goes wrong

| message | what it means | what to do |
| --- | --- | --- |
| `the arms are held: ...` | someone holds the arms lock | wait for their run to end; the message names what holds it |
| `arm '<side>' refuses to start: ... is still powered from an earlier session, holding the arm with nothing driving it` | a previous run's switch-off did not reach every motor (its log shows `torque off (missed replies: N)`) | support the arm (it has no brakes), switch its power off and on, run again |
| the arm does not move in a real run | check the log for `DRY RUN`, and that `--arm` is the arm you mean | |
| a camera is black that should not be | `--check`, then read the written yaml: the black one must be the other arm's wrist | |

## Status

- **Left arm:** real Dream-1 runs (`dreamlabs/dream-1-beta`) on our station, Nov 7 2026, including a step schedule.
- **Right arm:** the same code with the sides swapped. The config builds and loads in Dream's own loader. It has not
  been run on the right arm yet; do the dry run first.
- Written against Dream's station packages `dreamlabs` 1.0.37 and `dreamlabs-client` 1.1.3. It reaches into the
  runner's internals (`bodies.for_config`, `followers.Driver`, `control.ControlLoop`), so a newer Dream release may
  need small changes.
