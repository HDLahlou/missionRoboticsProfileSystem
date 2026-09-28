#!/usr/bin/env sh
# One-time set-up per clone: tell Git to use the hooks stored in this repository.
cd "$(dirname "$0")/.." || exit 1
git config core.hooksPath scripts/hooks
chmod +x scripts/hooks/pre-commit scripts/rp
echo "Git hooks installed. Changes to hardware/safety files now require a changelog entry."
