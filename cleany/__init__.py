"""
The Cleany Kivy Application
"""
import bisect
from datetime import datetime, timedelta
import json
import os
import requests
import socket

import yaml
import kivy
from kivy.app import App
from kivy.clock import Clock
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.uix.popup import Popup
from kivy.uix.behaviors import ButtonBehavior
from kivy.core.window import Window
from kivy.uix.checkbox import CheckBox
from kivy.uix.scrollview import ScrollView
from kivy.uix.gridlayout import GridLayout as KivyGrid
from kivy.metrics import dp

from . import weather, data, schema

kivy.require('2.1.0')

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
    if unit == 'h':
        return timedelta(hours=value)
    return timedelta(days=1)


class _TaskManager(BoxLayout):

    # pylint: disable=too-many-instance-attributes
    # More than 7 is fine in this case

    def __init__(self, **kwargs):
        super().__init__(orientation='vertical', **kwargs)

        # Top layout
        layout = BoxLayout(orientation='horizontal', size_hint=(1, .9))

        # Right layout
        self.room_tasks_layout = BoxLayout(orientation='vertical')
        right_section = BoxLayout(orientation='vertical')
        self.time_label = Label(text=str(datetime.now().strftime(TIME_FMT)),
                                    font_size='84sp')
        self.date_label = Label(text=str(datetime.now().strftime(DATE_FMT)),
                                    font_size='32sp')
        self.points_layout = GridLayout(cols=2)
        self.indefinite_tasks_layout = BoxLayout(orientation='vertical')
        right_section.add_widget(self.time_label)
        right_section.add_widget(self.date_label)
        right_section.add_widget(self.points_layout)
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
        self._initiate_users()
        self._display_users()
        self._initiate_tasks()
        self._display_tasks()

        Clock.schedule_interval(self._update_datetime, 1)
        Clock.schedule_interval(self._update_weather, 600)  # Update weather every 10 minutes
        Clock.schedule_interval(self._display_tasks, 3600) # Redraw tasks every hour
        self._update_weather(0)  # Initial weather fetch

    def _update_datetime(self, _):
        self.time_label.text = str(datetime.now().strftime(TIME_FMT))
        self.date_label.text = str(datetime.now().strftime(DATE_FMT))

    def _update_weather(self, _):
        try:
            temp, condition = weather.get_weather(
                self.data['location']['lat'], self.data['location']['lon'])
            self.weather_label.text = f"Temp: {temp}°C; Condition: {condition}"
        except requests.exceptions.RequestException as e:
            self.weather_label.text = f"Weather update failed: {e}"
        host = socket.gethostbyname(socket.gethostname())
        self.weather_label.text += f"\nHostname: {host}"
        

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

        # expand any grouped users into a flat list before searching
        users = self._expand_user_groups(users) if isinstance(users, list) else [users]

        try:
            pos = users.index(current_user)
        except ValueError:
            # If current_user isn't in the list (possible with grouped inputs),
            # start from the beginning to avoid crashing.
            pos = 0
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

    def _expand_user_groups(self, users_def):
        """
        Given a users definition which may contain strings or lists (groups),
        return a flattened list preserving order. E.g.
        ['alice', ['bob','charlie'], 'diana'] -> ['alice','bob','charlie','diana']
        """
        out = []
        for item in users_def:
            if isinstance(item, list):
                out.extend(item)
            else:
                out.append(item)
        return out

    def _user_display_name(self, entry):
        """Return a human-friendly display for a user entry which may be a string or list."""
        if isinstance(entry, list):
            if len(entry) == 2:
                return f"{entry[0]} and {entry[1]}"
            return ' and '.join(entry)
        return entry

    def _normalize_user_groups(self, users_def):
        """
        Convert a users definition (which may contain strings or lists) into
        a list of groups where each group is a list of member names.
        E.g. ['alice', ['bob','charlie']] -> [['alice'], ['bob','charlie']]
        """
        out = []
        for item in users_def:
            if isinstance(item, list):
                out.append(item)
            else:
                out.append([item])
        return out

    def _members_for_display(self, display_name, room_name, task_name=None):
        """
        Given a display name like 'david and francesco', find the corresponding
        member list in the room/task definitions. If task_name is provided, check
        task-level users first.
        """
        room = self.data['rooms'].get(room_name)
        if not room:
            return []

        # Check task override first
        if task_name:
            task_def = room['tasks'].get(task_name)
            if isinstance(task_def, dict) and 'users' in task_def:
                groups = self._normalize_user_groups(task_def['users'])
                for g in groups:
                    if self._user_display_name(g) == display_name:
                        return g

        # Fallback to room users
        groups = self._normalize_user_groups(room['users'])
        for g in groups:
            if self._user_display_name(g) == display_name:
                return g
        return []

    def _flat_members_for_task(self, task, indefinite):
        """
        Return a flattened list of member names eligible for a task.
        For grouped definitions this returns each member individually, preserving order and
        removing duplicates.
        """
        members = []
        if indefinite:
            # indefinite_tasks store simple user lists
            users = self.data['indefinite_tasks'][task.name]['users']
            for u in users:
                if u not in members:
                    members.append(u)
            return members

        room = self.data['rooms'].get(task.room)
        if not room:
            return members

        task_def = room['tasks'].get(task.name)
        if isinstance(task_def, dict) and 'users' in task_def:
            groups = self._normalize_user_groups(task_def['users'])
        else:
            groups = self._normalize_user_groups(room['users'])

        for g in groups:
            for m in g:
                if m not in members:
                    members.append(m)
        return members

    # pylint: disable=too-many-arguments,too-many-positional-arguments
    # Ehh
    def _assign_task(self, room_name, task_name, current_user, init, advance_user):

        # Get data that was loaded from the yaml file
        room = self.data['rooms'][room_name]
        task_obj = room['tasks'][task_name]

        # Determine groups for this task (task-level override or room-level)
        if isinstance(task_obj, dict) and 'users' in task_obj:
            groups = self._normalize_user_groups(task_obj['users'])
        else:
            groups = self._normalize_user_groups(room['users'])

        # current_user may be a display-name or a member; find group index
        group_index = None
        for i, g in enumerate(groups):
            if current_user in g:
                group_index = i
                break
            # also allow matching when current_user is a display string like 'a and b'
            if self._user_display_name(g) == current_user:
                group_index = i
                break

        if group_index is None:
            # fall back to first group
            group_index = 0

        # Find the new group index if advancing
        if advance_user:
            new_group_index = (group_index + 1) % len(groups)
        else:
            new_group_index = group_index

        new_user_group = groups[new_group_index]

        # For display and storage, set the 'user' to a display string like 'a and b'
        new_user_display = self._user_display_name(new_user_group)

        # Find the new due date and the period string
        period_str, due_date = self._get_new_duedate(task_obj, init)

        # Insert so list remains sorted; store display name as the assigned user
        bisect.insort(self.assigned_tasks,
                      data.new_task(new_user_display, room_name, task_name, due_date, period_str))
        return new_user_display


    def _initiate_users(self):

        # Get file paths
        user_path = _get_filepath(USERS_FILENAME)

        # Initate users
        self.users = data.Users(user_path)
        if self.users.size() == 0:
            for user in self.data['users']:
                self.users.initiate_user(user)

    def _initiate_tasks(self):

        # Get file paths
        rooms_path = _get_filepath(ROOMS_FILENAME)
        it_path = _get_filepath(IT_FILENAME)

        # Initate Assigned Tasks
        self.assigned_tasks = data.Tasks(rooms_path)
        if len(self.assigned_tasks) == 0:
            for room, details in self.data['rooms'].items():
                # find last group because _assign_task assigns to the next group, and we want
                # to start on the first group
                # expand any grouped users
                room_groups = self._normalize_user_groups(details['users'])
                # pick a member from the last group so advancing moves to the first group
                user = room_groups[-1][-1]
                for task_name, task in details['tasks'].items():
                    if isinstance(task, str) or "users" not in task:
                        user = self._assign_task(room, task_name, user, True, True)
                    else:
                        # if the task overrides the user section, ignore the rolling user assignment
                        # and just assign the first user
                        task_users = task["users"]
                        # if task overrides can also have groups, normalize
                        if isinstance(task_users, list):
                            task_groups = self._normalize_user_groups(task_users)
                            # pick a member from the last group so advancing moves to the first group
                            self._assign_task(room, task_name, task_groups[-1][-1], True, True)
                        else:
                            self._assign_task(room, task_name, task["users"], True, True)

        # Initiate Indefinite tasks
        self.indefinite_tasks = data.IndefiniteTasks(it_path)
        if len(self.indefinite_tasks) == 0:
            for task, details in self.data['indefinite_tasks'].items():
                user0 = details['users'][0]
                reps = details['repetitions']
                bisect.insort(self.indefinite_tasks, data.new_indefinite_task(user0, task, reps))



    def _display_users(self):
        self.points_layout.clear_widgets()

        headers = ["Name", "Surplus/Deficit Points"]

        # Add header row
        for header in headers:
            self.points_layout.add_widget(Label(text=header, bold=True))

        # Add data rows
        for user, points in self.users.all():
            if points == 0:
                color = "white"
            elif points > 0:
                color = "green"
            else:
                color = "red"
            self.points_layout.add_widget(Label(text=user))
            self.points_layout.add_widget(Label(text=self._format_points(points), color=color))

    def _format_points(self, points):
        """Format points for display: prefer simple fractions (like 2/3) when possible,
        otherwise show up to 2 decimals and trim trailing zeros.
        """
        from fractions import Fraction

        try:
            f = float(points)
        except Exception:
            return str(points)

        # Try to express as a fraction with a reasonably small denominator for readability
        frac = Fraction(f).limit_denominator(12)
        # If the fraction represents the float exactly or closely, and denominator > 1, show it
        if abs(frac - f) < 1e-9 and frac.denominator != 1:
            # Render improper fractions as mixed numbers, e.g. 3/2 -> '1 and 1/2'
            num = frac.numerator
            den = frac.denominator
            if abs(num) > den:
                whole = num // den
                rem = abs(num) % den
                if rem == 0:
                    return str(whole)
                return f"{whole} and {rem}/{den}"
            return f"{num}/{den}"

        # Otherwise fall back to two decimals trimmed
        s = f"{f:.2f}"
        if '.' in s:
            s = s.rstrip('0').rstrip('.')
        return s


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

    def _find_users_for_task(self, task, indefinite):
        """
        Given the parsed YAML data, a room name, and a task name,
        return the list of users assigned to that task.
        """
        if indefinite:
            return self.data['indefinite_tasks'][task.name]['users']

        room = self.data['rooms'].get(task.room)
        if not room:
            return []  # Room not found

        task_def = room['tasks'].get(task.name)
        if not task_def:
            return []  # Task not found

        # If users are specified for the task, use those (and return group display names)
        if isinstance(task_def, dict) and "users" in task_def:
            users = task_def["users"]
            groups = self._normalize_user_groups(users)
            return [self._user_display_name(g) for g in groups]

        # Otherwise, fall back to the users assigned to the room (expand into groups)
        groups = self._normalize_user_groups(room["users"])
        return [self._user_display_name(g) for g in groups]

    def _different_user_dialog(self, task, indefinite, instance):
        # Create new popup content using a ScrollView so it never overflows
        content = BoxLayout(orientation='vertical')
        txt = f"Complete task {task.name} as different user:"
        header = Label(text=txt, size_hint_y=None, height=40)
        content.add_widget(header)



        # Show individual members (flattened from groups) so any member can be selected
        flat_members = self._flat_members_for_task(task, indefinite)
        checkboxes = {}

        # Scrollable grid for members
        row_height = dp(56)
        grid = KivyGrid(cols=1, spacing=dp(6), padding=dp(6), size_hint_y=None)
        grid.bind(minimum_height=grid.setter('height'))

        class Row(ButtonBehavior, BoxLayout):
            pass

        for member in flat_members:
            row = Row(orientation='horizontal', size_hint_y=None, height=row_height)
            row.padding = (dp(12), dp(8))
            row.spacing = dp(12)
            cb = CheckBox(size_hint=(None, None), size=(dp(48), dp(48)))
            checkboxes[member] = cb
            def make_toggle(chk):
                return lambda *_: setattr(chk, 'active', not chk.active)
            row.bind(on_press=make_toggle(cb))
            lbl = Label(text=member, halign='left', valign='middle')
            lbl.size_hint_x = 1
            lbl.bind(size=lambda inst, sz: setattr(inst, 'text_size', (inst.width, inst.height)))
            cb.bind(active=lambda chk, val, lbl=lbl: setattr(lbl, 'color', (0.4, 1, 0.4, 1) if val else (1,1,1,1)))
            row.add_widget(cb)
            row.add_widget(lbl)
            grid.add_widget(row)

        scroll = ScrollView(size_hint=(1, 0.6))
        scroll.add_widget(grid)
        content.add_widget(scroll)

        def complete_selected_users(_):
            selected_members = [u for u, cb in checkboxes.items() if cb.active]
            # Deduplicate selections in case of unexpected duplicates
            selected_members = list(dict.fromkeys(selected_members))
            if not selected_members:
                self.popup.dismiss()
                return
 
            # Determine intended members for this assigned group
            if indefinite:
                self._complete_indefinite_task(task.name, instance)
                # For indefinite tasks the intended member is the currently assigned user
                # (task.user), not the full list of possible users.
                intended_members = [task.user]
            else:
                self._complete_task(task, advance_user=True)
                intended_members = self._members_for_display(task.user, task.room, task.name)
                if not intended_members:
                    intended_members = [task.user]
            # Deduplicate intended members as a safety against duplicate entries
            intended_members = list(dict.fromkeys(intended_members))

            # Missing intended members are those who were supposed to do it but didn't
            missing = [m for m in intended_members if m not in selected_members]

            # Unified approach: compute the per-doer contribution as
            # per_doer = n_intended / n_selected. Each selected member effectively
            # contributed `per_doer` units. Intended members were expected to
            # contribute 1 unit each; outsiders expected 0. Apply deltas = actual - expected
            # for each selected member, and any missing intended member gets -1.
            n_intended = len(intended_members)
            n_selected = len(selected_members)
            if n_selected == 0:
                # nothing selected (should be handled earlier), just dismiss
                self.popup.dismiss()
                return

            per_doer = float(n_intended) / float(n_selected)

            up_map = {}
            down_map = {}

            # For each selected member, compute their delta
            for s in selected_members:
                if s in intended_members:
                    # intended: expected 1, actual per_doer
                    delta = per_doer - 1.0
                    if delta > 0:
                        up_map[s] = up_map.get(s, 0.0) + delta
                    elif delta < 0:
                        down_map[s] = down_map.get(s, 0.0) + (-delta)
                else:
                    # outsider: expected 0, actual per_doer
                    if per_doer != 0:
                        up_map[s] = up_map.get(s, 0.0) + per_doer

            # Any intended who didn't participate get -1
            for m in missing:
                down_map[m] = down_map.get(m, 0.0) + 1.0

            # Apply scoring maps if any adjustments exist
            if up_map or down_map:
                self._surplus_and_deficit(up=up_map, down=down_map)
            self.popup.dismiss()

        # Add action buttons
        btns = BoxLayout(size_hint_y=None, height=dp(48))
        complete_btn = Button(text="Complete for selected users", on_press=complete_selected_users)
        cancel_button = Button(text="Cancel", on_press=lambda _: self.popup.dismiss())
        btns.add_widget(complete_btn)
        btns.add_widget(cancel_button)
        content.add_widget(btns)

        # Fixed popup size so layout is predictable and buttons are clickable
        self.popup = Popup(title="Complete task as a different user",
                           content=content, size_hint=(0.9, 0.7),
                           auto_dismiss=False)
        self.popup.open()

    def _show_confirmation_dialog(self, task, indefinite, instance=None):
        # Use the same Grid/Row + ScrollView pattern as _different_user_dialog so the
        # confirmation popup looks consistent and touch-friendly.
        content = BoxLayout(orientation='vertical')

        txt = f"{task.user}, are you sure you have completed this task?"

        # Message grid (single-row) using the same Row/Grid pattern
        row_height = dp(56)
        grid = KivyGrid(cols=1, spacing=dp(6), padding=dp(6), size_hint_y=None)
        grid.bind(minimum_height=grid.setter('height'))

        class Row(ButtonBehavior, BoxLayout):
            pass

        msg_text = f"{task.name}"
        if not indefinite:
            msg_text = msg_text + f" in {task.room}"

        # Compose single-line confirmation text and center it vertically
        txt = f"{task.user}, are you sure you have completed this task? {task.name}"
        if not indefinite:
            txt = txt + f" in {task.room}"

        # To avoid the message sitting too close to the buttons, place the label
        # inside a vertical BoxLayout with an expanding spacer above and below so
        # the text appears visually centered within the popup.
        spacer_top = BoxLayout(size_hint_y=0.2)
        spacer_bottom = BoxLayout(size_hint_y=0.2)
        lbl = Label(text=txt, size_hint_y=None, height=dp(40), halign='center', valign='middle')
        lbl.bind(size=lambda inst, sz: setattr(inst, 'text_size', (inst.width, inst.height)))
        content.add_widget(spacer_top)
        content.add_widget(lbl)
        content.add_widget(spacer_bottom)

        # Buttons row
        btns = BoxLayout(size_hint_y=None, height=dp(48))
        confirm_button = Button(text="Confirm", on_press=lambda _: (self._complete_indefinite_task(task.name, instance) if indefinite else self._complete_task(task), self.popup.dismiss()))
        cancel_button = Button(text="Cancel", on_press=lambda _: self.popup.dismiss())
        btns.add_widget(confirm_button)
        btns.add_widget(cancel_button)
        content.add_widget(btns)

        # Secondary action (open different-user dialog)
        def complete_task_persist_user(_):
            self.popup.dismiss()
            Clock.schedule_once(lambda dt: self._different_user_dialog(task, indefinite, instance), 0.05)

        persist_user_button = Button(text="Complete task as a different user", size_hint_y=None, height=dp(44), on_press=complete_task_persist_user)
        content.add_widget(persist_user_button)

        # Popup size similar to other dialog; give a bit more vertical room so centering looks good
        self.popup = Popup(title="Confirm Task Completion", content=content, size_hint=(0.9, 0.55), auto_dismiss=False)
        self.popup.open()

    def _complete_task(self, task, advance_user=True):
        # Normal completion does not touch surplus/deficit points when assigned group
        # members complete the task. Just advance assignment and refresh display.
        self.assigned_tasks.remove(task)
        self._assign_task(task.room, task.name, task.user, False, advance_user)
        self._display_tasks()

    def _surplus_and_deficit(self, up, down):
        self.users.up_and_down(up, down)
        self._display_users()

    def _complete_indefinite_task(self, task_name, instance):
        i, task = self.indefinite_tasks.increment(task_name)

        # If user has finished the required number of repetitions, reset reps back to 1
        # And go to the next user
        if task.rep > task.total_reps:
            users = self.data['indefinite_tasks'][task.name]['users']
            new_user = users[(users.index(task.user) + 1) % len(users)]
            self.indefinite_tasks.reset(i, new_user)
        if instance is not None:
            instance.text = f"{task.name}\n{task.user}\n{task.rep}/{task.total_reps}"


class CleanyApp(App):
    """
    The Cleany kivy application object. Call CleanyApp().run() to run it.
    """
    def build(self):
        return _TaskManager()
