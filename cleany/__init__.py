
"""
PyQt6 replacement for Cleany Kivy Application
Generated port preserving task rotation, groups, scoring and dialogs.
"""
import sys
import os
import bisect
import socket
from datetime import datetime, timedelta
from fractions import Fraction

import requests
import yaml

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QVBoxLayout, QHBoxLayout, QGridLayout,
    QLabel, QPushButton, QDialog,
    QScrollArea, QCheckBox
)

from . import weather, data, schema

NUM_TASKS_DISPLAYED = 8
WRITE_DIR_ANDROID = "/sdcard/"
ROOMS_FILENAME = "rooms.json"
IT_FILENAME = "it.json"
TASKS_FILENAME = "tasks.yaml"
SCHEMA_FILENAME = "schema.json"
USERS_FILENAME = "users.json"
TIME_FMT = "%H:%M"
DATE_FMT = "%y-%m-%d"


def _get_filepath(filename):
    if os.path.exists(WRITE_DIR_ANDROID):
        return os.path.join(WRITE_DIR_ANDROID, filename)
    return filename


def _queued_color(due_date):
    today = datetime.now().date()
    delta = (due_date - today).days
    if delta == 0:
        return "yellow"
    if delta < 0:
        return "red"
    return "lightgreen"


def _parse_period(period):
    unit = period[-1]
    value = int(period[:-1])
    if unit == "d":
        return timedelta(days=value)
    if unit == "w":
        return timedelta(weeks=value)
    if unit == "m":
        return timedelta(days=value * 30)
    if unit == "h":
        return timedelta(hours=value)
    return timedelta(days=1)


