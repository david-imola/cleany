import kivy
kivy.require('2.1.0') # replace with your current kivy version !

import requests
import yaml
from datetime import datetime, timedelta
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.button import Button
from kivy.uix.label import Label
from kivy.clock import Clock

queued_days_threshold_1 = 2
queued_days_threshold_2 = 4

tasks_to_display = 8


def _parse_period(period):
    unit = period[-1]
    value = int(period[:-1])
    if unit == 'd':
        return timedelta(days=value)
    elif unit == 'w':
        return timedelta(weeks=value)
    elif unit == 'm':
        return timedelta(days=value * 30)
    return timedelta(days=1)

class TaskManager(BoxLayout):
    def __init__(self, **kwargs):
        super().__init__(orientation='horizontal', **kwargs)
        
        self.room_tasks_layout = BoxLayout(orientation='vertical')
        self.right_section = BoxLayout(orientation='vertical')
        self.datetime_label = Label(text=str(datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        self.weather_label = Label(text="Fetching weather...")
        self.indefinite_tasks_layout = BoxLayout(orientation='vertical')
        
        self.right_section.add_widget(self.datetime_label)
        self.right_section.add_widget(self.weather_label)
        self.right_section.add_widget(self.indefinite_tasks_layout)
        
        self.add_widget(self.room_tasks_layout)
        self.add_widget(self.right_section)
        
        self.load_yaml()
        self.assign_tasks()
        self.display_tasks()
        
        Clock.schedule_interval(self.update_datetime, 1)
        Clock.schedule_interval(self.update_weather, 600)  # Update weather every 10 minutes
        self.update_weather(0)  # Initial weather fetch
    
    def update_datetime(self, dt):
        self.datetime_label.text = str(datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    
    def update_weather(self, dt):
        try:
            response = requests.get("https://api.open-meteo.com/v1/forecast?latitude=44.49381&longitude=11.33875&current_weather=true")
            data = response.json()
            temp = data["current_weather"]["temperature"]
            condition = data["current_weather"]["weathercode"]
            self.weather_label.text = f"Temp: {temp}°C | Condition: {condition}"
        except Exception as e:
            self.weather_label.text = f"Weather update failed: {e}"
    
    def load_yaml(self):
        with open("tasks.yaml", "r") as file:
            self.data = yaml.safe_load(file)
    
    def assign_tasks(self):
        self.assigned_tasks = []
        self.indefinite_tasks = []
        now = datetime.now().date()
        
        for room, details in self.data['rooms'].items():
            users = details['users']
            for task, info in details['tasks'].items():
                period = _parse_period(info['period'])
                start_date = datetime.strptime(info['start-date'], "%Y-%m-%d").date()
                cycle_pos = (now - start_date).days // period.days % len(users)
                assigned_user = users[cycle_pos]
                self.assigned_tasks.append({'user': assigned_user, 'room': room, 'task': task, 'queued_days': 0})
        
        indefinite_users = {}
        for task, details in self.data['indefinite_tasks'].items():
            users = details['users']
            reps = details['repititions']
            if task not in indefinite_users:
                indefinite_users[task] = 0
            user_index = indefinite_users[task] % len(users)
            self.indefinite_tasks.append({'user': users[user_index], 'task': task, 'rep': 1, 'total_reps': reps})
    
    def display_tasks(self):
        self.room_tasks_layout.clear_widgets()
        self.indefinite_tasks_layout.clear_widgets()
        now = datetime.now().date()
        

        for i in range(tasks_to_display):
            task = self.assigned_tasks[i]

            queued_days = task['queued_days']
            color = queued_color(queued_days)
            btn = Button(text=f"{task['task']}\n{task['user']}\n{task['room']}\Queued Days: {queued_days}", background_color=color)
            btn.bind(on_press=lambda instance, t=task: self.complete_task(t, instance))
            self.room_tasks_layout.add_widget(btn)
        
        for task in self.indefinite_tasks:
            btn = Button(text=f"{task['task']}\n{task['user']}\n{task['rep']}/{task['total_reps']}")
            btn.bind(on_press=lambda instance, t=task: self.next_indefinite_task(t, instance))
            self.indefinite_tasks_layout.add_widget(btn)
    
    def complete_task(self, task, instance):
        self.assigned_tasks.remove(task)
        self.room_tasks_layout.remove_widget(instance)
    
    def next_indefinite_task(self, task, instance):
        task['rep'] += 1
        if task['rep'] > task['total_reps']:
            users = self.data['indefinite_tasks'][task['task']]['users']
            task['rep'] = 1
            task['user'] = users[(users.index(task['user']) + 1) % len(users)]
        instance.text = f"{task['task']}\n{task['user']}\n{task['rep']}/{task['total_reps']}"

class TaskApp(App):
    def build(self):
        return TaskManager()

