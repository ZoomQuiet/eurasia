import ctypes.util
from cdefs import *
where = ctypes.util.find_library('ev')
if where is None:
    import os, posixpath
    base = posixpath.abspath(posixpath.dirname(__file__))
    for fn in os.listdir(base):
        if 'libev.so' == fn[:8]:
            where = posixpath.join(base, fn)
            break
assert where, 'ev.py needs libev installed.'
libev = CDLL(where)

EV_ATOMIC_T = c_sig_atomic_t

ev_tstamp = c_double
ev_loop_p = c_void_p # POINTER(ev_loop)

EV_UNDEF    =   -1
EV_NONE     = 0x00
EV_READ     = 0x01
EV_WRITE    = 0x02
EV__IOFDSET = 0x80

def EV_CB_DECLARE(type_):
    return CFUNCTYPE(None, c_void_p, POINTER(type_), c_int)

def EV_WATCHER(type_):
    return [('active'  , c_int), ('pending', c_int),
            ('priority', c_int), ('data', c_void_p),
            ('cb', EV_CB_DECLARE(type_))]

def EV_WATCHER_LIST(type_):
    return EV_WATCHER(type_) + [('next', ev_watcher_list_p)]

def EV_WATCHER_TIME(type_):
    return EV_WATCHER(type_) + [('at', ev_tstamp)]

class ev_watcher_list(Structure):
    pass

ev_watcher_list_p = POINTER(ev_watcher_list)
ev_watcher_list._fields_ = EV_WATCHER_LIST(ev_watcher_list)

class ev_io(Structure):
    pass

ev_io_p = POINTER(ev_io)
ev_io._fields_ = EV_WATCHER_LIST(ev_io) + \
    [('fd', c_int), ('events', c_int)]

class ev_timer(Structure):
    pass

ev_timer_p = POINTER(ev_timer)
ev_timer._fields_ = EV_WATCHER_TIME(ev_timer) + \
    [('repeat', ev_tstamp)]

class ev_signal(Structure):
    pass

ev_signal_p = POINTER(ev_signal)
ev_signal._fields_ = EV_WATCHER_LIST(ev_signal) + \
    [('signum', c_int)]

class ev_idle(Structure):
    pass

ev_idle_p = POINTER(ev_idle)
ev_idle._fields_ = EV_WATCHER(ev_idle)

class ev_async(Structure):
    pass

ev_async_p = POINTER(ev_async)
ev_async._fields_ = EV_WATCHER(ev_async) + \
    [('sent', EV_ATOMIC_T)]

def interface(name, restype, *argtypes):
    func = getattr(libev, name)
    func.restype, func.argtypes = restype, argtypes
    globals()[name] = func

if hasattr(libev, 'ev_run'):
    interface('ev_default_loop', ev_loop_p, c_uint)
    ev_default_loop_init = ev_default_loop
    interface('ev_run', None, ev_loop_p, c_int)
    ev_loop = ev_run
    interface('ev_break', None, ev_loop_p, c_int)
    ev_unloop = ev_break
else:
    interface('ev_default_loop_init', ev_loop_p, c_uint)
    ev_default_loop = ev_default_loop_init
    interface('ev_loop', None, ev_loop_p, c_int)
    ev_run = ev_loop
    interface('ev_unloop', None, ev_loop_p, c_int)
    ev_break = ev_unloop

EVRUN_NOWAIT   = EVLOOP_NONBLOCK = 1
EVRUN_ONCE     = EVLOOP_ONESHOT  = 2
EVBREAK_CANCEL = EVUNLOOP_CANCEL = 0
EVBREAK_ONE    = EVUNLOOP_ONE    = 1
EVBREAK_ALL    = EVUNLOOP_ALL    = 2

interface('ev_io_start', None, ev_loop_p, ev_io_p)
interface('ev_io_stop' , None, ev_loop_p, ev_io_p)
interface('ev_timer_start', None, ev_loop_p, ev_timer_p)
interface('ev_timer_stop' , None, ev_loop_p, ev_timer_p)
interface('ev_signal_start', None, ev_loop_p, ev_signal_p)
interface('ev_signal_stop' , None, ev_loop_p, ev_signal_p)

if hasattr(libev, 'ev_idle_start'):
    interface('ev_idle_start', None, ev_loop_p, ev_idle_p)
    interface('ev_idle_stop' , None, ev_loop_p, ev_idle_p)

if hasattr(libev, 'ev_async_start'):
    interface('ev_async_start', None, ev_loop_p, ev_async_p)
    interface('ev_async_stop' , None, ev_loop_p, ev_async_p)
    interface('ev_async_send' , None, ev_loop_p, ev_async_p)
