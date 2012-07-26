class Queue:
    def __init__(self):
        self.queue = deque()

    def __len__(self):
        if -1 == self.preference:
            return len(self.queue)
        else:
            return 0

    def put(self, data, timeout=-1):
        back_ = getcurrent()
        if 1 == self.preference:
            goto_, timer1 = self.queue.popleft()
            if not self.queue:
                self.preference = 0
            if timer1 is not None:
                timer.stop()
            idle_switch(back_, goto_, data)
        else:
            if 0 == timeout:
                raise default_full
            elif -1 == timeout:
                self.queue.append((back_, None, data))
                self.preference = -1
                back_.parent.switch()
            else:
                goto_  =  back_.parent
                item   = (back_, timer1, data)
                timer1 =  new_timer_throw(back_)
                self.queue.append(item)
                self.preference = -1
                try:
                    timer1(goto_, timeout, Full, default_full)
                except Full:
                    self.queue.remove(item)
                    if not self.queue:
                        self.preference = 0
                    raise

    def get(self, timeout=-1):
        back_ = getcurrent()
        if -1 == self.preference:
            goto_, timer1, data = self.queue.popleft()
            if not self.queue:
                self.preference = 0
            if timer1 is not None:
                timer1.stop()
            idle_switch(back_, goto_, None)
            return data
        else:
            if 0 == timeout:
                raise default_empty
            elif -1 == timeout:
                self.queue.append((back_, None))
                self.preference = 1
                return back_.parent.switch()
            else:
                goto_  =  back_.parent
                item   = (back_, timer1)
                timer1 =  new_timer_throw(back_)
                self.queue.append(item)
                self.preference = 1
                try:
                    timer1(goto_, timeout, Empty, default_empty)
                except Empty:
                    self.queue.remove(item)
                    if not self.queue:
                        self.preference = 0
                    raise

    def full(self):
        return self.preference != 1

    def empty(self):
        return self.preference != -1

    def balance(self):
        return self.preference * len(self.queue)

    balance, preference = property(balance), 0

def sleep(seconds):
    co = getcurrent()
    timer_switch(co, co.parent, seconds, None)

def new_sleep():
    co = getcurrent()
    timer_switch1 = new_timer_switch(co)
    def sleep1(seconds):
        return timer_switch1(co.parent, seconds)
    return sleep1

def idle():
    co = getcurrent()
    idle_switch(co, co.parent, None)

def new_idle():
    co = getcurrent()
    idle_switch1 = new_idle_switch(co)
    def idle1():
        return idle_switch1(co.parent)
    return idle1

code = '''class new_timer_%(name)s:
    def __init__(self, back_):
        self.timer = timer1 = ev_timer()
        memmove(byref(timer1), timer0, sizeof_timer)
        timer1.data = self.id_ = id_ = c_uint(id(back_)).value
        objects[id_] = ref(back_)
    def __del__(self):
        del objects[self.id_]
        if self.timer.active:
            ev_timer_stop(EV_DEFAULT_UC, byref(self.timer))
    def __call__(self, goto_, seconds, %(args)s):
        assert not self.timer.active
        co  =  getcurrent()
        timer1 = self.timer
        timer1.at = seconds
        ev_timer_start(EV_DEFAULT_UC, byref(timer1))
        co.parent = goto_.parent
        goto_.parent = co
        try:
            %(func)s
        finally:
            ev_timer_stop(EV_DEFAULT_UC, byref(timer1))
    def stop(self):
        if self.timer.active:
            ev_timer_stop(EV_DEFAULT_UC, byref(self.timer))
def timer_%(name)s(back_, goto_, seconds, %(args)s):
    co  =  getcurrent()
    timer1 = ev_timer()
    memmove(byref(timer1), timer0, sizeof_timer)
    timer1.at = seconds
    timer1.data = id_ = c_uint(id(back_)).value
    objects[id_] = ref(back_)
    ev_timer_start(EV_DEFAULT_UC, byref(timer1))
    co.parent = goto_.parent
    goto_.parent = co
    try:
        %(func)s
    finally:
        ev_timer_stop(EV_DEFAULT_UC, byref(timer1))
        del objects[id_]
class new_idle_%(name)s:
    def __init__(self, back_):
        self.idle = idle1 = ev_idle()
        memmove(byref(idle1), idle0, sizeof_idle)
        idle1.data = self.id_ = id_ = c_uint(id(back_)).value
        objects[id_] = ref(back_)
    def __del__(self):
        del objects[self.id_]
        if self.idle.active:
            ev_idle_stop(EV_DEFAULT_UC, byref(self.idle))
    def __call__(self, goto_, %(args)s):
        assert not self.idle.active
        co = getcurrent()
        idle1 = self.idle
        ev_idle_start(EV_DEFAULT_UC, byref(idle1))
        co.parent = goto_.parent
        goto_.parent = co
        try:
            %(func)s
        finally:
            ev_idle_stop(EV_DEFAULT_UC, byref(idle1))
    def stop(self):
        if self.idle.active:
            ev_idle_stop(EV_DEFAULT_UC, byref(self.idle))
def idle_%(name)s(back_, goto_, %(args)s):
    co = getcurrent()
    idle1 = ev_idle()
    memmove(byref(idle1), idle0, sizeof_idle)
    idle1.data = id_ = c_uint(id(back_)).value
    objects[id_] = ref(back_)
    ev_idle_start(EV_DEFAULT_UC, byref(idle1))
    co.parent = goto_.parent
    goto_.parent = co
    try:
        %(func)s
    finally:
        ev_idle_stop(EV_DEFAULT_UC, byref(idle1))
        del objects[id_]'''
for name, args, func in [
    ('switch', 'data=None', 'goto_.switch(data)'),
    ('throw' , '*args'    , 'goto_.throw(*args)')]:
    exec(code % {'name': name, 'args': args, 'func': func})
del code, name, args, func

def callback(l, w, e):
    id_    = w.contents.data
    back_  =  objects[id_]()
    co     =    getcurrent()
    co.parent = back_.parent
    back_.parent = co
    try:
        co.switch()
    except:
        print_exc(file=sys.stderr)

def find_cb(type_):
    for k, v in type_._fields_:
        if 'cb' == k:
            return v

def get_timer0():
    timer1 = ev_timer()
    buf = create_string_buffer(sizeof_timer)
    memset(byref(timer1), 0, sizeof_timer)
    timer1.cb = c_timer_cb
    memmove(buf, byref(timer1), sizeof_timer)
    return buf

def get_idle0():
    idle1 = ev_idle()
    buf = create_string_buffer(sizeof_idle)
    memset(byref(idle1), 0, sizeof_idle)
    idle1.cb = c_idle_cb
    memmove(buf, byref(idle1), sizeof_idle)
    return buf

import sys
from pyev import *
from weakref  import ref
from collections import deque
from greenlet import getcurrent
from traceback import print_exc
from exceptions_ import Empty, Full, Timeout

objects = {}
sizeof_timer = sizeof (ev_timer)
c_timer_cb   = find_cb(ev_timer)(callback)
timer0 = get_timer0(); del get_timer0

if hasattr(libev, 'ev_idle_start'):
    default_full  = Full()
    default_empty = Empty()
    sizeof_idle = sizeof (ev_idle)
    c_idle_cb = find_cb(ev_idle)(callback)
    idle0 = get_idle0(); del get_idle0
