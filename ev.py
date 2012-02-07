import ctypes.util
from ctypes import *
where = ctypes.util.find_library('ev')
assert where, 'ev.py needs libev installed.'
libev = CDLL(where)

ev_tstamp = c_double
ev_loop_p = c_void_p

EV_UNDEF    =         -1
EV_NONE     =       0x00
EV_READ     =       0x01
EV_WRITE    =       0x02
EV__IOFDSET =       0x80
EV_IO       =    EV_READ
EV_TIMEOUT  = 0x00000100
EV_TIMER    = EV_TIMEOUT
EV_PERIODIC = 0x00000200
EV_SIGNAL   = 0x00000400
EV_CHILD    = 0x00000800
EV_STAT     = 0x00001000
EV_IDLE     = 0x00002000
EV_PREPARE  = 0x00004000
EV_CHECK    = 0x00008000
EV_EMBED    = 0x00010000
EV_FORK     = 0x00020000
EV_ASYNC    = 0x00040000
EV_CUSTOM   = 0x01000000
EV_ERROR    = 0x80000000

def EV_CB_DECLARE(type):
    return CFUNCTYPE(None, c_void_p, POINTER(type), c_int)

def EV_WATCHER(type):
    return [
        ('active'  , c_int), ('pending', c_int),
        ('priority', c_int), ('data', c_void_p),
        ('cb', EV_CB_DECLARE(type))]

def EV_WATCHER_LIST(type):
    return EV_WATCHER(type) + [('next', ev_watcher_list_p)]

def EV_WATCHER_TIME(type):
    return EV_WATCHER(type) + [('at', ev_tstamp)]

class ev_watcher(Structure):
    pass
ev_watcher_p = POINTER(ev_watcher)
ev_watcher._fields_ = EV_WATCHER(ev_watcher)

class ev_watcher_list(Structure):
    pass
ev_watcher_list_p = POINTER(ev_watcher_list)
ev_watcher_list._fields_ = EV_WATCHER_LIST(ev_watcher_list)

class ev_watcher_time(Structure):
    pass
ev_watcher_time_p = POINTER(ev_watcher_time)
ev_watcher_time._fields_ = EV_WATCHER_TIME(ev_watcher_time)

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

class ev_periodic(Structure):
    pass
ev_periodic_p = POINTER(ev_periodic)
ev_periodic._fields_ = EV_WATCHER_TIME(ev_periodic) + \
    [('offset', ev_tstamp), ('interval', ev_tstamp),
     ('reschedule_cb', CFUNCTYPE(
         ev_tstamp, ev_periodic, ev_tstamp))]

class ev_signal(Structure):
    pass
ev_signal_p = POINTER(ev_signal)
ev_signal._fields_ = EV_WATCHER_LIST(ev_signal) + \
    [('signum', c_int)]

class ev_child(Structure):
    pass
ev_child_p = POINTER(ev_child)
ev_child._fields_ = EV_WATCHER_LIST(ev_child) + \
    [('flags', c_int), ('pid'    , c_int),
     ('rpid' , c_int), ('rstatus', c_int)]

# XXX ev_stat

class ev_idle(Structure):
    pass
ev_idle_p = POINTER(ev_idle)
ev_idle._fields_ = EV_WATCHER(ev_idle)

class ev_prepare(Structure):
    pass
ev_prepare_p = POINTER(ev_prepare)
ev_prepare._fields_ = EV_WATCHER(ev_prepare)

class ev_check(Structure):
    pass
ev_check_p = POINTER(ev_check)
ev_check._fields_ = EV_WATCHER(ev_check)

class ev_fork(Structure):
    pass
ev_fork_p = POINTER(ev_fork)
ev_fork._fields_ = EV_WATCHER(ev_fork)

class ev_embed(Structure):
    pass
ev_embed_p = POINTER(ev_embed)
ev_embed._fields_ = EV_WATCHER(ev_embed) + \
    [('other'  , ev_loop_p ), ('io'      , ev_io      ),
     ('prepare', ev_prepare), ('check'   , ev_check   ),
     ('timer'  , ev_timer  ), ('periodic', ev_periodic),
     ('idle'   , ev_idle   ), ('fork'    , ev_fork    )]

