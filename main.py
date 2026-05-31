"""
Entry point for the application
"""

import argparse
import sys

from PyQt6.QtWidgets import QApplication

from cleany import CleanyApp, schema, TASKS_FILENAME, SCHEMA_FILENAME


def run_app():
    app = QApplication(sys.argv)
    window = CleanyApp()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="Run or validate the program.")
    subparsers = parser.add_subparsers(dest="command", required=False)

    subparsers.add_parser("run", help="Run the program.")
    subparsers.add_parser("validate", help="Validate the tasks.yaml file.")

    args = parser.parse_args()

    if args.command is None or args.command == "run":
        run_app()

    elif args.command == "validate":
        schema.validate(TASKS_FILENAME, SCHEMA_FILENAME)