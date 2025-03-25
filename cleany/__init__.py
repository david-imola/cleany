"""
The Cleany Kivy Application
"""
import bisect
from datetime import datetime, timedelta
import json
import os
import requests

import yaml
import kivy
from kivy.app import App
from kivy.clock import Clock
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup

from . import weather, tasks, schema

kivy.require('2.1.0')

NUM_TASKS_DISPLAYED = 8
WRITE_DIR_ANDROID = "/sdcard/"
ROOMS_FILENAME = "rooms.json"
IT_FILENAME = "it.json"
TASKS_FILENAME = "tasks.yaml"
SCHEMA_FILENAME = "schema.json"
DATE_FMT = "%d/%m\n%H:%M"


def _get_filepath(filename):
    if os.path.exists(WRITE_DIR_ANDROID):
        return os.path.join(WRITE_DIR_ANDROID, filename)
    return filename


def _queued_color(due_date):
    today = datetime.now().date()
    delta = (due_date - today).days
    if delta == 0:
        return (1, 1, 0, 1)
    if delta < 0:
        return (1, 0, 0, 1)
    # if delta > 0
    return (0, 1, 0, 1)


def _parse_period(period):
    unit = period[-1]
    value = int(period[:-1])
    if unit == 'd':
        return timedelta(days=value)
    if unit == 'w':
        return timedelta(weeks=value)
    if unit == 'm':
        return timedelta(days=value * 30)
    return timedelta(days=1)


