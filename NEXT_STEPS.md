# NEXT_STEPS: what is still open

The repository cannot be used on real robots until the items below are done.

Acronyms are spelled out where they first appear. See `README.md` for how the tool works.

**Quick count of what is open in the files right now:** 42 unknown values (`FILL_ME_IN`): Franka 11,
G1 9, SO-101 12, Trossen 10. Plus 4 safety reviews, 16 unverified vendor-call lines (`# VERIFY`), and 4 open `TODO`
items. To see them yourself at any time:

```sh
grep -rn "FILL_ME_IN" robots/ .github/     # unknown values and owners
grep -rn "VERIFY"     robotprofiles/       # vendor calls to check
grep -rn "TODO"       robotprofiles/ .github/   # unfinished work
```

---

## Phase 0: Get the repository running on a computer

Do this on **each computer that talks to a robot**.

- [ ] Unzip the repo and open a terminal in the `robot-profiles` folder.
- [ ] Check Python is 3.9 or newer: `python3 --version` (developed and tested on 3.12).
- [ ] Install the tool's only library: `pip install -r requirements.txt` (PyYAML).
- [ ] If the repo is not already a Git repository on your hosting service (GitHub, GitLab...), create a
      remote repository and push it. The zip already contains one commit.
- [ ] Fix the commit author of that first commit (it is a placeholder):
      `git commit --amend --reset-author --no-edit`
- [ ] If a script says "permission denied": `chmod +x scripts/rp scripts/install_hooks.sh`
- [ ] Turn on the protective hook: `./scripts/install_hooks.sh` (blocks commits that change hardware or safety
      files without a changelog entry).
- [ ] Install **Git LFS** (Large File Storage, for big trained-model files): `git lfs install`
- [ ] Run the tests: `python3 -m unittest discover -s tests -v`. Everything should say OK.
- [ ] Try the tool safely: `./scripts/rp list` and `./scripts/rp apply franka example_user --dry-run`
      (a dry run touches nothing).

---

## Phase 1: Fill in the hardware facts (`FILL_ME_IN` values)

Run `./scripts/rp setup <robot>` and it will ask for each value below, one at a time. Press Enter to skip
anything you do not know yet. These files are **protected**, so afterwards add a row to
`robots/HARDWARE_CHANGELOG.md` and have a second person review before committing.

**Who should do this:** someone standing next to the robot who can read its labels, network settings, and
documentation. Do not guess. A wrong tool weight or IP address is worse than a blank.

### Franka (`robots/franka/hardware.yaml`), 9 values

| Field | What it is | Where to find it |
|---|---|---|
| `robot_id` | A short unique name you choose, e.g. `franka_lab_01` | Your choice; write it on a label on the robot too |
| `model` | `FR3` (Franka Research 3) or `Panda` (older) | Label on the arm base |
| `network.robot_ip` | IP address (Internet Protocol, a network address) of the arm's control box | Your network set-up; try opening it in a web browser (that is the Desk page) |
| `tool.name` | Name of what is bolted on, e.g. `franka_hand` | Your set-up |
| `tool.mass_kg` | Weight of everything past the flange (the plate at the end of the arm), in kg | Datasheet or a kitchen scale. Include cameras, adapters, cables |
| `tool.center_of_mass_m` | `[x, y, z]` in metres, measured from the flange | CAD (computer-aided design) model, or vendor data |
| `tool.inertia_kg_m2` | 9 numbers (3x3 matrix, row by row) describing how the tool resists rotation | CAD software or the vendor. Do not guess |
| `tool.flange_to_tcp_transform` | 16 numbers (4x4 matrix, column-major) locating the tool's working point (TCP, tool center point) | Desk shows the value for the standard Franka Hand |
| `cameras.wrist_camera_serial` | Serial number, or `none` | Label on the camera |

### Unitree G1 (`robots/g1/hardware.yaml`), 7 values

