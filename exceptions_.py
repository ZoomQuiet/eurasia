class Cancelled(Exception):
    pass

cancelled = Cancelled

class Unknow(Exception):
    pass

unknow = Unknow

class Full(Exception):
    pass

full = Full

class Empty(Exception):
    pass

empty = Empty

import _socket

class Timeout(_socket.timeout):
    num_sent = 0

timeout = Timeout

from greenlet import getcurrent

class Running(Timeout):
    def wait(self):
        co =  getcurrent()
        self.data[0]  = co
        co.parent.switch()
    data = None

running = Running
