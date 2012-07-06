from eio  import *
from pyev import *

# eio.pod#INITIALISATION_INTEGRATION

def repeat(l, w, e):
    if -1 != eio_poll() and repeat_watcher.active:
        ev_idle_stop(EV_DEFAULT_UC, byref(repeat_watcher))

repeat_watcher = ev_idle()
memset(byref(repeat_watcher), 0, sizeof(ev_idle))
for field, cb in ev_idle._fields_:
    if 'cb' == field:
        c_repeat = cb(repeat)
repeat_watcher.cb = c_repeat

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