| Field | What it is | Where to find it |
|---|---|---|
| `robot_id` | Short unique name, e.g. `g1_lab_01` | Your choice |
| `variant` | `EDU` (Education model, the one that can be programmed) or `base` | Purchase records or Unitree |
| `firmware_version` | Robot software version | Unitree's app or documentation |
| `network.interface` | Name of the network port **on your computer** wired to the robot, e.g. `eth0` | Linux: `ip link` lists them |
| `network.robot_ip` | Address of the robot's computer | Unitree's documentation (it gives an address range; confirm the exact one) |
| `hands.type` | `none`, or the model of dexterous hands fitted | Look at the robot / order records |
| `compute.onboard_computer` | e.g. the onboard Jetson, or `none` | Documentation |

### SO-101 (`robots/so101/hardware.yaml`), 10 values

| Field | What it is | Where to find it |
|---|---|---|
| `robot_id` | Short unique name, e.g. `so101_bench_01` | Your choice |
| `follower.lerobot_id` and `leader.lerobot_id` | The `id` you pass to LeRobot commands for each arm | The commands you already use; must match exactly |
| `follower.port` and `leader.port` | USB serial port of each arm | Prefer a stable path like `/dev/serial/by-id/usb-...` (Linux) because `/dev/ttyACM0` can change when cables move |
| `follower.calibration_file` and `leader.calibration_file` | Full path to each arm's calibration `.json` file | LeRobot usually stores these under `~/.cache/huggingface/lerobot/calibration/` (verify for your version) |
| `follower.calibration_sha256` and `leader.calibration_sha256` | A **fingerprint** of each calibration file (SHA-256, a code that changes if the file changes at all) | Run `./scripts/rp snapshot so101` after the two file paths are filled in, then paste the values |
| `cameras` | Cameras attached, e.g. `{front: /dev/video0}`, or `{}` | Your set-up |

Also confirm the pre-filled `motor_ids` (1 to 6, shoulder pan through gripper) match how your arms were
assembled. They are LeRobot's usual numbering, not something I could check.

### Trossen (`robots/trossen/hardware.yaml`), 8 values

| Field | What it is | Where to find it |
|---|---|---|
| `robot_id` | Short unique name | Your choice |
| `model` | Model name exactly as the `trossen_arm` library spells it (e.g. `wxai_v0`) | Trossen documentation for your generation |
| `end_effector` | End-effector (gripper) name as the library spells it | Same |
| `role` | `leader` (moved by hand), `follower` (copies the leader), or `standalone` | Your set-up |
| `network.ip_address` | The arm's IP address | Trossen documentation or your network set-up |
| `firmware_version` | Arm firmware version | Trossen tools. Driver and firmware versions must match |
| `payload_max_kg` | Maximum payload for your model | Manufacturer datasheet |
| `cameras` | Cameras attached, or `{}` | Your set-up |

- [ ] Franka filled in and reviewed
- [ ] G1 filled in and reviewed
- [ ] SO-101 filled in and reviewed (including fingerprints)
- [ ] Trossen filled in and reviewed
- [ ] Changelog rows added for each; changes committed

---

## Phase 2: Review the safety limits

The numbers in each `safety.yaml` are **conservative starter values I wrote without access to your robots**.
They are not engineering sign-off. A person who knows each robot must read the file, adjust what is wrong,
and then fill in the `review` block (`reviewed_by` and `reviewed_on`, two values per robot). The tool refuses to
run for real until that is done.

**Golden rule:** for stiffness, force and speed limits, a *lower* maximum is safer. For collision thresholds,
a *higher* threshold is *less* safe because the arm tolerates harder bumps before stopping.

### Franka

- [ ] Compare `joint_stiffness` and `cartesian_stiffness` maxima with the values you actually use and with
      Franka's documentation. Make sure the list lengths are right (7 joints; 6 for x, y, z, and three rotations).
- [ ] Decide the collision threshold range (`torque_threshold_nm`, `force_threshold_n`) from your task.
- [ ] Check gripper `force_n` and `speed_m_s` against the gripper's datasheet.
- [ ] Decide whether to allow a `torque` control mode (currently not allowed).
- [ ] Consider adding a workspace boundary rule (the file format only supports number and list limits today).

### Unitree G1

