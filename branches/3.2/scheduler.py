from pyev     import *
from weakref  import ref
from greenlet import getcurrent

if hasattr(libev, 'ev_idle_start'):
    class Idle:
        def __init__(self):
            self.idle = idle = ev_idle()
            memmove(byref(idle), idle0, sizeof_idle)
            id_ = c_uint(id(self)).value
            objects[id_] = ref(self)

        def __del__(self):
            if self.idle.active:
                ev_idle_stop(EV_DEFAULT_UC, byref(self.idle))
            id_ = c_uint(id(self)).value
            if id_ in objects:
                del objects[id_]

        def __call__(self):
            self.co = co = getcurrent()
            ev_idle_start(EV_DEFAULT_UC, byref(self.idle))
            try:
                co.parent.switch()
            finally:
                ev_idle_stop(EV_DEFAULT_UC, byref(self.idle))
                self.co = None
            id_ = c_uint(id(self)).value
            if id_ in objects:
                del objects[id_]

        co = None

    def idle_cb(l, w, e):
        id_ = w.contents.data
        idle = objects[id_]()
        if idle is not None and idle.co is not None:
            try:
                idle.co.switch()
            except:
                print_exc(file=sys.stderr)

    for field, cb in ev_idle._fields_:
        if 'cb' == field:
            c_idle_cb = cb(idle_cb)

    def get_idle0():
        idle = ev_idle()
        buf  = create_string_buffer(sizeof_idle)
        memset(byref(idle), 0, sizeof_idle)
        idle.cb = c_idle_cb
        memmove(buf, byref(idle), sizeof_idle)
        return buf

    sizeof_idle = sizeof(ev_idle)
    idle0 = get_idle0()

if hasattr(libev, 'ev_async_start'):
    class Sleep:
        def __init__(self):
            self.timer = timer = ev_timer()
            memmove(byref(timer), sleep0, sizeof_idle)
            id_ = c_uint(id(self)).value
            objects[id_] = ref(self)

        def __del__(self):
            if self.timer.active:
                ev_timer_stop(EV_DEFAULT_UC, byref(self.timer))
            id_ = c_uint(id(self)).value
            if id_ in objects:
                del objects[id_]

        def __call__(self, seconds):
            self.co =  co = getcurrent()
            self.timer.at = seconds
            ev_timer_start(EV_DEFAULT_UC, byref(self.timer))
            try:
                co.parent.switch()
            finally:
                ev_timer_stop(EV_DEFAULT_UC, byref(self.timer))
                self.co = None

        co = None

    def sleep_cb(l, w, e):
        id_ = w.contents.data
        timer = objects[id_]()
        if timer is not None and timer.co is not None:
            try:
                timer.co.switch()
            except:
                print_exc(file=sys.stderr)

    for field, cb in ev_timer._fields_:
        if 'cb' == field:
            c_sleep_cb = cb(sleep_cb)

    def get_sleep0():
        timer = ev_timer()
        buf = create_string_buffer(sizeof_timer)
        memset(byref(timer), 0, sizeof_timer)
        timer.cb = c_sleep_cb
        memmove(buf, byref(timer), sizeof_timer)
        return buf

    sizeof_timer = sizeof(ev_timer)
    sleep0 = get_sleep0()

objects = {}