# XXX ev_async ev_any_watcher

EVFLAG_AUTO       = 0x00000000
EVFLAG_NOENV      = 0x01000000
EVFLAG_FORKCHECK  = 0x02000000
EVFLAG_NOINOTIFY  = 0x00100000
EVFLAG_NOSIGFD    = 0x00200000
EVBACKEND_SELECT  = 0x00000001
EVBACKEND_POLL    = 0x00000002
EVBACKEND_EPOLL   = 0x00000004
EVBACKEND_KQUEUE  = 0x00000008
EVBACKEND_DEVPOLL = 0x00000010
EVBACKEND_PORT    = 0x00000020

ev_version_major = libev.ev_version_major
ev_version_major.restype = c_int
ev_version_major.argtypes = None
ev_version_minor = libev.ev_version_minor
ev_version_minor.restype = c_int
ev_version_minor.argtypes = None

ev_supported_backends = libev.ev_supported_backends
ev_supported_backends.restype = c_int
ev_supported_backends.argtypes = None
ev_recommended_backends = libev.ev_recommended_backends
ev_recommended_backends.restype = c_int
ev_recommended_backends.argtypes = None
ev_embeddable_backends = libev.ev_embeddable_backends
ev_embeddable_backends.restype = c_int
ev_embeddable_backends.argtypes = None

ev_time = libev.ev_time
ev_time.restype = ev_tstamp
ev_time.argtypes = None
ev_sleep = libev.ev_sleep
ev_sleep.restype = None
ev_sleep.argtypes = [ev_tstamp]

ev_set_allocator = libev.ev_set_allocator
ev_set_allocator.restype = None
ev_set_allocator.argtypes = \
    [CFUNCTYPE(c_void_p, c_void_p, c_long)]

ev_set_syserr_cb = libev.ev_set_syserr_cb
ev_set_syserr_cb.restype = None
ev_set_syserr_cb.argtypes = [CFUNCTYPE(None, c_char_p)]

ev_default_loop_init = libev.ev_default_loop_init
ev_default_loop_init.restype = ev_loop_p
ev_default_loop_init.argtypes = [c_uint]

if hasattr(libev, 'ev_loop_new'):
    ev_loop_new = libev.ev_loop_new
    ev_loop_new.restype = ev_loop_p
    ev_loop_new.argtypes = [c_uint]
    ev_loop_destroy = libev.ev_loop_destroy
    ev_loop_destroy.restype = None
    ev_loop_destroy.argtypes = [ev_loop_p]
    ev_loop_fork = libev.ev_loop_fork
    ev_loop_fork.restype = None
    ev_loop_fork.argtypes = [ev_loop_p]

    ev_now = libev.ev_now
    ev_now.restype = ev_tstamp
    ev_now.argtypes = [ev_loop_p]
else:
    ev_default_loop = libev.ev_default_loop
    ev_default_loop.restype = c_int
    ev_default_loop.argtypes = [c_uint]

ev_default_destroy = libev.ev_default_destroy
ev_default_destroy.restype = None
ev_default_destroy.argtypes = None
ev_default_fork = libev.ev_default_fork
ev_default_fork.restype = None
ev_default_fork.argtypes = None

ev_backend = libev.ev_backend
ev_backend.restype = c_uint
ev_backend.argtypes = [ev_loop_p]

ev_now_update = libev.ev_now_update
ev_now_update.restype = None
ev_now_update.argtypes = [ev_loop_p]

if hasattr(libev, 'ev_walk'):
    ev_walk = libev.ev_walk
    ev_walk.restype = None
    ev_walk.argtypes = \
        [ev_loop_p, c_int, CFUNCTYPE(
             None, ev_loop_p, c_int, c_void_p)]

EVLOOP_NONBLOCK	= 1
EVLOOP_ONESHOT	= 2
EVUNLOOP_CANCEL = 0
EVUNLOOP_ONE    = 1
EVUNLOOP_ALL    = 2

