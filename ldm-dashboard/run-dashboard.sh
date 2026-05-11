#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "[ldm-dashboard] Installing dependencies..."
npm install

echo "[ldm-dashboard] Starting dashboard on http://0.0.0.0:5173"
exec npm run dev
