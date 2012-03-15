import _socket

class Timeout(_socket.timeout):
    num_sent = 0

timeout = Timeout