if hasattr(libev, 'ev_loop'):
    ev_loop = libev.ev_loop
    ev_loop.restype = None
    ev_loop.argtypes = [ev_loop_p, c_int]
    ev_unloop = libev.ev_unloop
    ev_unloop.restype = None
    ev_unloop.argtypes = [ev_loop_p, c_int]

    ev_ref = libev.ev_ref
    ev_ref.restype = None
    ev_ref.argtypes = [ev_loop_p]
    ev_unref = libev.ev_unref
    ev_unref.restype = None
    ev_unref.argtypes = [ev_loop_p]

    ev_once = libev.ev_once
    ev_once.restype = None
    ev_once.argtypes = \
        [ev_loop_p, c_int, c_int, ev_tstamp, CFUNCTYPE(
             None, c_int, c_void_p), c_void_p]

if hasattr(libev, 'ev_loop_count'):
    ev_loop_count = libev.ev_loop_count
    ev_loop_count.restype = c_uint
    ev_loop_count.argtypes = [ev_loop_p]
    ev_loop_depth = libev.ev_loop_depth
    ev_loop_depth.restype = c_uint
    ev_loop_depth.argtypes = [ev_loop_p]
    ev_loop_verify = libev.ev_loop_verify
    ev_loop_verify.restype = None
    ev_loop_verify.argtypes = [ev_loop_p]

    ev_set_io_collect_interval = \
        libev.ev_set_io_collect_interval
    ev_set_io_collect_interval.restype = None
    ev_set_io_collect_interval.argtypes = \
        [ev_loop_p, ev_tstamp]
    ev_set_timeout_collect_interval = \
        libev.ev_set_timeout_collect_interval
    ev_set_timeout_collect_interval.restype = None
    ev_set_timeout_collect_interval.argtypes = \
        [ev_loop_p, ev_tstamp]

    ev_set_userdata = libev.ev_set_userdata
    ev_set_userdata.restype = None
    ev_set_userdata.argtypes = [ev_loop_p, c_void_p]
    ev_userdata = libev.ev_userdata
    ev_userdata.restype = None
    ev_userdata.argtypes = [ev_loop_p]
    ev_set_invoke_pending_cb = \
        libev.ev_set_invoke_pending_cb
    ev_set_invoke_pending_cb.restype = None
    ev_set_invoke_pending_cb.argtypes = \
        [ev_loop_p, CFUNCTYPE(None, ev_loop_p)]
    ev_set_loop_release_cb = libev.ev_set_loop_release_cb
    ev_set_loop_release_cb.restype = None
    ev_set_loop_release_cb.argtypes = \
        [ev_loop_p, CFUNCTYPE(None, ev_loop_p),
             CFUNCTYPE(None, ev_loop_p)]

    ev_pending_count = libev.ev_pending_count
    ev_pending_count.restype = c_uint
    ev_pending_count.argtypes = [ev_loop_p]
    ev_invoke_pending = libev.ev_invoke_pending
    ev_invoke_pending.restype = None
    ev_invoke_pending.argtypes = [ev_loop_p]

    ev_suspend = libev.ev_suspend
    ev_suspend.restype = None
    ev_suspend.argtypes = [ev_loop_p]
    ev_resume = libev.ev_resume
    ev_resume.restype = None
    ev_resume.argtypes = [ev_loop_p]

ev_feed_event = libev.ev_feed_event
ev_feed_event.restype = None
ev_feed_event.argtypes = [ev_loop_p, c_void_p, c_int]
ev_feed_fd_event = libev.ev_feed_fd_event
ev_feed_fd_event.restype = None
ev_feed_fd_event.argtypes = [ev_loop_p, c_int, c_int]
ev_feed_signal_event = libev.ev_feed_signal_event
ev_feed_signal_event.restype = None
ev_feed_signal_event.argtypes = [ev_loop_p, c_int]
ev_invoke = libev.ev_invoke
ev_invoke.restype = None
ev_invoke.argtypes = [ev_loop_p, c_int, c_int]
ev_clear_pending = libev.ev_clear_pending
ev_clear_pending.restype = c_int
ev_clear_pending.argtypes = [ev_loop_p, c_void_p]

