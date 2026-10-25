#!/bin/bash
# Make LightGBM and XGBoost loadable on macOS without Homebrew's libomp.
#
# Their wheels link against @rpath/libomp.dylib and only search absolute
# Homebrew/MacPorts paths. On a machine where `brew install libomp` is not
# possible (e.g. /opt/homebrew not user-writable), those lookups all fail and
# importing either library raises a dlopen error.
#
# scikit-learn's wheel already bundles a compatible libomp.dylib, so this
# copies it next to each library and adds @loader_path to the rpath list, which
# makes the existing @rpath/libomp.dylib reference resolve locally. The
# libraries must be re-signed afterwards because editing a Mach-O invalidates
# its ad-hoc signature.
#
# Re-run this after any `pip install` that reinstalls lightgbm or xgboost.
#
#     bash scripts/fix_openmp.sh

set -euo pipefail

VENV="${VENV:-.venv}"
SP="$(cd "$VENV/lib"/python3.*/site-packages && pwd)"
OMP="$SP/sklearn/.dylibs/libomp.dylib"

# install_name_tool/otool want a writable xcrun cache dir.
export XCRUN_DB_PATH="${TMPDIR:-/tmp}/xcrun_db"

if [ ! -f "$OMP" ]; then
  echo "error: no bundled libomp at $OMP (is scikit-learn installed?)" >&2
  exit 1
fi

for pkg in lightgbm:lib_lightgbm.dylib xgboost:libxgboost.dylib; do
  dir="$SP/${pkg%%:*}/lib"
  lib="$dir/${pkg##*:}"

  [ -f "$lib" ] || { echo "skip ${pkg%%:*}: not installed"; continue; }

  cp -f "$OMP" "$dir/libomp.dylib"

  # Adding a duplicate rpath is an error, so only add it when absent.
  if ! otool -l "$lib" 2>/dev/null | grep -q "path @loader_path "; then
    install_name_tool -add_rpath @loader_path "$lib" 2>/dev/null || true
  fi
  codesign --force --sign - "$lib" >/dev/null 2>&1

  if "$VENV/bin/python" -c "import ${pkg%%:*}" 2>/dev/null; then
    echo "ok   ${pkg%%:*} imports"
  else
    echo "FAIL ${pkg%%:*} still will not import" >&2
    exit 1
  fi
done
