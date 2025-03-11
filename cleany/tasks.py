"""
Task related data structures.
"""

import json
from datetime import datetime


class _Task:

    # pylint: disable=too-few-public-methods
    def __init__(self, dict1=None):
        self.user = ""
        self.room = ""
        self.name = ""
        self.due_date = datetime.utcfromtimestamp(0).date()
        self.period = ""
        if dict1:
            self.__dict__.update(dict1)
            self.due_date = datetime.strptime(self.due_date,'%Y-%m-%d').date()

    def __lt__(self, other):
        return self.due_date < other.due_date


def new_task(user, room, name, due_date, period):
    """
    Create a new task

    :param str user: The current assigned user
    :param str room: The room this task is associated with.
    :param str name: The name of the task
    :param datetime.date due_date: When the task is due
    :param str period: The period of the task
    """
    task = _Task()
    task.user = user
    task.room = room
    task.name = name
    task.due_date = due_date
    task.period = period
    return task


# A solution for always persisting the state of the list in storage,
# not having to worry about application lifecycle, etc.
# Works fine for this app because its low volume, infrequent read/writes.
# Horrible idea for big data with frequent read/writes.
class Tasks(list):
    """
    A means of collecting the tasks as a list, automatically managing their
    persistence in storage. (That is, you treat it and a list, and the read/write to storage
    gets taken care of automatically in the back end)
    """
    def __init__(self, filename):
        self.filename = filename
        super().__init__(self._load())

    def _load(self):
        try:
            with open(self.filename, "r", encoding="utf-8") as f:
                return json.load(f, object_hook=_Task)
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def _save(self):
        with open(self.filename, "w", encoding="utf-8") as f:
            json.dump(self, f, default=lambda o: o.__dict__ if isinstance(o, _Task) else str(o))

    def __setitem__(self, index, value):
        super().__setitem__(index, value)
        self._save()

    def append(self, value):
        super().append(value)
        self._save()

    def extend(self, iterable):
        super().extend(iterable)
        self._save()

    def insert(self, index, value):
        super().insert(index, value)
        self._save()

    def remove(self, value):
        super().remove(value)
        self._save()

    def pop(self, index=-1):
        value = super().pop(index)
        self._save()
        return value

    def clear(self):
        super().clear()
        self._save()


class _IndefiniteTask():

    # pylint: disable=too-few-public-methods
    def __init__(self, dict1=None):
        self.user = ""
        self.name = ""
        self.rep = -1
        self.total_reps = -1
        if dict1:
            self.__dict__.update(dict1)

    def __lt__(self, other):
        return self.name < other.name


def new_indefinite_task(user, name, total_reps):
    """
    Create a new indefinite task
    """
    it = _IndefiniteTask()
    it.user = user
    it.name = name
    it.rep = 1
    it.total_reps = total_reps
    return it


class IndefiniteTasks(list):
    """
    A means of collecting the indefinite tasks as a list, automatically managing
    their persistence to storage. (That is, you treat it and a list, and the read/write to storage
    gets taken care of automatically in the back end)
    """
    def __init__(self, filename):
        self.filename = filename
        super().__init__(self._load())

    def _load(self):
        try:
            with open(self.filename, "r", encoding="utf-8") as f:
                return json.load(f, object_hook=_IndefiniteTask)
        except (FileNotFoundError, json.JSONDecodeError):
            return []

    def _save(self):
        with open(self.filename, "w", encoding="utf-8") as f:
            json.dump(self, f, default=lambda o: o.__dict__)

    def __setitem__(self, index, value):
        super().__setitem__(index, value)
        self._save()

    def append(self, value):
        super().append(value)
        self._save()

    def extend(self, iterable):
        super().extend(iterable)
        self._save()

    def insert(self, index, value):
        super().insert(index, value)
        self._save()

    def remove(self, value):
        super().remove(value)
        self._save()

    def pop(self, index=-1):
        value = super().pop(index)
        self._save()
        return value

    def clear(self):
        super().clear()
        self._save()

    def increment(self, name):
        """
        Increment the indefinite task's repetition
        """
        # pylint: disable=consider-using-enumerate
        for i in range(len(self)):
            if self[i].name == name:
                break
        self[i].rep += 1
        self._save()
        return i, self[i]

    def reset(self, index, new_user):
        """
        Reset the indefinite task's repetitions and assign a new user

        :param int index: The index of the task
        ·param str new_user: The task's new assigned user
        """
        self[index].rep = 1
        self[index].user = new_user
        self._save()