ev_io_start = libev.ev_io_start
ev_io_start.restype = None
ev_io_start.argtypes = [ev_loop_p, ev_io_p]
ev_io_stop = libev.ev_io_stop
ev_io_stop.restype = None
ev_io_stop.argtypes = [ev_loop_p, ev_io_p]

ev_timer_start = libev.ev_timer_start
ev_timer_start.restype = None
ev_timer_start.argtypes = [ev_loop_p, ev_timer_p]
ev_timer_stop = libev.ev_timer_stop
ev_timer_stop.restype = None
ev_timer_stop.argtypes = [ev_loop_p, ev_timer_p]
ev_timer_again = libev.ev_timer_again
ev_timer_again.restype = None
ev_timer_again.argtypes = [ev_loop_p, ev_timer_p]
ev_timer_remaining = libev.ev_timer_remaining
ev_timer_remaining.restype = ev_tstamp
ev_timer_remaining.argtypes = [ev_loop_p, ev_timer_p]

ev_periodic_start = libev.ev_periodic_start
ev_periodic_start.restype = None
ev_periodic_start.argtypes = [ev_loop_p, ev_periodic_p]
ev_periodic_stop = libev.ev_periodic_stop
ev_periodic_stop.restype = None
ev_periodic_stop.argtypes = [ev_loop_p, ev_periodic_p]
ev_periodic_again = libev.ev_periodic_again
ev_periodic_again.restype = None
ev_periodic_again.argtypes = [ev_loop_p, ev_periodic_p]

ev_signal_start = libev.ev_signal_start
ev_signal_start.restype = None
ev_signal_start.argtypes = [ev_loop_p, ev_signal_p]
ev_signal_stop = libev.ev_signal_stop
ev_signal_stop.restype = None
ev_signal_stop.argtypes = [ev_loop_p, ev_signal_p]

ev_child_start = libev.ev_child_start
ev_child_start.restype = None
ev_child_start.argtypes = [ev_loop_p, ev_child_p]
ev_child_stop = libev.ev_child_stop
ev_child_stop.restype = None
ev_child_stop.argtypes = [ev_loop_p, ev_child_p]

# XXX ev_stat_start ev_stat_stop ev_stat_stat

if hasattr(libev, 'ev_idle_start'):
    ev_idle_start = libev.ev_idle_start
    ev_idle_start.restype = None
    ev_idle_start.argtypes = [ev_loop_p, ev_idle_p]
    ev_idle_stop = libev.ev_idle_stop
    ev_idle_stop.restype = None
    ev_idle_stop.argtypes = [ev_loop_p, ev_idle_p]

ev_prepare_start = libev.ev_prepare_start
ev_prepare_start.restype = None
ev_prepare_start.argtypes = [ev_loop_p, ev_prepare_p]
ev_prepare_stop = libev.ev_prepare_stop
ev_prepare_stop.restype = None
ev_prepare_stop.argtypes = [ev_loop_p, ev_prepare_p]

ev_check_start = libev.ev_check_start
ev_check_start.restype = None
ev_check_start.argtypes = [ev_loop_p, ev_check_p]
ev_check_stop = libev.ev_check_stop
ev_check_stop.restype = None
ev_check_stop.argtypes = [ev_loop_p, ev_check_p]

if hasattr(libev, 'ev_fork_start'):
    ev_fork_start = libev.ev_fork_start
    ev_fork_start.restype = None
    ev_fork_start.argtypes = [ev_loop_p, ev_fork_p]
    ev_fork_stop = libev.ev_fork_stop
    ev_fork_stop.restype = None
    ev_fork_stop.argtypes = [ev_loop_p, ev_fork_p]

if hasattr(libev, 'ev_embed_start'):
    ev_embed_start = libev.ev_embed_start
    ev_embed_start.restype = None
    ev_embed_start.argtypes = [ev_loop_p, ev_embed_p]
    ev_embed_stop = libev.ev_embed_stop
    ev_embed_stop.restype = None
    ev_embed_stop.argtypes = [ev_loop_p, ev_embed_p]
    ev_embed_sweep = libev.ev_embed_sweep
    ev_embed_sweep.restype = None
    ev_embed_sweep.argtypes = [ev_loop_p, ev_embed_p]

# XXX ev_async_start ev_async_stop ev_async_send
