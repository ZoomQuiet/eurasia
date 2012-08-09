def apply(func, args=(), kwargs={}, timeout=-1):
    co  = getcurrent()
    id_ = c_uint(id(co)).value
    if -1 == timeout:
        data = [co, None, func, args, kwargs]
        objects[id_] = data
        req = eio_custom (c_execute, 0, c_cb, id_)
        contents = req.contents
        try:
            co.parent.switch()
            if contents.cancelled:
                raise default_cancelled
            if 0 == contents.result:
                return data[1]
            raise data[1]
        finally:
            del objects[id_]
    else:
        data = [co, None, func, args, kwargs, 0]
        objects[id_] = data
        timer1 = ev_timer()
        memmove(byref(timer1), timer0, sizeof_timer)
        timer1.at   = timeout
        timer1.data = id_
        ev_timer_start(EV_DEFAULT_UC, byref(timer1))
        req = eio_custom (c_execute_t, 0, c_cb, id_)
        contents = req.contents
        try:
            try:
                co.parent.switch()
            except Timeout:
                if contents.cancelled:
                    raise default_cancelled
                elif 0 == data[5]:
                    eio_cancel(req)
                    raise
                elif 1 == data[5]:
                    e = Running()
                    e.data = data
                    raise e
                elif 2 == data[5]:
                    pass
                else:
                    raise
            if contents.cancelled:
                raise default_cancelled
            if 0 == contents.result:
                return data[1]
            raise data[1]
        finally:
            ev_timer_stop(EV_DEFAULT_UC, byref(timer1))
            del objects[id_]

import os, sys
from pyev  import *
from pyeio import *
from greenlet import getcurrent
from traceback import print_exc
from collections import namedtuple
from exceptions_ import Cancelled, Running, Unknow

def cb(req):
    id_ = req.contents.data
    try:
        objects[id_][0].switch()
    except:
        print_exc(file=sys.stderr)
    return 0

c_cb = eio_cb(cb)

def execute(req):
    contents = req.contents
    id_      = contents.data
    data     = objects[id_]
    try:
        res = data[2](*data[3], **data[4])
    except BaseException, err:
        contents.result = -1
        data[1] = err
    except:
        contents.result = -1
        data[1] = default_unknow
    else:
        contents.result =  0
        data[1] = res
    return 0

c_execute = eio_custom.argtypes[0](execute)

def execute_t(req):
    contents = req.contents
    id_      = req.contents.data
    data     = objects[id_]
    data[5] = 1
    try:
        res = data[2](*data[3], **data[4])
    except BaseException, err:
        contents.result = -1
        data[1] = err
        data[5] = 2
    except:
        contents.result = -1
        data[1] = default_unknow
        data[5] = 2
    else:
        contents.result =  0
        data[1] = res
        data[5] = 2
    return 0

def timer_cb(l, w, e):
    id_  = w.contents.data
    try:
        objects[id_].g.throw(
            Timeout,
            Timeout(ETIMEOUT, 'operation timed out'))
    except:
        print_exc(file=sys.stderr)

def get_timer0():
    timer1 = ev_timer()
    buf = create_string_buffer(sizeof_timer)
    memset(byref(timer1), 0, sizeof_timer)
    timer1.cb = c_timer_cb
    memmove(buf, byref(timer1), sizeof_timer)
    return buf

for k, v in ev_timer._fields_:
    if 'cb' == k:
        c_timer_cb = v(timer_cb)

c_execute_t = eio_custom.argtypes[0](execute_t)
default_cancelled = Cancelled()
default_unknow    = Unknow()
sizeof_timer = sizeof(ev_timer)
timer0 = get_timer0(); del get_timer0, k, v
objects = {}
