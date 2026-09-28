# robot-profiles

Shared, versioned, safety-checked settings for lab robots: Unitree G1, Franka, SO-101, and Trossen.

> Not yet ready for real robots. See [`NEXT_STEPS.md`](NEXT_STEPS.md) first.

## Layout

```
robots/<robot>/hardware.yaml   protected physical facts (review + changelog required)
robots/<robot>/safety.yaml     protected hard limits (robot lead only)
robots/<robot>/base.yaml       shared defaults
profiles/<robot>/<name>.yaml   your personal overrides
```

Effective settings = `base.yaml` + your profile, checked against `safety.yaml`.

## Setup (once per computer)

Requires Python 3.9+ and Git.

```sh
pip install -r requirements.txt
./scripts/install_hooks.sh
git lfs install                 # for model files
```

Then install the vendor library for the robots that computer controls (see `requirements.txt`).
If a script says "permission denied": `chmod +x scripts/rp scripts/install_hooks.sh`.

## Setup (once per robot)

1. `./scripts/rp setup <robot>` to fill in `FILL_ME_IN` values (`g1`, `franka`, `so101`, `trossen`).
2. Have someone who knows the robot review `safety.yaml`.
3. Add a row to `robots/HARDWARE_CHANGELOG.md`, get a review, commit.
4. SO-101 only: `./scripts/rp snapshot so101` and paste the fingerprints into `hardware.yaml`.
5. Put real usernames in `.github/CODEOWNERS`.

## Usage

```sh
./scripts/rp list                                   # robots, profiles, current locks
./scripts/rp new-profile franka alex_pick_place     # create your profile
./scripts/rp validate franka alex_pick_place        # check against safety limits
./scripts/rp apply franka alex_pick_place --dry-run # preview
./scripts/rp apply franka alex_pick_place           # apply and lock the robot
./scripts/rp release franka                         # release the lock when done
```

Useful `apply` flags: `--clamp` (clip values to limits), `--yes` (skip checklist), `--force-lock`.
Set `ROBOT_USER=yourname` if sharing a login.

Read the applied settings in your own code:

```python
# PYTHONPATH=/path/to/repo python3 my_script.py
from robotprofiles import load_active
cfg = load_active("franka")["settings"]
```

## Tests

```sh
python3 -m unittest discover -s tests -v
```
