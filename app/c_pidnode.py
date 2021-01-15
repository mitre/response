from app.utility.base_object import BaseObject


class PidNode(BaseObject):

    def __init__(self, pid, parent_pid=None, child_pids=None):
        self.parent_pid = parent_pid
        self.pid = pid
        self.child_pids = child_pids