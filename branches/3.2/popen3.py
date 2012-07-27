from errno  import EBADF
from ctypes import get_errno
from fcntl  import fcntl, F_SETFL
from subprocess import Popen, PIPE
from socket_ import error, SocketWrapper
from os import read, write, strerror, O_NONBLOCK

class fakesocket:
    def __init__(self, file):
        fd = file.fileno()
        if fcntl(fd, F_SETFL, O_NONBLOCK) != 0:
            errorno = get_errno()
            raise OSError(errorno, strerror(errorno))
        self.fd = fd
        self.file = file

    def recv(self, size):
        if -1 == self.fd:
            raise error(EBADF, 'Bad file descriptor')
        return read (self.fd, size)

    def send(self, data):
        if -1 == self.fd:
            raise error(EBADF, 'Bad file descriptor')
        return write(self.fd, data)

    def fileno(self):
        if -1 == self.fd:
            raise error(EBADF, 'Bad file descriptor')
        return self.fd

    def close(self):
        self.file.close()
        self.fd = -1

def popen3(*args):
    _ = Popen(args, stdin=PIPE, stdout=PIPE, stderr=PIPE)
    stdin  = SocketWrapper(fakesocket(_.stdin ))
    stdout = SocketWrapper(fakesocket(_.stdout))
    stderr = SocketWrapper(fakesocket(_.stderr))
    return stdin, stdout, stderr