class TaskManager(QWidget):

    def __init__(self):
        super().__init__()

        root = QVBoxLayout(self)
        top = QHBoxLayout()

        self.room_tasks_layout = QVBoxLayout()

        right = QVBoxLayout()

        self.time_label = QLabel()
        self.time_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.time_label.setStyleSheet("font-size:84px;")

        self.date_label = QLabel()
        self.date_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.date_label.setStyleSheet("font-size:32px;")

        self.points_layout = QGridLayout()
        self.indefinite_tasks_layout = QVBoxLayout()

        right.addWidget(self.time_label)
        right.addWidget(self.date_label)
        right.addLayout(self.points_layout)
        right.addLayout(self.indefinite_tasks_layout)

        top.addLayout(self.room_tasks_layout, 2)
        top.addLayout(right, 1)

        root.addLayout(top)

        self.weather_label = QLabel("Fetching weather...")
        root.addWidget(self.weather_label)

        self._load_yaml()
        self._initiate_users()
        self._initiate_tasks()

        self._display_users()
        self._display_tasks()

        self.update_datetime()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_datetime)
        self.timer.start(1000)

        self.weather_timer = QTimer(self)
        self.weather_timer.timeout.connect(self.update_weather)
        self.weather_timer.start(600000)

        self.update_weather()

    def _load_yaml(self):
        with open(_get_filepath(TASKS_FILENAME), "r", encoding="utf8") as f:
            self.data = yaml.safe_load(f)
        schema.validate_yaml(self.data, SCHEMA_FILENAME)

    def update_datetime(self):
        now = datetime.now()
        self.time_label.setText(now.strftime(TIME_FMT))
        self.date_label.setText(now.strftime(DATE_FMT))

    def update_weather(self):
        try:
            temp, cond = weather.get_weather(
                self.data["location"]["lat"],
                self.data["location"]["lon"]
            )
            host = socket.getfqdn()
            self.weather_label.setText(
                f"Temp: {temp}°C; Condition: {cond}\nHostname: {host}"
            )
        except requests.exceptions.RequestException as e:
            self.weather_label.setText(str(e))

    def _normalize_user_groups(self, users_def):
        out = []
        for item in users_def:
            if isinstance(item, list):
                out.append(item)
            else:
                out.append([item])
        return out

    def _user_display_name(self, entry):
        if isinstance(entry, list):
            return " and ".join(entry)
        return entry

    def _get_new_duedate(self, task_dict, init):
        if isinstance(task_dict, str):
            period_str = task_dict
            period = _parse_period(period_str)
        else:
            period_str = task_dict["period"]
            period = _parse_period(period_str)
            if "stagger" in task_dict and init:
                period += _parse_period(task_dict["stagger"])
        return period_str, (datetime.now() + period).date()

    def _assign_task(self, room_name, task_name, current_user, init, advance_user):
        room = self.data["rooms"][room_name]
        task_obj = room["tasks"][task_name]

        if isinstance(task_obj, dict) and "users" in task_obj:
            groups = self._normalize_user_groups(task_obj["users"])
        else:
            groups = self._normalize_user_groups(room["users"])

        idx = 0
        for i, g in enumerate(groups):
            if current_user in g or self._user_display_name(g) == current_user:
                idx = i
                break

        if advance_user:
            idx = (idx + 1) % len(groups)

        new_user = self._user_display_name(groups[idx])
        period_str, due_date = self._get_new_duedate(task_obj, init)

        bisect.insort(
            self.assigned_tasks,
            data.new_task(new_user, room_name, task_name, due_date, period_str)
        )
        return new_user

    def _initiate_users(self):
        self.users = data.Users(_get_filepath(USERS_FILENAME))
        if self.users.size() == 0:
            for user in self.data["users"]:
                self.users.initiate_user(user)

    def _initiate_tasks(self):
        self.assigned_tasks = data.Tasks(_get_filepath(ROOMS_FILENAME))

        if len(self.assigned_tasks) == 0:
            for room, details in self.data["rooms"].items():
                groups = self._normalize_user_groups(details["users"])
                user = groups[-1][-1]

                for task_name, task in details["tasks"].items():
                    if isinstance(task, str) or "users" not in task:
                        user = self._assign_task(room, task_name, user, True, True)
                    else:
                        tgroups = self._normalize_user_groups(task["users"])
                        self._assign_task(
                            room,
                            task_name,
                            tgroups[-1][-1],
                            True,
                            True
                        )

        self.indefinite_tasks = data.IndefiniteTasks(_get_filepath(IT_FILENAME))

        if len(self.indefinite_tasks) == 0:
            for task, details in self.data["indefinite_tasks"].items():
                bisect.insort(
                    self.indefinite_tasks,
                    data.new_indefinite_task(
                        details["users"][0],
                        task,
                        details["repetitions"]
                    )
                )

    def clear_layout(self, layout):
        while layout.count():
            item = layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _format_points(self, points):
        frac = Fraction(float(points)).limit_denominator(12)
        if abs(float(frac) - float(points)) < 1e-9 and frac.denominator != 1:
            return f"{frac.numerator}/{frac.denominator}"
        return str(round(float(points), 2))

    def _display_users(self):
        # Remove old widgets properly
        while self.points_layout.count():
            item = self.points_layout.takeAt(0)

            if item.widget():
                item.widget().deleteLater()

        self.points_layout.addWidget(QLabel("Name"), 0, 0)
        self.points_layout.addWidget(QLabel("Points"), 0, 1)

        for row, (user, pts) in enumerate(self.users.all(), start=1):
            self.points_layout.addWidget(QLabel(user), row, 0)

            lbl = QLabel(self._format_points(pts))

            if pts > 0:
                lbl.setStyleSheet("color: green")
            elif pts < 0:
                lbl.setStyleSheet("color: red")

            self.points_layout.addWidget(lbl, row, 1)

    def _display_tasks(self):
        self.clear_layout(self.room_tasks_layout)
        self.clear_layout(self.indefinite_tasks_layout)

        for task in self.assigned_tasks[:NUM_TASKS_DISPLAYED]:
            btn = QPushButton(
                f"Task: {task.name}\nWho: {task.user}\nWhere: {task.room}\nDue: {task.due_date} ({task.period})"
            )
            btn.setStyleSheet(f"background:{_queued_color(task.due_date)}")
            btn.clicked.connect(lambda _, t=task: self.confirm_task(t))
            self.room_tasks_layout.addWidget(btn)

        for task in self.indefinite_tasks:
            btn = QPushButton(
                f"{task.name}\n{task.user}\n{task.rep}/{task.total_reps}"
            )
            btn.clicked.connect(lambda _, t=task: self.confirm_indefinite(t))
            self.indefinite_tasks_layout.addWidget(btn)

    def complete_task(self, task):
        self.assigned_tasks.remove(task)
        self._assign_task(task.room, task.name, task.user, False, True)
        self._display_tasks()

    def complete_indefinite(self, task):
        i, task = self.indefinite_tasks.increment(task.name)
        if task.rep > task.total_reps:
            users = self.data["indefinite_tasks"][task.name]["users"]
            new_user = users[(users.index(task.user) + 1) % len(users)]
            self.indefinite_tasks.reset(i, new_user)
        self._display_tasks()

    def confirm_task(self, task):
        dlg = QDialog(self)
        dlg.setWindowTitle("Confirm Task")

        layout = QVBoxLayout(dlg)
        layout.addWidget(
            QLabel(f"{task.user}, completed {task.name} in {task.room}?")
        )

        ok = QPushButton("Confirm")
        cancel = QPushButton("Cancel")

        different = QPushButton(
            "Complete task as a different user"
        )

        ok.clicked.connect(lambda: (self.complete_task(task), dlg.accept()))
        cancel.clicked.connect(dlg.reject)
        different.clicked.connect(
            lambda: (
                dlg.accept(),
                self.different_user_dialog(
                    task,
                    False
                )
                )
        )

        layout.addWidget(ok)
        layout.addWidget(cancel)
        layout.addWidget(different)

        dlg.exec()

    def confirm_indefinite(self, task):
        dlg = QDialog(self)
        layout = QVBoxLayout(dlg)

        layout.addWidget(QLabel(task.name))

        ok = QPushButton("Confirm")
        cancel = QPushButton("Cancel")
        different = QPushButton(
        "Complete task as a different user"
        )

        ok.clicked.connect(
            lambda: (self.complete_indefinite(task), dlg.accept())
        )
        cancel.clicked.connect(dlg.reject)

        different.clicked.connect(
            lambda: (
                dlg.accept(),
                self.different_user_dialog(
                    task,
                    True
                )
            )
        )

        layout.addWidget(ok)
        layout.addWidget(cancel)
        layout.addWidget(different)

        dlg.exec()

    def _members_for_display(self, display_name, room_name, task_name=None):

        room = self.data["rooms"].get(room_name)
        if not room:
            return []

        if task_name:
            task_def = room["tasks"].get(task_name)

            if isinstance(task_def, dict) and "users" in task_def:
                groups = self._normalize_user_groups(task_def["users"])

                for g in groups:
                    if self._user_display_name(g) == display_name:
                        return g

        groups = self._normalize_user_groups(room["users"])

        for g in groups:
            if self._user_display_name(g) == display_name:
                return g

        return []
    
    def _flat_members_for_task(self, task, indefinite):

        members = []

        if indefinite:
            users = self.data["indefinite_tasks"][task.name]["users"]

            for u in users:
                if u not in members:
                    members.append(u)

            return members

        room = self.data["rooms"].get(task.room)

        if not room:
            return members

        task_def = room["tasks"].get(task.name)

        if isinstance(task_def, dict) and "users" in task_def:
            groups = self._normalize_user_groups(task_def["users"])
        else:
            groups = self._normalize_user_groups(room["users"])

        for g in groups:
            for m in g:
                if m not in members:
                    members.append(m)

        return members

    def _surplus_and_deficit(self, up, down):
        self.users.up_and_down(up, down)
        self._display_users()

    def different_user_dialog(self, task, indefinite):

        dlg = QDialog(self)

        dlg.setWindowTitle("Complete task as a different user")
        layout = QVBoxLayout(dlg)
        layout.addWidget(QLabel(f"Complete {task.name} as:"))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        container = QWidget()
        users_layout = QVBoxLayout(container)
        checkboxes = {}

        for member in self._flat_members_for_task(
            task,
            indefinite
        ):

            cb = QCheckBox(member)
            checkboxes[member] = cb
            users_layout.addWidget(cb)

        scroll.setWidget(container)
        layout.addWidget(scroll)

        def complete_selected():
            selected_members = [
                user
                for user, cb
                in checkboxes.items()
                if cb.isChecked()
            ]
            if not selected_members:
                dlg.accept()
                return
            if indefinite:
                self.complete_indefinite(task)
                intended_members = [task.user]
            else:
                self.complete_task(task)
                intended_members = self._members_for_display(
                    task.user,
                    task.room,
                    task.name
                )
                if not intended_members:
                    intended_members = [task.user]

            missing = [m for m in intended_members if m not in selected_members]
            n_intended = len(intended_members)
            n_selected = len(selected_members)

            per_doer = float(n_intended) / float(n_selected)

            up_map = {}
            down_map = {}

            for s in selected_members:
                if s in intended_members:
                    delta = per_doer - 1.0
                    if delta > 0:
                        up_map[s] = (
                            up_map.get(s, 0)
                            + delta
                        )
                    elif delta < 0:
                        down_map[s] = (
                            down_map.get(s, 0)
                            + (-delta)
                        )
                else:
                    up_map[s] = (
                        up_map.get(s, 0)
                        + per_doer
                    )

            for m in missing:
                down_map[m] = (
                    down_map.get(m, 0)
                    + 1.0
                )
                
            if up_map or down_map:
                self._surplus_and_deficit(
                    up_map,
                    down_map
                )
            dlg.accept()

        
        complete_btn = QPushButton("Complete for selected users")
        cancel_btn = QPushButton("Cancel")

        complete_btn.clicked.connect(complete_selected)
        cancel_btn.clicked.connect(dlg.reject)

        layout.addWidget(complete_btn)
        layout.addWidget(cancel_btn)

        dlg.resize(500, 600)
        dlg.exec()
        
        


class CleanyApp(QMainWindow):

    def __init__(self):
        super().__init__()

        self.setCentralWidget(TaskManager())

        show_cursor = int(os.environ.get("CLEANY_SHOW_CURSOR", "0"))
        if not show_cursor:
            QApplication.setOverrideCursor(Qt.CursorShape.BlankCursor)

        self.showFullScreen()


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = CleanyApp()
    window.show()
    sys.exit(app.exec())
