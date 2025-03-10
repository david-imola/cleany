"""
Entry point for the application
"""

import argparse

from cleany import CleanyApp, schema, TASKS_FILENAME, SCHEMA_FILENAME

if __name__ == "__main__":

    parser = argparse.ArgumentParser(description="Run or validate the program.")
    subparsers = parser.add_subparsers(dest="command", required=False)
    subparsers.add_parser("run", help="Run the program.")
    subparsers.add_parser("validate", help="Validate the tasks.yaml file.")
    args = parser.parse_args()

    if args.command is None or args.command == "run":
        CleanyApp().run()
    elif args.command == "validate":
        schema.validate(TASKS_FILENAME, SCHEMA_FILENAME)
