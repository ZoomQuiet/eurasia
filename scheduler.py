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
    back_ = getcurrent()
    timer_switch(back_, back_.parent, seconds)
    return back_

def sleep_raise(seconds):
    back_ = getcurrent()
    timer_switch_raise(back_, back_.parent, seconds)
    return back_

def new_sleep():
    back_ = getcurrent()
    timer_switch1 = new_timer_switch(back_)
    def sleep1(seconds):
        return timer_switch1(back_.parent, seconds)
    return sleep1

def new_sleep_raise():
    back_ = getcurrent()
    timer_switch1 = new_timer_switch_raise(back_)
    def sleep1(seconds):
        return timer_switch1(back_.parent, seconds)
    return sleep1

def idle():
    back_ = getcurrent()
    idle_switch(back_, back_.parent, None)
    return back_

def new_idle():
    back_ = getcurrent()
    idle_switch1 = new_idle_switch(back_)
    def idle1():
        return idle_switch1(back_.parent)
    return idle1

code = '''class new_timer_%(name)s%(desc)s:
    def __init__(self, back_):
        self.timer = timer1 = ev_timer()
        memmove(byref(timer1), %(timer0)s, sizeof_timer)
        timer1.data = self.id_ = id_ = c_uint(id(back_)).value
        objects[id_] = ref(back_)
    def __del__(self):
        del objects[self.id_]
        if self.timer.active:
            ev_timer_stop(EV_DEFAULT_UC, byref(self.timer))
    def __call__(self, goto_, seconds, %(args)s):
        assert not self.timer.active
        timer1 = self.timer
        timer1.at = seconds
        ev_timer_start(EV_DEFAULT_UC, byref(timer1))
        try:
            %(func)s
        finally:
            ev_timer_stop(EV_DEFAULT_UC, byref(timer1))
    def stop(self):
        if self.timer.active:
            ev_timer_stop(EV_DEFAULT_UC, byref(self.timer))
def timer_%(name)s%(desc)s(back_, goto_, seconds, %(args)s):
    timer1 = ev_timer()
    memmove(byref(timer1), %(timer0)s, sizeof_timer)
    timer1.at = seconds
    timer1.data = id_ = c_uint(id(back_)).value
    objects[id_] = ref(back_)
    ev_timer_start(EV_DEFAULT_UC, byref(timer1))
    try:
        %(func)s
    finally:
        ev_timer_stop(EV_DEFAULT_UC, byref(timer1))
        del objects[id_]'''
for desc, timer0 in [('', 'timer00'), ('_raise', 'timer01')]:
    for name, args, func in [
        ('switch', 'args=()', 'goto_.switch(*args)'),
        ('throw' , 'args=()', 'goto_.throw (*args)')]:
        exec(code % {
            'args': args, 'desc': desc, 'func': func,
                'name': name, 'timer0': timer0})

code = '''class new_idle_%(name)s:
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
        idle1 = self.idle
        ev_idle_start(EV_DEFAULT_UC, byref(idle1))
        try:
            %(func)s
        finally:
            ev_idle_stop(EV_DEFAULT_UC, byref(idle1))
    def stop(self):
        if self.idle.active:
            ev_idle_stop(EV_DEFAULT_UC, byref(self.idle))
def idle_%(name)s(back_, goto_, %(args)s):
    idle1 = ev_idle()
    memmove(byref(idle1), idle0, sizeof_idle)
    idle1.data = id_ = c_uint(id(back_)).value
    objects[id_] = ref(back_)
    ev_idle_start(EV_DEFAULT_UC, byref(idle1))
    try:
        %(func)s
    finally:
        ev_idle_stop(EV_DEFAULT_UC, byref(idle1))
        del objects[id_]'''
for name, args, func in [
    ('switch', 'args=()', 'goto_.switch(*args)'),
    ('throw' , 'args=()', 'goto_.throw (*args)')]:
    exec(code % {'name': name, 'args': args, 'func': func})
del args, code, desc, func, name, timer0

def callback(l, w, e):
    id_   = w.contents.data
    back_ =  objects[id_]()
    try:
        back_.switch()
    except:
        print_exc(file=sys.stderr)

def timer_cb(l, w, e):
    id_   = w.contents.data
    back_ =  objects[id_]()
    try:
        back_.throw(
            Timeout,
            Timeout(ETIMEDOUT, 'operation timed out'))
    except:
        print_exc(file=sys.stderr)

def find_cb(type_):
    for k, v in type_._fields_:
        if 'cb' == k:
            return v

def get_timer0(c_callback):
    timer1 = ev_timer()
    buf = create_string_buffer(sizeof_timer)
    memset(byref(timer1), 0, sizeof_timer)
    timer1.cb = c_callback
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
from errno import ETIMEDOUT
from collections import deque
from greenlet import getcurrent
from traceback import print_exc
from exceptions_ import Empty, Full, Timeout

objects = {}
sizeof_timer = sizeof (ev_timer)
c_timer_cb00 = find_cb(ev_timer)(callback)
c_timer_cb01 = find_cb(ev_timer)(timer_cb)
timer00 = get_timer0(c_timer_cb00);
timer01 = get_timer0(c_timer_cb01); del get_timer0

if hasattr(libev, 'ev_idle_start'):
    default_full  = Full()
    default_empty = Empty()
    sizeof_idle = sizeof (ev_idle)
    c_idle_cb = find_cb(ev_idle)(callback)
    idle0 = get_idle0(); del get_idle0
