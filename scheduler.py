import sys
from pyev import *
from weakref  import ref
from greenlet import getcurrent
from traceback import print_exc

class Sleep:
    def __init__(self):
        co = getcurrent()
        self.id_ = id_ = c_uint(id(co)).value
        self.tm  = tm  = ev_timer()
        memmove(byref(tm), timer0, sizeof_timer)
        tm.data = id_
        objects[id_] = ref(co)

    def __del__(self):
        del objects[self.id_]
        if self.tm.active:
            ev_timer_stop(EV_DEFAULT_UC, byref(self.tm))

    def __call__(self, seconds):
        assert not self.tm.active
        co = objects[self.id_]
        tm = self.tm
        tm.at = seconds
        ev_timer_start(EV_DEFAULT_UC, byref(tm))
        try:
            co.parent.switch()
        finally:
            ev_timer_stop(EV_DEFAULT_UC, byref(tm))

def sleep(seconds):
    co  = getcurrent()
    id_ = c_uint(id(co)).value
    tm  = ev_timer()
    memmove(byref(tm), timer0, sizeof_timer)
    tm.at = seconds
    tm.data = id_
    objects[id_] = ref(co)
    ev_timer_start(EV_DEFAULT_UC, byref(tm))
    try:
        co.parent.switch()
    finally:
        ev_timer_stop(EV_DEFAULT_UC, byref(tm))
        del objects[id_]

def callback(l, w, e):
    id_ = w.contents.data
    co  = objects[id_]()
    try:
        co.switch()
    except:
        print_exc(file=sys.stderr)

def find_cb(type_):
    for k, v in type_._fields_:
        if 'cb' == k:
            return v

def get_timer0():
    tm = ev_timer()
    buf = create_string_buffer(sizeof_timer)
    memset(byref(tm), 0, sizeof_timer)
    tm.cb = c_sleep_cb
    memmove(buf, byref(tm), sizeof_timer)
    return buf

objects = {}
sizeof_timer = sizeof (ev_timer)
c_sleep_cb   = find_cb(ev_timer)(callback)
timer0 = get_timer0(); del get_timer0

if hasattr(libev, 'ev_idle_start'):
    class Idle:
        def __init__(self):
            co = getcurrent()
            self.id_ = id_ = c_uint(id(co)).value
            self.idl = idl = ev_idle()
            memmove(byref(idl), idle0, sizeof_idle)
            idl.data = id_
            objects[id_] = ref(co)

        def __del__(self):
            del objects[self.id_]
            if self.idl.active:
                ev_idle_stop(EV_DEFAULT_UC, byref(self.idl))

        def __call__(self):
            assert not self.idl.active
            co  = objects[self.id_]
            idl = self.idl
            ev_idle_start(EV_DEFAULT_UC, byref(idl))
            try:
                co.parent.switch()
            finally:
                ev_idle_stop(EV_DEFAULT_UC, byref(idl))

    def idle():
        co  = getcurrent()
        id_ = c_uint(id(co)).value
        idl = ev_idle()
        memmove(byref(idl), idle0, sizeof_idle)
        idl.data = id_
        objects[id_] = ref(co)
        ev_idle_start(EV_DEFAULT_UC, byref(idl))
        try:
            co.parent.switch()
        finally:
            ev_idle_stop(EV_DEFAULT_UC, byref(idl))
            del objects[id_]

    def get_idle0():
        idl = ev_idle()
        buf = create_string_buffer(sizeof_idle)
        memset(byref(idl), 0, sizeof_idle)
        idl.cb = c_idle_cb
        memmove(buf, byref(idl), sizeof_idle)
        return buf

    sizeof_idle = sizeof (ev_idle)
    c_idle_cb   = find_cb(ev_idle)(callback)
    idle0 = get_idle0(); del get_idle0