- [ ] Review the speed limits (`max_forward_speed_m_s` 0.4, `max_lateral_speed_m_s` 0.3, `max_turn_rate_rad_s` 0.5).
- [ ] Review `kp_scale`/`kd_scale` (stiffness and damping multipliers) and `action_scale` limits.
- [ ] **Decide about low-level control** (commanding every joint directly, which switches off the built-in
      balance software). It is blocked on purpose. Only add `low_level` after a written safety review. Falls
      can hurt people and cost a lot to repair.
- [ ] Write down your gantry/harness procedure and where the emergency stop is.

### SO-101

- [ ] Check `max_relative_target` (largest move per control step): confirm the **units** in your LeRobot version,
      then set a sensible ceiling.
- [ ] Check `p_coefficient` (servo stiffness) against LeRobot's default for the SO-101 (verify the current value)
      and against overheating experience.
- [ ] Check `teleop.fps` (control steps per second) limits.

### Trossen

- [ ] Confirm which control modes to allow (`position`, `velocity` allowed; `effort` blocked on purpose).
- [ ] Set the `goal_time_s` minimum (currently 1.0 s; lower means faster, jerkier moves).
- [ ] Set `speed_scale` and `kp_scale` ceilings for your model and payload.

- [ ] All four `review` blocks filled in and committed with a changelog entry

---

## Phase 3: Verify every vendor call (`# VERIFY`)

I wrote the code that talks to each vendor's library from general knowledge and could not run it against a real
robot or install the libraries. **Names, arguments and behaviour change between versions.** For each line
below: open the vendor's current documentation for the version you installed, confirm or correct the line, then
delete its `# VERIFY` comment.

Suggested order: check the **import** lines first (does the library install at all?), then **read-only** calls
(snapshot), then calls that **change** the robot.

### Franka: `robotprofiles/adapters/franka.py` (library: `panda-py`)

- [ ] `import panda_py`: correct package and import name for your version
- [ ] `panda_py.Panda(ip)`: constructor arguments (newer versions may require Desk login details)
- [ ] `get_robot()`: returns the low-level object that owns the calls below
- [ ] `get_state()` and `state.q`: joint positions (`q`, in radians)
- [ ] `set_collision_behavior(...)`: number and order of the eight lists
- [ ] `set_load(mass, centre_of_mass, inertia)`: argument order and units
- [ ] `set_EE(transform)`: the tool point matrix layout (column-major 4x4)
- [ ] Confirm your arm model (FR3 or Panda) is supported by the version you installed
- [ ] Confirm Desk has the brakes unlocked and FCI (Franka Control Interface) activated before testing

### Unitree G1: `robotprofiles/adapters/g1.py` (library: `unitree_sdk2_python`)

- [ ] `from unitree_sdk2py.core.channel import ChannelFactoryInitialize`: import path
- [ ] `ChannelFactoryInitialize(0, iface)`: arguments (domain id, network interface name)

### SO-101: `robotprofiles/adapters/so101.py` (library: LeRobot)

- [ ] Nothing is sent to the servos today, so there are no live vendor calls. Verify only that the calibration
      file location you entered is the one your LeRobot version actually reads.

### Trossen: `robotprofiles/adapters/trossen.py` (library: `trossen_arm`)

- [ ] `import trossen_arm`: package name
- [ ] `trossen_arm.Model.<name>` and `trossen_arm.StandardEndEffector.<name>`: enum names match what you typed
      into `model` and `end_effector`
- [ ] `TrossenArmDriver()`: constructor
- [ ] `driver.configure(model, effector, ip, True)`: argument list
- [ ] `driver.get_all_positions()`: method name

### After the code reads correctly, test on the real robot

For each robot, in this order, with a person present and the emergency stop in reach:

- [ ] `./scripts/rp apply <robot> example_user --dry-run` shows a sensible plan
- [ ] `./scripts/rp snapshot <robot>` connects and prints the robot's state
- [ ] `./scripts/rp apply <robot> example_user` succeeds, and the run log in `runs/` looks right
- [ ] A **read-only** test of your own control script using `load_active("<robot>")`
- [ ] A slow, small motion test (G1: on the gantry) before anything else

