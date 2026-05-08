#!/bin/bash

set -e  # Exit immediately if a command exits with a non-zero status

COMMAND=$1


# Detect python executable
# If a local venv exists prefer its python so callers don't have to `source` the script.
if [ -x "venv/bin/python" ]; then
  PYTHON="venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON=python3
elif command -v python >/dev/null 2>&1; then
  PYTHON=python
else
  echo "Python is not installed or not in PATH"
  exit 1
fi


case "$COMMAND" in
  install)
    $PYTHON -m venv venv/
    # Use the venv's python to install packages (no need to activate the shell)
    venv/bin/python -m pip install --upgrade pip
    venv/bin/python -m pip install -r requirements.txt
    cp -n tasks.sample.yaml tasks.yaml
    ;;
  venv)
    if [ ! -f venv/bin/activate ]; then
      echo "No virtualenv found. Run './app.sh install' first."
      exit 1
    fi
    echo "Starting a new shell with virtualenv activated (exit to return)..."
    # Start an interactive shell with the venv activated so user doesn't need to source.
    bash -ic 'source "venv/bin/activate"; exec bash'
    ;;
  run)
    $PYTHON main.py run
    ;;
  validate)
    $PYTHON main.py validate
    ;;
  lint)
    pylint cleany/ main.py
    ;;
  reset)
    rm -f it.json rooms.json users.json
    ;;
  android)
    case "$2" in
      deploy)
        buildozer android debug deploy run
        ;;
      debug)
        buildozer android logcat
        ;;
      shell)
        adb shell
        ;;
      push)
        adb push tasks.yaml /sdcard/
        ;;
      push-rooms)
        adb push rooms.json /sdcard/
        ;;
      push-users)
        adb push users.json /sdcard/
        ;;
      reset)
        adb shell rm /sdcard/rooms.json /sdcard/it.json /sdcard/users.json
        ;;
      *)
        echo "Unknown android command: $2"
        exit 1
        ;;
    esac
    ;;
  *)
    echo "Unknown command: $COMMAND"
    exit 1
    ;;
esac
