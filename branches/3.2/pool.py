def apply(func, args=(), kwargs={}, timeout=-1):
    back_ = getcurrent()
    id_   = c_uint(id(back_)).value
    data  = frame()
    data.back_  = back_
    data.func   = func
    data.args   = args
    data.kwargs = kwargs
    if -1 == timeout:
        objects[id_] = ref(data)
        try:
            req = eio_custom(c_execute, 0, c_cb, id_)
            contents = req.contents
            back_.parent.switch()
            if contents.cancelled:
                raise default_cancelled
            if 0 == contents.result:
                return data.result
            raise data.exception
        finally:
            del objects[id_]
    else:
        timer1 = ev_timer()
        memmove(byref(timer1), timer0, sizeof_timer)
        timer1.at = timeout
        timer1.data  = id_
        objects[id_] = ref(data)
        ev_timer_start(EV_DEFAULT_UC, byref(timer1))
        try:
            req = eio_custom(c_execute, 0, c_cb, id_)
            contents = req.contents
            try:
                back_.parent.switch()
            except Timeout:
                if 1 == data.readystate:
                    wait = Wait()
                    wait.get_frame = ref(data)
                    raise wait
                if 0 == data.readystate:
                    if contents.cancelled:
                        raise default_cancelled
                    eio_cancel(req)
                    raise
            if contents.cancelled:
                raise default_cancelled
            if 0 == contents.result:
                return data.result
            raise data.exception
        finally:
            ev_timer_stop (EV_DEFAULT_UC, byref(timer1))
            del objects[id_]

class frame:
    back_  = func = args = kwargs = None
    result = exception = None
    readystate = 0

import sys
from pyev  import *
from pyeio import *
from weakref import ref
from errno import ETIMEDOUT
from greenlet import getcurrent
from traceback import print_exc
from exceptions_ import Cancelled, Wait, Unknow

def cb(req):
    id_ = req.contents.data
    try:
        objects[id_]().back_.switch()
    except:
        print_exc(file=sys.stderr)
    return 0

c_cb = eio_cb(cb)

def execute(req):
    contents = req.contents
    id_      = contents.data
    try:
        data = objects[id_]()
        data.readystate = 1
        try:
            res = data.func(*data.args, **data.kwargs)
        except BaseException, err:
            data.exception = err
            contents.result = -1
            data.readystate =  2
        except:
            data.exception = default_unknow
            contents.result = -1
            data.readystate =  2
        else:
            data.result = res
            data.readystate =  2
    except:
        print_exc(file=sys.stderr)
    return 0

c_execute = eio_custom.argtypes[0](execute)

def timer_cb(l, w, e):
    id_ = w.contents.data
    try:
        objects[id_]().back_.throw(
            Timeout,
            Timeout(ETIMEDOUT, 'operation timed out'))
    except:
        print_exc(file=sys.stderr)

for k, v in ev_timer._fields_:
    if 'cb' == k:
        c_timer_cb = v(timer_cb)

def get_timer0():
    timer1 = ev_timer()
    buf = create_string_buffer(sizeof_timer)
    memset(byref(timer1), 0, sizeof_timer)
    timer1.cb = c_timer_cb
    memmove(buf, byref(timer1), sizeof_timer)
    return buf

sizeof_timer = sizeof(ev_timer)
timer0 = get_timer0(); del get_timer0, k, v

default_cancelled = Cancelled()
default_unknow    = Unknow()
objects = {}
