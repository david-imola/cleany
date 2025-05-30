#!/bin/bash

set -e  # Exit immediately if a command exits with a non-zero status

COMMAND=$1

case "$COMMAND" in
  install)
    python -m venv venv/
    source venv/bin/activate
    pip install -r requirements.txt
    cp -n tasks.sample.yaml tasks.yaml
    ;;
  venv)
    source venv/bin/activate
    unset COMMAND
    ;;
  run)
    python main.py run
    ;;
  validate)
    python main.py validate
    ;;
  lint)
    pylint cleany/ main.py
    ;;
  reset)
    rm it.json rooms.json users.json
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
