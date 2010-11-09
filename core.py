from signal import SIGINT
from _weakref import proxy
from ctypes import get_errno
from cStringIO import StringIO
from fcntl import fcntl, F_SETFL
from pyev import EV_READ, EV_WRITE
from greenlet import greenlet, getcurrent
from pyev import default_loop, Io, Timer, Signal
from os import read, write, close, strerror, O_NONBLOCK
from errno import EBADF, ECONNRESET, ENOTCONN, EPIPE, \
    ESHUTDOWN, ETIMEDOUT, EWOULDBLOCK

def sleep(seconds):
    '''sleep(seconds)

    Delay execution for a given number of seconds.  The argument may be
    a floating point number for subsecond precision.'''
    timer = Timer(seconds, 0., loop, s_timer_cb, getcurrent())
    timer.start()
    try:
        schedule()
    finally:
        timer.stop()

class file(object):
    def __init__(self, f):
        '''file(fileno) -> coroutine file object'''
        if fcntl(f, F_SETFL, O_NONBLOCK) != 0:
            errno = get_errno()
            raise OSError(errno, strerror(errno))

        self.f = f
        relf = proxy(self)
        self.buf = StringIO()
        self.r_timer = Timer(0. , 0. , loop, r_timer_cb, relf)
        self.w_timer = Timer(0. , 0. , loop, w_timer_cb, relf)
        self.r_event = Io(f, EV_READ , loop, r_event_cb, relf)
        self.w_event = Io(f, EV_WRITE, loop, w_event_cb, relf)

    def _close(self):
        # Close the file. May be overridden.
        return close(self.f)

    def _recv(self, size):
        # Read from file. May be overridden.
        return read(self.f, size)

    def _send(self, data):
        # Write data to file. May be overridden.
        return write(self.f, data)

    def ready(self, timeout=-1):
        '''ready(timeout=-1) -> bool

        To test if this file is ready for access.
        '''
        assert not hasattr(self, 'x_gcurr')
        if timeout > 0:
            timer = Timer(timeout, 0., loop, x_timer_cb, self)
            event = Io(self.f, EV_READ|EV_WRITE, loop, x_event_cb, self)
            timer.start()
            event.start()
            self.x_gcurr = getcurrent()
            try:
                schedule()
            finally:
                del self.x_gcurr
                event.stop()
                timer.stop()
        else:
            event = Io(self.f, EV_READ|EV_WRITE, loop, x_event_cb, self)
            event.start()
            self.x_gcurr = getcurrent()
            try:
                schedule()
            finally:
                del self.x_gcurr
                event.stop()

    def recv(self, size=8192, timeout=-1):
        '''recv(size=8192, timeout=-1) -> data

        Read up to buffersize bytes from the file.
        When no data is available, block until at least one byte is available.
        When the file is closed and all data is read, return the empty string.
        '''
        if self.f == -1:
            return ''
        self.r_wait(timeout)
        if self.f == -1:
            return ''
        try:
            return self._recv(size)
        except BaseException, e:
            if e[0] in edisconn:
                self._close()
                self.f = -1
                return ''
            raise

    def send(self, data, timeout=-1):
        '''send(data, timeout=-1) -> count

        Write a data string to the file.  Return the number of bytes
        wrote; this may be less than len(data) if the IO is busy.
        '''
        if self.f == -1:
            if self.closed:
                raise OSError(EBADF, 'Bad file descriptor')
            raise OSError(EPIPE, 'Broken pipe')
        self.w_wait(timeout)
        if self.f == -1:
            raise OSError(EPIPE, 'Broken pipe')
        try:
            return self._send(data)
        except BaseException, e:
            if e[0] in edisconn:
                self._close()
                self.f = -1
                raise OSError(EPIPE, 'Broken pipe')
            raise

    def read(self, size=-1, timeout=-1):
        '''read(size=-1, timeout=-1) -> read at most size bytes, returned as a string.

        If the size argument is negative or omitted, read until EOF is reached.
        Notice that when in non-blocking mode, less data than what was requested
        may be returned, even if no size parameter was given.
        '''
        return self._r_call(self._read, timeout, size)

    def readline(self, size=-1, timeout=-1):
        '''readline(size=-1, timeout=-1) -> next line from the file, as a string.

        Retain newline.  A non-negative size argument limits the maximum
        number of bytes to return (an incomplete line may be returned then).
        Return an empty string at EOF.
        '''
        return self._r_call(self._readline, timeout, size)

    def sendall(self, data, timeout=-1):
        '''sendall(data, timeout=-1)

        Send a data string to the socket.
        If a timeout occurs, timeout.num_sent has been sent.
        '''
        return self._w_call(self._sendall, timeout, data)

    def close(self):
        '''close() -> None or (perhaps) an integer.  Close the file.

        Sets data attribute .closed to True.  A closed file cannot be used for
        further I/O operations.  close() may be called more than once without
        error.  Some kinds of file objects (for example, opened by popen())
        may return an exit status upon closing.
        '''
        if not self.closed:
            self._close()
            self.closed = 1
            self.f = -1
    closed = 0

    def _read(self, size=-1):
        buf = self.buf
        buf.seek(0, 2)  # seek end
        # Read until EOF
        if size < 0:
            self.buf = StringIO()  # reset buf.  we consume it via buf.
            if self.f == -1:
                return buf.getvalue()
            while 1:
                try:
                    self.r_wait()
                except timeout:
                    self.buf = buf  # restore buf before raise.
                    raise
                if self.f == -1:
                    return buf.getvalue()
                try:
                    data = self._recv(8192)
                except BaseException, e:
                    if e[0] in edisconn:
                        self._close()
                        self.f = -1
                        return buf.getvalue()
                    raise
                if not data:
                    break
                buf.write(data)
            return buf.getvalue()
        # Read until size bytes or EOF seen, whichever comes first
        bufsize = buf.tell()
        if bufsize >= size:
            # Already have size bytes in our buffer?  Extract and return.
            buf.seek(0)
            rv = buf.read(size)
            self.buf = StringIO()
            self.buf.write(buf.read())
            return rv

        self.buf = StringIO()  # reset buf.  we consume it via buf.
        if self.f == -1:
            return buf.getvalue()
        while 1:
            left = size - bufsize
            try:
                self.r_wait()
            except timeout:
                self.buf = buf  # restore buf before raise.
                raise
            if self.f == -1:
                return buf.getvalue()
            # _recv() will malloc the amount of memory given as its
            # parameter even though it often returns much less data
            # than that.  The returned data string is short lived
            # as we copy it into a StringIO and free it.  This avoids
            # fragmentation issues on many platforms.
            try:
                data = self._recv(left)
            except BaseException, e:
                if e[0] in edisconn:
                    self._close()
                    self.f = -1
                    return buf.getvalue()
                raise
            if not data:
                break
            n = len(data)
            if n == size and not bufsize:
                # Shortcut.  Avoid buffer data copies when:
                # - We have no data in our buffer.
                # AND
                # - Our call to recv returned exactly the
                #   number of bytes we were asked to read.
                return data
            if n == left:
                buf.write(data)
                del data  # explicit free
                break
            buf.write(data)
            bufsize += n
            del data
        return buf.getvalue()

    def _readline(self, size=-1):
        buf = self.buf
        buf.seek(0, 2)  # seek end
        if buf.tell() > 0:
            # check if we already have it in our buffer
            buf.seek(0)
            bline = buf.readline(size)
            if bline.endswith('\n') or len(bline) == size:
                self.buf = StringIO()
                self.buf.write(buf.read())
                return bline
            del bline
        if size < 0:
            buf.seek(0, 2)  # seek end
            self.buf = StringIO()  # reset buf.  we consume it via buf.
            if self.f == -1:
                return buf.getvalue()
            while 1:
                try:
                    self.r_wait()
                except timeout:
                    self.buf = buf  # restore buf before raise.
                    raise
                if self.f == -1:
                    return buf.getvalue()
                try:
                    data = self._recv(8192)
                except BaseException, e:
                    if e[0] in edisconn:
                        self._close()
                        self.f == -1
                        return buf.getvalue()
                    raise
                if not data:
                    break
                nl = data.find('\n')
                if nl >= 0:
                    nl += 1
                    buf.write(data[:nl])
                    self.buf.write(data[nl:])
                    del data
                    break
                buf.write(data)
            return buf.getvalue()
        # Read until size bytes or \n or EOF seen, whichever comes first
        buf.seek(0, 2)  # seek end
        bufsize = buf.tell()
        if bufsize >= size:
            buf.seek(0)
            rv = buf.read(size)
            self.buf = StringIO()
            self.buf.write(buf.read())
            return rv
        self.buf = StringIO()  # reset buf.  we consume it via buf.
        if self.f == -1:
            return buf.getvalue()
        while 1:
            try:
                self.r_wait()
            except timeout:
                self.buf = buf  # restore buf before raise.
                raise
            if self.f == -1:
                return buf.getvalue()
            try:
                data = self._recv(8192)
            except BaseException, e:
                if e[0] in edisconn:
                    self._close()
                    self.f == -1
                    return buf.getvalue()
                raise
            if not data:
                break
            left = size - bufsize
            # did we just receive a newline?
            nl = data.find('\n', 0, left)
            if nl >= 0:
                nl += 1
                # save the excess data to buf
                self.buf.write(data[nl:])
                if bufsize:
                    buf.write(data[:nl])
                    break
                else:
                    # Shortcut.  Avoid data copy through buf when returning
                    # a substring of our first _recv().
                    return data[:nl]
            n = len(data)
            if n == size and not bufsize:
                return data
            if n >= left:
                buf.write(data[:left])
                self.buf.write(data[left:])
                break
            buf.write(data)
            bufsize += n
        return buf.getvalue()

    def _sendall(self, data):
        if self.f == -1:
            if self.closed:
                raise OSError(EBADF, 'Bad file descriptor')
            raise OSError(EPIPE, 'Broken pipe')
        pos  = 0
        left = len(data)
        while pos < left:
            try:
                self.w_wait()
            except timeout, e:
                e.num_sent = pos
                raise e
            if self.f == -1:
                raise OSError(EPIPE, 'Broken pipe')
            try:
                pos += self._send(data[pos:pos+8192])
            except BaseException, e:
                if e[0] != EWOULDBLOCK:
                    self._close()
                    self.f = -1
                    raise

    code = '''\
    def ${ev}_call(self, func, timeout=-1):
        if timeout > 0:
            assert not self.${ev}_timer.active
            timer = self.${ev}_timer
            timer.set(timeout, 0.)
            def wrapper(*args, **kwargs):
                timer.start()
                try:
                    return func(*args, **kwargs)
                finally:
                    timer.stop()
            return wrapper
        return func

    def _${ev}_call(self, func, timeout=-1, *args):
        if timeout > 0:
            assert not self.${ev}_timer.active
            timer = self.${ev}_timer
            timer.set(timeout, 0.)
            timer.start()
            try:
                return func(*args)
            finally:
                timer.stop()
        else:
            return func(*args)

    def ${ev}_wait(self, timeout=-1):
        if timeout > 0:
            assert not self.${ev}_timer.active
            self.${ev}_timer.set(timeout, 0.)
            self.${ev}_timer.start()
            self.${ev}_event.start()
            self.${ev}_gcurr = getcurrent()
            try:
                self.${ev}_gcurr.parent.switch()
            finally:
                del self.${ev}_gcurr
                self.${ev}_event.stop()
                self.${ev}_timer.stop()
        else:
            assert not self.${ev}_event.active
            self.${ev}_event.start()
            self.${ev}_gcurr = getcurrent()
            try:
                self.${ev}_gcurr.parent.switch()
            finally:
                del self.${ev}_gcurr
                self.${ev}_event.stop()'''

    code = '\n'.join([s[4:] for s in code.split('\n')])
    for ev in 'rw':
        exec(code.replace('${ev}', ev))
    del code, ev, s

