class Cancelled(Exception):
    pass

class Unknow(Exception):
    pass

class Full(Exception):
    pass

class Empty(Exception):
    pass

import _socket

class Timeout(_socket.timeout):
    num_sent = 0

from greenlet import getcurrent

class Wait(Timeout):
    def __call__(self):
        data = self.get_frame()
        data.back_ = back_ = getcurrent()
        back_.parent.switch()

    get_frame = None
