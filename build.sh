#!/usr/bin/env bash
# helm-x build script — macOS / Linux (mirrors build.bat for Windows/MinGW)
set -euo pipefail

cd "$(dirname "$0")"

# 1. (re)generate embedded resources — only when the full asset set is
#    present. rewriter_builtin.json is kept out of git and baked into the
#    committed src/resources_generated.cpp; regenerating without it would
#    strip that resource, so fall back to the committed file instead.
if [ -f assets/rewriter_builtin.json ]; then
    python3 tools/embed.py
else
    echo "[skip] assets/rewriter_builtin.json absent — using committed src/resources_generated.cpp"
fi

# 2. configure + build
cmake -B build -DCMAKE_BUILD_TYPE=Release "$@"
cmake --build build -j

echo
echo "[OK] build/helmx"
echo "[OK] deps check: otool -L build/helmx  (macOS)  |  ldd build/helmx  (Linux)"
