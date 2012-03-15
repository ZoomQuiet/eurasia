from pyev   import *
from signal import SIGINT

def keyboard_interrupt_cb(l, w, e):
    ev_unloop(EV_DEFAULT_UC, EVUNLOOP_ALL)

for field, cb in ev_signal._fields_:
    if 'cb' == field:
        c_keyboard_interrupt_cb = cb(keyboard_interrupt_cb)
del field, cb

keyboard_interrupt = ev_signal()
memset(byref(keyboard_interrupt), 0, sizeof(ev_signal))
keyboard_interrupt.cb = c_keyboard_interrupt_cb
keyboard_interrupt.signum = SIGINT
ev_signal_start(EV_DEFAULT_UC, byref(keyboard_interrupt))
