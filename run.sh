#!/bin/sh

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
VENV_ACTIVATE="$SCRIPT_DIR/.venv/bin/activate"

if [ ! -f "$VENV_ACTIVATE" ]; then
    printf '%s\n' "Virtual environment not found: $VENV_ACTIVATE" >&2
    exit 1
fi

cleanup() {
    if command -v deactivate >/dev/null 2>&1; then
        deactivate
    fi
}

trap cleanup 0 HUP INT TERM

. "$VENV_ACTIVATE"
cd "$SCRIPT_DIR" || exit 1

PYTHONPATH=src python -m jr100emu.app --rom datas/jr100rom.prg --joystick --audio --scale 3 "$@"
