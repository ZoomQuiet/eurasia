import sys
from eio  import *
from pyev import *
from os   import strerror
from weakref    import ref
from exceptions import Timeout
from errno      import ETIMEDOUT
from traceback  import print_exc
from greenlet   import getcurrent

interface = '''\
fsync     (fd)
close     (fd)
read      (fd, buf, length, offset)
write     (fd, buf, length, offset)
ftruncate (fd, offset)
open      (path, flags, mode)
truncate  (path, offset)
mkdir     (path, mode)
rmdir     (path)
unlink    (path)
rename    (path, new_path)'''

code = '''def %(func)s_without_timeout(%(args)s):
    co  = getcurrent()
    id_ = c_uint(id(co)).value
    objects[id_] = ref(co)
    req = eio_%(func)s(%(args)s, 0, c_callback, id_)
    try:
        co.parent.switch()
    finally:
        del objects[id_]
    return req.contents.result

def %(func)s(%(args)s, timeout):
    co  = getcurrent()
    id_ = c_uint(id(co)).value
    tm  = ev_timer()
    memmove(byref(tm), timer0, sizeof_timer)
    tm.at = timeout
    objects[id_] = ref(co)
    ev_timer_start(EV_DEFAULT_UC, byref(tm))
    req = eio_%(func)s(%(args)s, 0, c_callback, id_)
    contents = req.contents
    try:
        try:
            co.parent.switch()
        except Timeout:
            if contents.cancelled:
                return contents.result
            eio_cancel(req)
            raise
    finally:
        ev_timer_stop(EV_DEFAULT_UC, byref(tm))
        del objects[id_]
    return contents.result'''

for line in interface.split('\n'):
    args = line[line.find('(')+1:line.rfind(')')].strip()
    func = line[:line.find('(')].strip()
    if not func:
        continue
    exec(code % {'func': func, 'args': args})
del interface, code, line, args, func

_pread = read
del read
def pread(fd, length, offset, timeout):
    buf = create_string_buffer(length)
    n = _pread(fd, buf, length, offset, timeout)
    return buf.raw[:n]

_pread_without_timeout = read_without_timeout
del read_without_timeout
def pread_without_timeout(fd, length, offset):
    buf = create_string_buffer(length)
    n = _pread_without_timeout(
        fd, buf, length, offset)
    return buf.raw[:n]

_pwrite = write
del write
def pwrite(fd, data, offset, timeout):
    return _pwrite(fd, data, len(data), offset, timeout)

_pwrite_without_timeout = write_without_timeout
del write_without_timeout
def pwrite_without_timeout(fd, data, offset):
    return _pwrite_without_timeout(
        fd, data, len(data), offset)

def callback(req):
    contents = req.contents
    id_   = contents.data
    errno = contents.errorno
    co    = objects[id_]()
    if 0 == errno:
        try:
            co.switch()
        except:
            print_exc(file=sys.stderr)
    else:
        try:
            co.throw(IOError,
                     IOError(errno, strerror(errno)))
        except:
            print_exc(file=sys.stderr)
    return 0

def tm_cb(l, w, e):
    id_ = w.contents.data
    co  = objects[id_]()
    try:
        co.throw(Timeout,
                 Timeout(ETIMEDOUT, 'operation timed out'))
    except:
        print_exc(file=sys.stderr)

def get_timer0():
    buf = create_string_buffer(sizeof_timer)
    tm  = ev_timer()
    memset(byref(tm), 0, sizeof_timer)
    tm.cb = c_tm_cb
    memmove(buf, byref(tm), sizeof_timer)
    return buf

for field, cb in ev_timer._fields_:
    if 'cb' == field:
        c_tm_cb = cb(tm_cb)
del field, cb
c_callback   = eio_cb(callback)
sizeof_timer = sizeof(ev_timer)
timer0 = get_timer0(); del get_timer0

objects = {}

# eio.pod#INITIALISATION_INTEGRATION

def repeat(l, w, e):
    if -1 != eio_poll() and repeat_watcher.active:
        ev_idle_stop(EV_DEFAULT_UC, byref(repeat_watcher))

repeat_watcher = ev_idle()
memset(byref(repeat_watcher), 0, sizeof(ev_idle))
for field, cb in ev_idle._fields_:
    if 'cb' == field:
        c_repeat = cb(repeat)

def ready(l, w, e):
    if -1 == eio_poll() and not repeat_watcher.active:
        ev_idle_start(EV_DEFAULT_UC, byref(repeat_watcher))

ready_watcher = ev_async()
memset(byref(ready_watcher), 0, sizeof(ev_async))
for field, cb in ev_async._fields_:
    if 'cb' == field:
        c_ready = cb(ready)
del field, cb
ready_watcher.cb = c_ready
ev_async_start(EV_DEFAULT_UC, byref(ready_watcher))

def want_poll():
    ev_async_send(EV_DEFAULT_UC, byref(ready_watcher))

c_want_poll = eio_init.argtypes[0](want_poll)
c_done_poll = cast(NULL, eio_init.argtypes[1])
eio_init(c_want_poll, c_done_poll)