class _TaskManager(BoxLayout):

    # pylint: disable=too-many-instance-attributes
    # More than 7 is fine in this case

    def __init__(self, **kwargs):
        super().__init__(orientation='vertical', **kwargs)

        # Top layout
        layout = BoxLayout(orientation='horizontal', size_hint=(1, .9))
        self.room_tasks_layout = BoxLayout(orientation='vertical')
        right_section = BoxLayout(orientation='vertical')
        self.datetime_label = Label(text=str(datetime.now().strftime(DATE_FMT)),
                                    font_size='96sp')
        self.indefinite_tasks_layout = BoxLayout(orientation='vertical')

        right_section.add_widget(self.datetime_label)
        right_section.add_widget(self.indefinite_tasks_layout)

        layout.add_widget(self.room_tasks_layout)
        layout.add_widget(right_section)

        # Bottom label
        self.weather_label = Label(text="Fetching weather...", size_hint=(1, .1))

        # Define popup now for linter
        self.popup = None

        # Add top layout and bottom label to the parent layout
        self.add_widget(layout)
        self.add_widget(self.weather_label)

        self._load_yaml()
        self._initiate_tasks()
        self._display_tasks()

        Clock.schedule_interval(self._update_datetime, 1)
        Clock.schedule_interval(self._update_weather, 600)  # Update weather every 10 minutes
        Clock.schedule_interval(self._display_tasks, 3600) # Redraw tasks every hour
        self._update_weather(0)  # Initial weather fetch

    def _update_datetime(self, _):
        self.datetime_label.text = str(datetime.now().strftime(DATE_FMT))

    def _update_weather(self, _):
        try:
            temp, condition = weather.get_weather(
                self.data['location']['lat'], self.data['location']['lon'])
            self.weather_label.text = f"Temp: {temp}°C\nCondition: {condition}"
        except requests.exceptions.RequestException as e:
            self.weather_label.text = f"Weather update failed: {e}"

    def _load_yaml(self):
        tasks_path = _get_filepath(TASKS_FILENAME)
        with open(tasks_path, "r", encoding="utf-8") as file:
            self.data = yaml.safe_load(file)

        # Validate against our schema
        schema.validate_yaml(self.data, SCHEMA_FILENAME)

    def _get_new_user(self, room_dict, task_dict, current_user):
        # true if the yaml contents of the task is just the period
        is_simple = isinstance(task_dict, str)
        users = room_dict['users']
        if not is_simple:
            if "users" in task_dict:
                users = task_dict["users"]
        pos = users.index(current_user)
        pos = pos + 1
        if pos >= len(users):
            pos = 0
        return users[pos]

    def _get_new_duedate(self, task_dict, init):
        # true if the yaml contents of the task is just the period
        is_simple = isinstance(task_dict, str)
        # Find the new due date
        if is_simple:
            period_str = task_dict
            period = _parse_period(period_str)
        else:
            period_str = task_dict["period"]
            period = _parse_period(period_str)
            if "stagger" in task_dict and init:
                stagger = _parse_period(task_dict["stagger"])
                period = period + stagger
        return period_str, (datetime.now() + period).date()

    # pylint: disable=too-many-arguments,too-many-positional-arguments
    # Ehh
    def _assign_task(self, room_name, task_name, current_user, init, advance_user):

        # Get data that was loaded from the yaml file
        room = self.data['rooms'][room_name]
        task_obj = room['tasks'][task_name]

        # Find the new user
        if advance_user:
            new_user = self._get_new_user(room, task_obj, current_user)
        else:
            new_user = current_user

        # Find the new due date and the period string
        period_str, due_date = self._get_new_duedate(task_obj, init)

        # Insert so list remains sorted
        bisect.insort(self.assigned_tasks,
                      tasks.new_task(new_user, room_name, task_name, due_date, period_str))
        return new_user

    def _initiate_tasks(self):

        # Get file paths
        rooms_path = _get_filepath(ROOMS_FILENAME)
        it_path = _get_filepath(IT_FILENAME)

        # Initate Assigned Tasks
        self.assigned_tasks = tasks.Tasks(rooms_path)
        if len(self.assigned_tasks) == 0:
            for room, details in self.data['rooms'].items():
                # find last user because _assign_tasks assigns to the next user, and we want
                # to start on the first user
                user = details['users'][-1]
                for task_name, task in details['tasks'].items():
                    if isinstance(task, str) or "users" not in task:
                        user = self._assign_task(room, task_name, user, True, True)
                    else:
                        # if the task overrides the user section, ignore the rolling user assignment
                        # and just assign the first user
                        self._assign_task(room, task_name, task["users"][0], True, True)

        # Initiate Indefinite tasks
        self.indefinite_tasks = tasks.IndefiniteTasks(it_path)
        if len(self.indefinite_tasks) == 0:
            for task, details in self.data['indefinite_tasks'].items():
                user0 = details['users'][0]
                reps = details['repetitions']
                bisect.insort(self.indefinite_tasks, tasks.new_indefinite_task(user0, task, reps))

    def _display_tasks(self, _=None):
        self.room_tasks_layout.clear_widgets()
        self.indefinite_tasks_layout.clear_widgets()

        # Display assigned Tasks
        for i in range(min(NUM_TASKS_DISPLAYED, len(self.assigned_tasks))):
            task = self.assigned_tasks[i]
            due_date = task.due_date
            color = _queued_color(due_date)
            btn = Button(
            text=
            f"Task: {task.name}\nWho: {task.user}\nWhere: {task.room}"
            f"\nDue Date: {task.due_date} ({task.period})",
            background_color=color)
            # pylint: disable=no-member
            btn.bind(on_press=lambda _, t=task: self._show_confirmation_dialog(t, False))
            self.room_tasks_layout.add_widget(btn)

        # Display Indefinete tasks
        for task in self.indefinite_tasks:
            btn = Button(text=f"{task.name}\n{task.user}\n{task.rep}/{task.total_reps}")
            # pylint: disable=no-member
            btn.bind(on_press=lambda instance,
                     t=task: self._show_confirmation_dialog(t, True, instance))
            self.indefinite_tasks_layout.add_widget(btn)

    def _show_confirmation_dialog(self, task, indefinite, instance=None):
        # Create the popup content
        content = BoxLayout(orientation='vertical')
        txt = f"{task.user}, are you sure you have completed this task?\n\n{task.name}"
        if not indefinite:
            txt = txt + f" in {task.room}"
        content.add_widget(Label(text=txt))

        # Define the buttons for the dialog
        cancel_button = Button(text="Cancel", on_press=lambda _: self.popup.dismiss())

        def complete_task(_):
            if indefinite:
                self._complete_indefinite_task(task.name, instance)
            else:
                self._complete_task(task)
            self.popup.dismiss()
        confirm_button = Button(text="Confirm", on_press=complete_task)

        # Add buttons to the content layout
        content.add_widget(cancel_button)
        content.add_widget(confirm_button)

        # Add the non-advance task completion button if not indefinite task
        if not indefinite:
            def complete_task_persist_user(_):
                self._complete_task(task, advance_user=False)
                self.popup.dismiss()
            persist_user_button = Button(text="Complete task, but don't advance user",
                                         on_press=complete_task_persist_user)
            content.add_widget(persist_user_button)

        # Create the popup
        self.popup = Popup(title="Confirm Task Completion",
                           content=content,
                           size_hint=(0.7, 0.5),
                           auto_dismiss=False)

        # Open the popup
        self.popup.open()

    def _complete_task(self, task, advance_user=True):
        self.assigned_tasks.remove(task)
        self._assign_task(task.room, task.name, task.user, False, advance_user)
        self._display_tasks()

    def _complete_indefinite_task(self, task_name, instance):
        i, task = self.indefinite_tasks.increment(task_name)

        # If user has finished the required number of repetitions, reset reps back to 1
        # And go to the next user
        if task.rep > task.total_reps:
            users = self.data['indefinite_tasks'][task.name]['users']
            new_user = users[(users.index(task.user) + 1) % len(users)]
            self.indefinite_tasks.reset(i, new_user)
        instance.text = f"{task.name}\n{task.user}\n{task.rep}/{task.total_reps}"


class CleanyApp(App):
    """
    The Cleany kivy application object. Call CleanyApp().run() to run it.
    """
    def build(self):
        return _TaskManager()
