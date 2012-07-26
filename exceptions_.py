class Cancelled(Exception):
    pass

class Full(Exception):
    pass

class Empty(Exception):
    pass

import _socket

class Timeout(_socket.timeout):
    num_sent = 0

timeout = Timeout
