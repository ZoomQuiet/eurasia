from ev import *

def run(flags=0):
    ev_run(EV_DEFAULT_UC, flags)

def break_(how=EVBREAK_ALL):
    ev_break(EV_DEFAULT_UC, how)

EV_DEFAULT_UC = ev_default_loop(0)