---

## Phase 4: Decisions only you can make

- [ ] **Franka model:** FR3 or Panda? (affects which `panda-py` version and settings apply.)
- [ ] **Trossen generation:** newer Trossen AI arms (what the adapter targets) or older WidowX/ViperX with
      Dynamixel motors (needs a different adapter; see Phase 5)?
- [ ] **CODEOWNERS:** replace the two `@FILL_ME_IN` entries in `.github/CODEOWNERS` with real GitHub usernames or
      team names, and (on GitHub) turn on branch protection so reviews are actually required. If you use GitLab
      or another host, move the file to the location that host expects.
- [ ] **Who are the robot leads** allowed to approve changes to hardware and safety files?
- [ ] **Sharing rules:** the lock only works on the one computer that controls a robot. Decide how people book
      time when several computers can reach the same robot (a shared calendar is usually enough).
- [ ] **Shared logins:** if several developers use one computer login, agree that everyone sets
      `ROBOT_USER=theirname` in their terminal so locks and logs name the right person.
- [ ] **Where run logs go:** `runs/` is per computer and not in Git. Decide whether to collect them somewhere
      shared.
- [ ] **Naming convention** for profiles, e.g. `<name>_<experiment>`.
- [ ] **How long a lock should last** (currently 8 hours; the constant is `LOCK_TTL_SECONDS` in
      `robotprofiles/lock.py`).

---

## Phase 5: Unfinished code

These are deliberately left open rather than guessed. Ask for them (in Claude, or a developer) once Phase 3 is
done, because they depend on verified vendor calls.

- [ ] **G1 state readback** (`adapters/g1.py`, `snapshot()`): subscribe to the robot's low-state messages and
      return joint angles so run logs show the state before and after. Today it returns a note only.
- [ ] **Franka `snapshot()`, Trossen `snapshot()`** work only once their vendor calls are verified.
- [ ] **SO-101 servo settings push** (`adapters/so101.py`, `push()`): optional. Today your own LeRobot scripts read
      motor settings from the active file; nothing is written to the servos by this tool.
- [ ] **Older Trossen arms** (Interbotix / Dynamixel): a second adapter, if you own them.
- [ ] **Windows support for SO-101 port checks:** currently assumes Linux-style device paths.

Optional improvements (not needed to get started):

- [ ] A `diff` command to compare two profiles side by side
- [ ] Automatic run-log collection to a shared folder
- [ ] A continuous-integration job (GitHub Actions) that runs the tests and `validate` on every pull request
- [ ] A safety rule type for workspace boundaries

---

## Phase 6: Roll out to the team

- [ ] Each developer creates their own profile: `./scripts/rp new-profile <robot> <name>`
- [ ] Move each developer's existing numbers into their profile (only the values that differ from `base.yaml`)
- [ ] Check each with `./scripts/rp validate <robot> <profile>`
- [ ] Delete or rename the `example_user.yaml` profiles once real ones exist (their `checkpoint` paths point to
      files that do not exist)
- [ ] Update every control script to read settings with `load_active("<robot>")` instead of hard-coded numbers
- [ ] Add the shared-robot etiquette to your team notes: `apply` when you start, `release` when you finish
- [ ] Run one supervised session per robot where two developers swap profiles, and confirm each gets exactly
      their own values back
- [ ] Set a review date: revisit `safety.yaml` after the first month of real use

---

## Known limits of the current version

- The lock covers **one computer**, not a whole network.
- Safety rules can express minimum, maximum and allowed values only. They cannot express relationships between
  settings or workspace shapes.
- The tool checks *settings*; it cannot see what your own control code then does with them.
- `--yes` skips the human checklist. It exists for scripting; using it casually removes a safety step.
- Nothing has been run against a real robot. All 27 automated tests and the end-to-end test use temporary files
  and a stand-in port.

## Definition of done

The project is ready for daily use when: zero `FILL_ME_IN` remain, all four safety files have a named
reviewer, every `# VERIFY` has been checked or removed, each robot has passed the Phase 3 hardware test, every
developer has a validated profile, and the protective Git hook is installed on every computer.
