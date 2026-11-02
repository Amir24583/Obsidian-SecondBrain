#!/usr/bin/env bash
# File every new, changed, moved or deleted source into the wiki with Claude Code.
# Use from cron/systemd for raw/inbox drops, e.g. hourly.
set -euo pipefail
exec python3 "$(dirname "$0")/sb.py" auto "$@"