code = '''\
def ${ev}_timer_cb(w, evts):
    try:
        w.data.${ev}_gcurr.throw(timeout, timeout(ETIMEDOUT, 'timed out'))
    except:
        excepthook()

def ${ev}_event_cb(w, evts):
    try:
        w.data.${ev}_gcurr.switch()
    except:
        excepthook()

def ${ev}_timer_cb_without_excepthook(w, evts):
    w.data.${ev}_gcurr.throw(timeout, timeout(ETIMEDOUT, 'timed out'))

def ${ev}_event_cb_without_excepthook(w, evts):
    w.data.${ev}_gcurr.switch()'''

for ev in 'xrw': # r:read w:write x:rw callback
    exec(code.replace('${ev}', ev))
del code, ev

def s_timer_cb(w, evts): # sleep timer callback
    try:
        w.data.switch()
    except:
        excepthook()

def s_timer_cb_without_excepthook(w, evts):
        w.data.switch()

class timeout(OSError):
    num_sent = 0  # bytes were already sent

def without_excepthook():
    global x_event_cb, r_event_cb, w_event_cb
    x_event_cb, r_event_cb, w_event_cb = \
        x_event_cb_without_excepthook, \
        r_event_cb_without_excepthook, \
        w_event_cb_without_excepthook
    global x_timer_cb, r_timer_cb, w_timer_cb, s_timer_cb
    x_timer_cb, r_timer_cb, w_timer_cb, s_timer_cb = \
        x_timer_cb_without_excepthook, \
        r_timer_cb_without_excepthook, \
        w_timer_cb_without_excepthook, \
        s_timer_cb_without_excepthook

def excepthook():
    # need to override
    pass

__all__  = 'exit file loop schedule timeout mainloop'.split()
edisconn = {ECONNRESET: None, ENOTCONN: None, ESHUTDOWN: None}
schedule = getcurrent().switch
loop     = default_loop()
exit     = loop.unloop
mainloop = loop.loop

def sigcb(w, evts):  # ctrl + c
    w.loop.unloop()
keyboard_interrupt = Signal(SIGINT, loop, sigcb)
keyboard_interrupt.start()
