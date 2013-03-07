############################################################################
# Copyright (c) 2007-2012  Wilhelm Shen
# Copyright (c) 2011-2012  Huzhou Xunpu InfoTech Co.,Ltd.  <www.pyforce.com>
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are
# met:
#
# * Redistributions of source code must retain the above copyright notice,
#   this list of conditions and the following disclaimer.
#
# * Redistributions in binary form must reproduce the above copyright
#   notice, this list of conditions and the following disclaimer in the
#   documentation and/or other materials provided with the distribution.
#
# * Neither the name of the Eurasia nor the names of its contributors may be
#   used to endorse or promote products derived from this software without
#   specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED
# TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR
# PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR
# CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL,
# EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO,
# PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR
# PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF
# LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
# NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
############################################################################

__version__, revision = '3.2', '$Revision$'
if revision.find(':') >= 0:
    revision = revision[revision.find(':')+1:revision.rfind('$')].strip()
    __version__ = '%s:%s' % (__version__, revision)
else:
    revision = ''

def find_library(name):
    import ctypes.util
    where = ctypes.util.find_library(name)
    if where is not None:
        return where
    import os, posixpath
    root = 'lib' + name
    dn = posixpath.dirname(__file__)
    base = posixpath.abspath(dn)
    for fn in os.listdir(base):
        items = fn.split('.')
        if len(items) > 1 and items[0] == root and \
           items[1] in ('so', 'dll', 'dylib'):
            where = posixpath.join(base, fn)
            if posixpath.isfile(where):
                return where

def declare(lib, defs):
    for line in defs.split(';'):
        name, args = line.split(':', 1)
        attr = name.strip()
        func = getattr(lib, attr, None)
        if func is None:
            continue
        argtypes = []
        for arg in args.split(','):
            argtypes.append(eval(arg))
        func.restype = argtypes.pop(0)
        func.argtypes = tuple(argtypes)
        globals()[attr] = func

def _fields_(fields):
    lines = []
    for field in fields.split(';'):
        key, val = field.split(':', 1)
        line = '("%s", %s)' % (key.strip(), val.strip())
        lines.append(line)
    code = '[%s]' % ', '.join(lines)
    return eval(code)

def __USE_FILE_OFFSET64():
    import platform
    uname_r = platform.uname()[2]
    fn = '/lib/modules/%s/build/.config' % uname_r
    try:
        fd = open(fn, 'r')
    except IOError:
        return False
    confs = fd.read()
    fd.close()
    for conf in confs.split('\n'):
        try:
            key, val = conf.split('=', 1)
        except ValueError:
            continue
        if 'CONFIG_LARGEFILE' == key.strip().upper():
            if 'y' == val.strip().lower():
                return True
            return False
    return False

from ctypes import *

NULL = c_void_p(None)
c_uchar  = c_ubyte
c_mode_t = c_uint
c_sig_atomic_t = c_int

assert sizeof(c_size_t) == sizeof(c_long)
c_ssize_t = c_long

if sizeof(c_long) == sizeof(c_longlong):
    c_off_t = c_long
elif __USE_FILE_OFFSET64():
    c_off_t = c_int64
else:
    c_off_t = c_long

class c_statvfs(Structure):
    pass

c_statvfs_p = POINTER(c_statvfs)
c_statvfs._fields_ = _fields_('''\
f_bsize:c_ulong;f_frsize:c_ulong;f_blocks:c_ulong;f_bfree:c_ulong;f_bavail:\
c_ulong;f_files:c_ulong;f_ffree:c_ulong;f_favail:c_ulong;f_fsid:c_ulong;f_f\
lag:c_ulong;f_namemax:c_ulong''')

class c_stat(Structure):
    pass

c_stat_p = POINTER(c_stat)
c_stat._fields_ = _fields_('''\
st_dev:c_uint;st_ino:c_ulong;st_nlink:c_uint;pad1:c_uint;st_mode:c_int;st_u\
id:c_uint;st_gid:c_uint;pad0:c_int;st_rdev:c_uint;st_size:c_ulong;st_blksiz\
e:c_long;st_blocks:c_long;st_atime:c_long;st_atimensec:c_ulong;st_mtime:c_l\
ong;st_mtimensec:c_ulong;st_ctime:c_long;st_ctimensec:c_ulong''')

############################################################################

where = find_library('ev')
assert where, 'eurasia.py needs libev installed.'
libev = CDLL(where, use_errno=True)

EV_ATOMIC_T = c_sig_atomic_t
ev_tstamp = c_double
ev_loop_p = c_void_p # POINTER(ev_loop)

EV_UNDEF    =   -1
EV_NONE     = 0x00
EV_READ     = 0x01
EV_WRITE    = 0x02
EV__IOFDSET = 0x80

def EV_CB_DECLARE(type_):
    return CFUNCTYPE(None, c_void_p, POINTER(type_), c_int)

def EV_WATCHER(type_):
    fields = _fields_('''\
active:c_int;pending:c_int;priority:c_int;data:c_void_p''')
    fields.append(('cb', EV_CB_DECLARE(type_)))
    return fields

def EV_WATCHER_LIST(type_):
    return EV_WATCHER(type_) + [('next', ev_watcher_list_p)]

def EV_WATCHER_TIME(type_):
    return EV_WATCHER(type_) + [('at', ev_tstamp)]

class ev_watcher_list(Structure):
    pass

ev_watcher_list_p = POINTER(ev_watcher_list)
ev_watcher_list._fields_ = EV_WATCHER_LIST(ev_watcher_list)

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

class ev_signal(Structure):
    pass

ev_signal_p = POINTER(ev_signal)
ev_signal._fields_ = EV_WATCHER_LIST(ev_signal) + \
    [('signum', c_int)]

class ev_idle(Structure):
    pass

ev_idle_p = POINTER(ev_idle)
ev_idle._fields_ = EV_WATCHER(ev_idle)

class ev_async(Structure):
    pass

ev_async_p = POINTER(ev_async)
ev_async._fields_ = EV_WATCHER(ev_async) + \
    [('sent', EV_ATOMIC_T)]

if hasattr(libev, 'ev_run'):
    declare(libev, '''\
ev_default_loop:ev_loop_p,c_uint;ev_run:None,ev_loop_p,c_int;ev_break:None,\
ev_loop_p,c_int''')
    ev_default_loop_init = ev_default_loop
    ev_loop = ev_run
    ev_unloop = ev_break
else:
    declare(libev, '''\
ev_default_loop_init:ev_loop_p,c_uint;ev_loop:None,ev_loop_p,c_int;ev_unloo\
p:None,ev_loop_p,c_int''')
    ev_default_loop = ev_default_loop_init
    ev_run = ev_loop
    ev_break = ev_unloop

EVRUN_NOWAIT   = EVLOOP_NONBLOCK = 1
EVRUN_ONCE     = EVLOOP_ONESHOT  = 2
EVBREAK_CANCEL = EVUNLOOP_CANCEL = 0
EVBREAK_ONE    = EVUNLOOP_ONE    = 1
EVBREAK_ALL    = EVUNLOOP_ALL    = 2

declare(libev, '''\
ev_io_start:None,ev_loop_p,ev_io_p;ev_io_stop:None,ev_loop_p,ev_io_p;ev_tim\
er_start:None,ev_loop_p,ev_timer_p;ev_timer_stop:None,ev_loop_p,ev_timer_p;\
ev_signal_start:None,ev_loop_p,ev_signal_p;ev_signal_stop:None,ev_loop_p,ev\
_signal_p;ev_idle_start:None,ev_loop_p,ev_idle_p;ev_idle_stop:None,ev_loop_\
p,ev_idle_p;ev_async_start:None,ev_loop_p,ev_async_p;ev_async_stop:None,ev_\
loop_p,ev_async_p;ev_async_send:None,ev_loop_p,ev_async_p''')

############################################################################

where = find_library('eio')
assert where, 'eurasia.py needs libeio installed.'
libeio = CDLL(where, use_errno=True)

eio_ssize_t = c_ssize_t
eio_tstamp  = c_double
# eio_wd = c_void_p  # POINTER(eio_pwd)

class eio_pwd(Structure):
    pass

eio_wd = POINTER(eio_pwd)
eio_pwd._fields_ = [('len', c_int), ('str', c_char_p)]
# if HAVE_AT in config.h:
#     eio_pwd._fields_.insert(0, ('fd', c_int))

class eio_req(Structure):
    pass

eio_req_p = POINTER(eio_req)
eio_cb  = CFUNCTYPE(c_int, eio_req_p)
execute = CFUNCTYPE( None, eio_req_p)
eio_req._fields_ = _fields_('''\
next:eio_req_p;wd:eio_wd;result:eio_ssize_t;offs:c_off_t;size:c_size_t;ptr1\
:c_void_p;ptr2:c_void_p;nv1:eio_tstamp;nv2:eio_tstamp;type:c_int;int1:c_int\
;int2:c_long;int3:c_long;errorno:c_int;cancelled:c_uchar;flags:c_uchar;pri:\
c_char;data:c_void_p;finish:eio_cb;destory:c_void_p;feed:c_void_p;grp:eio_r\
eq_p;grp_prev:eio_req_p;grp_next:eio_req_p;grp_first:eio_req_p''')

declare(libeio, # INITIALISATION/INTEGRATION
'''\
eio_init:c_int,CFUNCTYPE(None),CFUNCTYPE(None);eio_poll:c_int;eio_nreqs:c_u\
int;'''
# CANCELLING REQUESTS
'''eio_cancel:None,eio_req_p;'''
# POSIX API WRAPPERS
'''\
eio_open:eio_req_p,c_char_p,c_int,c_mode_t,c_int,eio_cb,c_void_p;eio_trunca\
te:eio_req_p,c_char_p,c_off_t,c_int,eio_cb,c_void_p;eio_chown:eio_req_p,c_c\
har_p,c_int,c_int,c_int,eio_cb,c_void_p;eio_chmod:eio_req_p,c_char_p,c_mode\
_t,c_int,eio_cb,c_void_p;eio_mkdir:eio_req_p,c_char_p,c_mode_t,c_int,eio_cb\
,c_void_p;eio_rmdir:eio_req_p,c_char_p,c_int,eio_cb,c_void_p;eio_unlink:eio\
_req_p,c_char_p,c_int,eio_cb,c_void_p;eio_utime:eio_req_p,c_char_p,c_double\
,c_double,c_int,eio_cb,c_void_p;eio_mknod:eio_req_p,c_char_p,c_mode_t,c_off\
_t,c_int,eio_cb,c_void_p;eio_link:eio_req_p,c_char_p,c_char_p,c_int,eio_cb,\
c_void_p;eio_symlink:eio_req_p,c_char_p,c_char_p,c_int,eio_cb,c_void_p;eio_\
rename:eio_req_p,c_char_p,c_char_p,c_int,eio_cb,c_void_p;eio_mlock:eio_req_\
p,c_void_p,c_size_t,c_int,eio_cb,c_void_p;eio_close:eio_req_p,c_int,c_int,e\
io_cb,c_void_p;eio_sync:c_int,eio_cb,c_void_p;eio_fsync:eio_req_p,c_int,c_i\
nt,eio_cb,c_void_p;eio_fdatasync:eio_req_p,c_int,c_int,eio_cb,c_void_p;eio_\
futime:eio_req_p,c_int,c_double,c_double,c_int,eio_cb,c_void_p;eio_ftruncat\
e:eio_req_p,c_int,c_off_t,c_int,eio_cb,c_void_p;eio_fchmod:eio_req_p,c_int,\
c_mode_t,c_int,eio_cb,c_void_p;eio_fchown:eio_req_p,c_int,c_int,c_int,c_int\
,eio_cb,c_void_p;eio_dup2:eio_req_p,c_int,c_int,c_int,eio_cb,c_void_p;eio_r\
ead:eio_req_p,c_int,c_void_p,c_size_t,c_off_t,c_int,eio_cb,c_void_p;eio_wri\
te:eio_req_p,c_int,c_void_p,c_size_t,c_off_t,c_int,eio_cb,c_void_p;eio_mloc\
kall:eio_req_p,c_int,c_int,eio_cb,c_void_p;eio_msync:eio_req_p,c_void_p,c_s\
ize_t,c_int,c_int,eio_cb,c_void_p;eio_readlink:eio_req_p,c_char_p,c_int,eio\
_cb,c_void_p;eio_realpath:eio_req_p,c_char_p,c_int,eio_cb,c_void_p;eio_stat\
:eio_req_p,c_char_p,c_int,eio_cb,c_void_p;eio_lstat:eio_req_p,c_char_p,c_in\
t,eio_cb,c_void_p;eio_fstat:eio_req_p,c_int,c_int,eio_cb,c_void_p;eio_statv\
fs:eio_req_p,c_char_p,c_int,eio_cb,c_void_p;eio_fstatvfs:eio_req_p,c_int,c_\
int,eio_cb,c_void_p;'''
# READING DIRECTORIES
'''eio_readdir:eio_req_p,c_char_p,c_int,c_int,eio_cb,c_void_p;'''
# OS-SPECIFIC CALL WRAPPERS
'''\
eio_sendfile:eio_req_p,c_int,c_int,c_off_t,c_size_t,c_int,eio_cb,c_void_p;\
eio_readahead:eio_req_p,c_int,c_off_t,c_size_t,c_int,eio_cb,c_void_p;eio_s\
yncfs:eio_req_p,c_int,c_int,eio_cb,c_void_p;eio_sync_file_range:eio_req_p,\
c_int,c_off_t,c_size_t,c_uint,c_int,eio_cb,c_void_p;eio_fallocate:eio_req_\
p,c_int,c_mode_t,c_off_t,c_off_t,c_int,eio_cb,c_void_p;'''
# LIBEIO-SPECIFIC REQUESTS
'''\
eio_mtouch:eio_req_p,c_char_p,c_size_t,c_int,c_int,eio_cb,c_void_p;eio_cus\
tom:eio_req_p,execute,c_int,eio_cb,c_void_p;eio_busy:eio_req_p,c_double,c_\
int,eio_cb,c_void_p;eio_nop:eio_req_p,c_int,eio_cb,c_void_p;'''
# GROUPING AND LIMITING REQUESTS
'''\
eio_grp:eio_req_p, eio_cb, c_void_p;eio_grp_add:None,eio_req_p,eio_req_p;e\
io_grp_cancel:None,eio_req_p;'''
# OTHER
'''\
eio_wd_open:eio_req_p,c_char_p,c_int,eio_cb,c_void_p;eio_wd_close:eio_wd,c\
_int,eio_cb,c_void_p;eio_seek:eio_req_p,c_int,c_off_t,c_int,c_int,eio_cb,c\
_void_p;'''
# MISC GARBAGE
'''eio_sendfile_sync:eio_ssize_t,c_int,c_int,c_off_t,c_size_t''')

############################################################################

def run(flags=0):
    ev_run(EV_DEFAULT_UC, flags)

def break_(how=EVBREAK_ALL):
    ev_break(EV_DEFAULT_UC, how)

EV_DEFAULT_UC = ev_default_loop(0)

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

############################################################################

def cpu_count():
    if sys.platform == 'win32':
        return int(os.environ['NUMBER_OF_PROCESSORS'])
    elif sys.platform == 'darwin':
        return int(os.popen('sysctl -n hw.ncpu').read())
    else:
        return os.sysconf('SC_NPROCESSORS_ONLN')

def setuid(user):
    import pwd
    try:
        uid = int(user)
    except ValueError:
        try:
            pwrec = pwd.getpwnam(user)
        except KeyError:
            raise OSError ('username %r not found' % user)
        uid = pwrec[2]
    else:
        try:
            pwrec = pwd.getpwuid(uid)
        except KeyError:
            raise OSError ('uid %r not found' % user)
    euid = os.geteuid()
    if euid != 0 and euid != uid:
        raise OSError ('only root can change users')
    os.setgid(pwrec[3])
    os.setuid(uid)

def setprocname(procname, key='__PROCNAME', format='%s '):
    if not os.environ.has_key(key):
        environ = dict(os.environ)
        environ[key] = procname
        os.execlpe(*([sys.executable, format % procname] + \
                      sys.argv + [environ]))
    where = find_library('c')
    assert where, 'setprocname needs libc installed.'
    libc = CDLL(where)
    procname = create_string_buffer(procname)
    platform = sys.platform.upper()
    if 'LINUX' in platform:
        libc.prctl(15, procname, 0, 0, 0)
    elif 'BSD' in platform:
        libc.setproctitle(procname)

def meminfo():
    pairs, buf = {}, []
    fd = os.open('/proc/meminfo', os.O_RDONLY)
    try:
        data = os.read(fd, 8192)
        while data:
            buf.append(data)
            data = os.read(fd, 8192)
    finally:
        os.close(fd)
    for data in ''.join(buf).split('\n'):
        pair = data.split(':', 1)
        if 2 == len(pair):
            val = pair[1].strip()
            if ' kB' == val[-3:]:
                pairs[pair[0]] = int(val[:-3]) << 10
            else:
                pairs[pair[0]] = val
    return pairs

import os, sys

############################################################################

def find_cb(type_):
    for key, val in type_._fields_:
        if 'cb' == key:
            return val

def kbint_cb(l, w, e):
    break_(EVBREAK_ALL)

from signal import SIGINT

c_kbint_cb = find_cb(ev_signal)(kbint_cb)
kbint = ev_signal()
memset(byref(kbint), 0, sizeof(ev_signal))
kbint.cb = c_kbint_cb
kbint.signum = SIGINT
ev_signal_start(EV_DEFAULT_UC, byref(kbint))

############################################################################

socket_init = '''    self.csocket = csocket1 = csocket()
    memmove(byref(csocket1), csocket0, sizeof_csocket)
    fd = _sock.fileno()
    csocket1.r_io.fd = csocket1.w_io.fd = csocket1.x_io.fd = fd
    id_ = c_uint(id(self)).value
    csocket1.r_io.data = csocket1.w_io.data = csocket1.x_io.data = csocket1\
.r_timer.data = csocket1.w_timer.data = csocket1.x_timer.data = id_
    self._sock = _sock
    self.buf = StringIO()
    objects[id_] = ref(self)
def fileno(self):
    return self._sock.fileno()
''' + '\n'.join('''def _%(type)s_wait(self):
    ev_io_start(EV_DEFAULT_UC, byref(self.csocket.%(type)s_io))
    try:
        self.%(type)s_co.parent.switch()
    finally:
        ev_io_stop(EV_DEFAULT_UC, byref(self.csocket.%(type)s_io))
def %(type)s_wait(self, timeout):
    assert self.%(type)s_co is None, '%(desc)s conflict'
    csocket1 = self.csocket
    self.%(type)s_co = co = getcurrent()
    csocket1.%(type)s_timer.at = timeout
    ev_timer_start(EV_DEFAULT_UC, byref(csocket1.%(type)s_timer))
    ev_io_start(EV_DEFAULT_UC, byref(csocket1.%(type)s_io))
    try:
        co.parent.switch()
    finally:
        ev_io_stop(EV_DEFAULT_UC, byref(csocket1.%(type)s_io))
        ev_timer_stop(EV_DEFAULT_UC, byref(csocket1.%(type)s_timer))
        self.%(type)s_co = None''' % {
    'type': type_, 'desc': desc} for type_, desc in [
        ('r', 'read'), ('w', 'write'), ('x', 'connect')])

import base64, zlib

socket_file = zlib.decompress(base64.decodestring('''\
eNrtWG1v2zYQ/u5fwaEILCGOEPdTZ8wB1sTDigV2sTjrB88QZJluuKikQdFWs18/HknJpN7sGM4y
YCnQpiKPd8fnjs9DZolXKOQ4WnopTlY9lJK/sT/oIPlnsVmhIYLhQP43HwpSjB+9yx567+dDsEZa
wqTASeLpCbIq5q6Gyq926/rxizG+NT50NpBHMZcnIS3uBCf066eJV50NMk4E9gofvuUciw2nMkan
3R1ZhnIwDjeECo9oUHw/2EbJBiuD7IEkGPV3W5HbhEWUCUQoYou/cCzS3bQVHPL6ioXyZWWf4JVA
GiB0kUNWzAr+5DpTuYc8zCIiLC/4e4zXAk3JN8w2omaJ3i786+YWkbQl2ju0jESUt0GYsvhRYhtv
Pcja75x58BGqj7ScC+accRSlCLs+JWI4kJOUoeEQja4n4/Hvo7vRFElre2I8mcJcefju1/vpzeTL
2HVa7DNOWGrDe1gRqlDILKGmsH030kL21mMxQiU2CaYe2PnOYkhWFTWiS+XKlLa2N2B5ZTXAWopd
NLkbD/4sceK6qSbbtDw/p+dDRDu1/urRW+bkkRCKjyUQzROGOdAVumyniQXEsphCh3bYAjzCcIDp
Ms2IePC6f9KuD40EpVJzfl6eAWo6KzVMcyDb2IhBMAdTd+SNUU/PqKfnzJNQ5of+j+8LylQf/0/K
bBc8msg5cBGsCF2qk9tD8nBowbFDJXAKLt1IclCSWL/twILvGU0Gc78McS1BV3lzNqDJvIqWu0lV
1CStcWYxvvL08lJytV9KZgOwmPt7gVOOSnZHikyzpgDXSA7RXDFwjBlL1HDAw5hpawi2zzpT1rBG
gpzpH9/1jzGTdGwiys81Z2vMxZNnhvyO8W/PmaE8W3m4d+I3hKPdQ0KzyvCib3LaS4R7eM/sqdvN
jS/60BeizF41ZOc2ooFPzZvV2syhsnd5wDKNaR0xNKY+NI21UFheghLPvAir7WCC2qTyCmBqA914
TFmO0ifgRQ2FN/r86fOoh7ofOXvEFK3JGncdDBrquKtlVhGuCrEYhKs1bZCoam0VUvrEnnnwEaqP
YyTqB1mcL5P725uPt5Pr3xpEh4eNsqNEJecB62TVVa/9GJgDL+kl3nCOqWi7JTiY1FyZpB5FSVJ3
teAWk1TrE6WpJA3LkqTKVPYEREExo6uExKJbrIihIlj080uE+T58b7kDaQTA8CACxTUY7Sq61bNh
KiIuvNEf4c3ol5/vb6fh/XUPLZ44XnllT/6pAbSSYOtn51Bbgrx1Sq+Sf7t9al4mby303BY6FMQX
aiN9kWkVELs2mVsbtbpUnDVLZYDLzr4imVuyeyHcBampWnMzV2DWmgap/FRzNTR4EnZQVTNp6FdZ
vBKzfBlgAbzN44caBWhdrwUMcj8f1grYTM4N5N9zuIjNCzkrvbiczbZLW0nmLG0DqTOq17xk7zur
+UXV2vLlUu3t+1KlmskoayUjy9+pmCHbzwyv2bKtvXhgP7u/bNjTZTigm2+hbFtAVu6509ouCL+d
oP/OCXqOEmXNSpSVLzTmvmy9ctvkQ6JcVfBYkC12HjKWDWEVA0cWA/HAWeapEvfa3jZt75TjZdrq
U7sLDn1V173U4LexZnAmbeZnnvIsW1xJ//GAZwcAnrUCnr0G4NnrAf4Pl86zew=='''
)) + '\n'.join('''def %s(self):
    csocket1 = self.csocket
    if csocket1.w_timer.active:
        if csocket1.w_io.active:
            self.w_co.throw(error, error(EPIPE, 'Broken pipe'))
        else:
            ev_timer_stop(EV_DEFAULT_UC, byref(csocket1.w_tm))
    if csocket1.r_timer.active:
        if csocket1.r_io.active:
            self.r_co.throw(error, error(EPIPE, 'Broken pipe'))
        else:
            ev_timer_stop(EV_DEFAULT_UC, byref(csocket1.r_timer))
    self._sock.close()
    id_ = c_uint(id(self)).value
    if id_ in objects:
        del objects[id_]%%(close)s''' % s for s in ['close', '__del__'])

socket_sendfile = zlib.decompress(base64.decodestring('''\
eNrtVE1v2zAMvedXcCiGyphjrNcVHtC12WXBemm2o+Ap1CpMlQKJbtZ/P33YjtvaXXvrobwkFMnn
9yhSW5Tg0Wyl0sg8almCMlxuS7BSeqQShG1N+CF1g7alenlSfFpAsMZ7dASxptpzYUF5+G4NlnC8
d4owFBqplaDjlB5qAyzUuYB7K/5U8aPGsiIliHiEdNKndH6KHcHO+hAQPLDixDK34jQe83C+s8oQ
OhbcYvGeKaNINbrwqVijpFgbdaSDA+UafiOJ1jk01NFQEpaBQ90LzmKjkbs7ONH214F/hv8MH+/H
ouEtV5Z7ahyx1Q9+sfp6tllf8c15Cb/uHErWSw5klC2KRwCPvtjboKDye0XimhWTaUfg0Lc6qufD
JeeLGK45drBMImLn+qyudQ9taE7GnSaXpDtnuvby9H+GYQe6+nm5WV98WV+ef4N3da6eBx86ILT1
+ARyNNcojxHROpZwS/DkRn4x17s8ZPChV3uar3p58EPvqttGtxiU5uw0fMJh46daKJVptJ65035a
7O5lwzIJOh7xuJQpiNrjIW2EF0fdVU2ck27qFyNWKfrMMU65I3KvaGdmAy9YKPwrcEdwlZsUnkDA
J3agMu1N3Lvh9YFlUr74z6y+7fLbLt8H61fwGXgPN3DqNfgHh3IRuA=='''))

where, _sendfile = find_library('c'), None
if where is not None:
    libc = CDLL(where, use_errno=True)
    if hasattr(libc, 'sendfile'):
        if 'linux' in sys.platform:
            _sendfile = libc.sendfile
            _sendfile.argtypes = (c_int, c_int, POINTER(c_off_t), c_size_t)
            _sendfile.restype = c_ssize_t
            socket_sendfile = socket_sendfile % {
                'initial': '''\
    pos = c_off_t(offset)
    pos_ = pointer(pos)''', 'sendfile': '''\
                    result = _sendfile(out_fd, in_fd, pos_, left)''',
                'increase': '''\
                    offset += result
                    left -= result
                    pos.value = offset''' }
        elif 'darwin' == sys.platform:
            _sendfile = libc.sendfile
            _sendfile.argtypes = (
                c_int, c_int, c_off_t, POINTER(c_off_t), c_void_p, c_int)
            _sendfile.restype = c_int
            socket_sendfile = socket_sendfile % {
                'initial': '''\
    num_sent = c_off_t(count)
    num_sent_ = pointer(num_sent)''', 'sendfile': '''\
                    result = _sendfile(in_fd, out_fd, offset, num_sent_, No\
ne, 0)''', 'increase': '''\
                    offset += num_sent.value
                    left -= num_sent.value
                    num_sent.value = left''' }
        elif sys.platform in ('freebsd', 'dragonfly'):
            _sendfile = libc.sendfile
            _sendfile.argtypes = (c_int, c_int, c_off_t, c_size_t,
                    c_void_p, POINTER(c_off_t), c_int)
            _sendfile.restype = c_ssize_t
            socket_sendfile = socket_sendfile % {
                'initial': '''\
    num_sent = c_off_t()
    num_sent_ = pointer(num_sent)''', 'sendfile': '''\
                    result = _sendfile(in_fd, out_fd, offset, left, None, n\
um_sent_, 0)''', 'increase': '''\
                    offset += num_sent.value
                    left -= num_sent.value''' }

import _socket
from errno import *
from weakref import ref
from cStringIO import StringIO
from traceback import print_exc
from greenlet import greenlet, getcurrent
from _socket import error, socket as realsocket, timeout as realtimeout

class socket:
    exec ('''def __init__(self, family=_socket.AF_INET, type_=_socket.SOCK_\
STREAM, proto=0):
    _sock = realsocket(family, type_, proto)
    _sock.setblocking(0)
''' + socket_init)
    exec (socket_file % {
        'recv_left': '''\
            data = self._sock.recv(left)''',
        'recv_8192': '''\
            data = self._sock.recv(8192)''',
        'recv_size': '''\
        return self._sock.recv(size)''',
        'send_data': '''\
            return self._sock.send(data)''',
        'send_8192': '''\
                        pos += self._sock.send(data[pos:pos+8192])''',
        'close': '' })
    if _sendfile is not None:
        exec (socket_sendfile)

    def connect(self, addr, timeout):
        errno = self._sock.connect_ex(addr)
        if EALREADY == errno or EINPROGRESS == errno or \
           EISCONN  == errno or EWOULDBLOCK == errno:
            id_ = c_uint(id(self)).value
            if id_ not in objects:
                raise error(EPIPE, 'Broken pipe')
            self.x_wait(timeout)
            errno = self._sock.connect_ex(addr)
        if 0 == errno or EISCONN == errno:
            return
        raise error(errno, strerror(errno))

class socket_wrapper:
    exec ('''def __init__(self, _sock):
''' + socket_init)
    exec (socket_file % {
        'recv_left': '''\
            data = self._sock.recv(left)''',
        'recv_8192': '''\
            data = self._sock.recv(8192)''',
        'recv_size': '''\
        return self._sock.recv(size)''',
        'send_data': '''\
            return self._sock.send(data)''',
        'send_8192': '''\
                        pos += self._sock.send(data[pos:pos+8192])''',
        'close': '' })
    if _sendfile is not None:
        exec (socket_sendfile)

class csocket(Structure):
    _fields_ = _fields_('''\
r_io:ev_io;r_timer:ev_timer;w_io:ev_io;w_timer:ev_timer;x_io:ev_io;x_timer:\
ev_timer''')

class server_wrapper:
    def __init__(self, _sock, handler):
        self.handler = handler
        self._sock = _sock
        self.cserver = cserver1 = ev_io()
        memmove(byref(cserver1), cserver0, sizeof_ev_io)
        cserver1.fd = _sock.fileno()
        id_ = c_uint(id(self)).value
        cserver1.data = id_
        objects[id_] = ref(self)

    def __del__(self):
        if self.cserver.active:
            ev_io_stop(EV_DEFAULT_UC, byref(self.cserver))
        id_ = c_uint(id(self)).value
        del objects[id_]

    def fileno(self):
        return self._sock.fileno()

    def close(self):
        if self.cserver.active:
            ev_io_stop(EV_DEFAULT_UC, byref(self.cserver))

    def start(self):
        if not self.cserver.active:
            ev_io_start(EV_DEFAULT_UC, byref(self.cserver))

    def stop(self):
        if self.cserver.active:
            ev_io_stop(EV_DEFAULT_UC, byref(self.cserver))

    def serve_forever(self, flags=0):
        self.start()
        run(flags)

    def exit(self, how=EVBREAK_ALL):
        self.stop()
        break_(how)

def server_r_io_cb(l, w, e):
    id_ = w.contents.data
    server1 = objects[id_]()
    _sock, addr = server1._sock.accept()
    _sock.setblocking(0)
    socket1 = socket_wrapper(_sock)
    goto_ = greenlet(server1.handler)
    try:
        goto_.switch(socket1, addr)
    except:
        print_exc(file=sys.stderr)

def get_cserver0():
    cserver0 = ev_io()
    memset(byref(cserver0), 0, sizeof_ev_io)
    cserver0.events = EV__IOFDSET | EV_READ
    cserver0.cb = c_server_r_io_cb
    buf = create_string_buffer(sizeof_ev_io)
    memmove(buf, byref(cserver0), sizeof_ev_io)
    return buf

def get_csocket0():
    csocket0 = csocket()
    memset(byref(csocket0), 0, sizeof_csocket)
    for type_ in 'r_io w_io x_io r_timer w_timer x_timer'.split():
        exec ('csocket0.%s.cb = c_socket_%s_cb' % (type_, type_))
    csocket0.r_io.events = EV__IOFDSET | EV_READ
    csocket0.w_io.events = EV__IOFDSET | EV_WRITE
    csocket0.x_io.events = EV__IOFDSET | EV_WRITE | EV_READ
    csocket0.r_timer.repeat = csocket0.w_timer.repeat = \
    csocket0.x_timer.repeat = 0.
    buf = create_string_buffer(sizeof_csocket)
    memmove(buf, byref(csocket0), sizeof_csocket)
    return buf

class Timeout(realtimeout):
    num_sent = 0

for type_, desc in [('r', 'read'), ('w', 'write'), ('x', 'connect')]:
    exec('''def socket_%(type)s_io_cb(l, w, e):
    id_ = w.contents.data
    socket1 = objects[id_]()
    try:
        socket1.%(type)s_co.switch()
    except:
        print_exc(file=sys.stderr)
def socket_%(type)s_timer_cb(l, w, e):
    id_ = w.contents.data
    socket1 = objects[id_]()
    try:
        socket1.%(type)s_co.throw(Timeout, Timeout(ETIMEDOUT, '%(desc)s tim\
ed out'))
    except:
        print_exc(file=sys.stderr)
c_socket_%(type)s_io_cb = find_cb(ev_io)(socket_%(type)s_io_cb)
c_socket_%(type)s_timer_cb = find_cb(ev_timer)(socket_%(type)s_timer_cb)   \
''' % {'type': type_, 'desc': desc})

sizeof_csocket = sizeof(csocket)
csocket0 = get_csocket0()

c_server_r_io_cb = find_cb(ev_io)(server_r_io_cb)
sizeof_ev_io = sizeof(ev_io)
cserver0 = get_cserver0()
objects = {}

############################################################################

class pipe_wrapper:
    exec('''def __init__(self, _sock):
    self._fileno = _sock.fileno()
''' + socket_init)
    exec (socket_file % {
        'recv_left': '''\
            if -1 == self._fileno:
                raise error(EBADF, 'Bad file descriptor')
            data = os_read(self._fileno, left)''',
        'recv_8192': '''\
            if -1 == self._fileno:
                raise error(EBADF, 'Bad file descriptor')
            data = os_read(self._fileno, 8192)''',
        'recv_size': '''\
        if -1 == self._fileno:
            raise error(EBADF, 'Bad file descriptor')
        return os_read(self._fileno, size)''',
        'send_data': '''\
            if -1 == self._fileno:
                raise error(EBADF, 'Bad file descriptor')
            return os_write(self._fileno, data)''',
        'send_8192': '''\
                        if -1 == self._fileno:
                            raise error(EBADF, 'Bad file descriptor')
                        pos += os_write(self._fileno, data[pos:pos+8192])  \
        ''', 'close': '\n    self._fileno = -1' })

    def fileno(self):
        fd = self._fileno
        if -1 == fd:
            raise error(EBADF, 'Bad file descriptor')
        return fd

def popen3(*args):
    result = apply_(Popen, args, {'stdin': PIPE,
        'stdout': PIPE, 'stderr': PIPE})
    if fcntl(result.stdin.fileno(), F_SETFL, O_NONBLOCK) != 0:
        errno = get_errno()
        raise OSError(errno, strerror(errno))
    if fcntl(result.stdout.fileno(), F_SETFL, O_NONBLOCK) != 0:
        errno = get_errno()
        raise OSError(errno, strerror(errno))
    if fcntl(result.stderr.fileno(), F_SETFL, O_NONBLOCK) != 0:
        errno = get_errno()
        raise OSError(errno, strerror(errno))
    stdin = pipe_wrapper(result.stdin)
    stdout = pipe_wrapper(result.stdout)
    stderr = pipe_wrapper(result.stderr)
    return stdin, stdout, stderr

from fcntl import fcntl, F_SETFL
from subprocess import Popen, PIPE
from os import strerror, O_NONBLOCK, read as os_read, write as os_write

############################################################################

class tcpserver(server_wrapper):
    def __init__(self, address, handler):
        attrs = bind(address, _socket.SOCK_STREAM)
        self.__dict__.update(attrs)
        server_wrapper.__init__(self, self._sock, handler)

    def start(self, request_queue_size=-1):
        if not self.activated:
            if -1 == request_queue_size:
                self._sock.listen(self.request_queue_size)
            else:
                self._sock.listen(request_queue_size)
            self.activated = 1
        server_wrapper.start(self)

    request_queue_size = 8192
    activated = 0

def bind(address, sock_type):
    family, addr = addrinfo(address)
    if isinstance(addr, int):
        _sock = _socket.fromfd(addr, family, sock_type)
        _sock.setblocking(0)
        activated = 1
    else:
        _sock = _socket.socket(family, sock_type)
        _sock.setblocking(0)
        activated = 0
        if _socket.AF_INET6 == family and '::' == addr[0]:
            _sock.setsockopt(_socket.IPPROTO_IPV6, _socket.IPV6_V6ONLY, 0)
        _sock.setsockopt(_socket.SOL_SOCKET, _socket.SO_REUSEADDR, 1)
        _sock.bind(addr)
    server_address = _sock.getsockname()
    if isinstance(server_address, tuple):
        host, server_port = server_address
        server_name = getfqdn(host)
    else:
        server_port = server_name = None
    return {'server_address': server_address,
            'server_name'   : server_name,
            'server_port'   : server_port,
            'sock_family'   : family,
            'sock_type'     : sock_type,
            'activated'     : activated,
            '_sock'         : _sock}

def addrinfo(address):
    if isinstance(address, str):
        _ = is_ipv4_with_port(address)
        if _:
            host, port = _.groups()
            return _socket.AF_INET , (host, int(port))
        _ = is_ipv6_with_port(address)
        if _:
            host, port = _.groups()
            return _socket.AF_INET6, (host, int(port))
        _ = is_domain_with_port(address)
        if _:
            host, port = _.groups()
            return _socket.AF_INET , (host, int(port))
        raise ValueError(address)
    family, addr = address
    if _socket.AF_INET == family:
        if isinstance(addr, tuple):
            host, port = addr
            port = int(port)
            if not ((is_ipv4  (host)   or \
                     is_domain(host)) and \
                  0 <= port < 65536):
                raise ValueError(address)
            return _socket.AF_INET, (host, port)
        else:
            return _socket.AF_INET,  addr
    if _socket.AF_INET6 == family:
        if isinstance(addr, tuple):
            host, port = addr
            port = int(port)
            if not ((is_ipv6  (host)   or \
                     is_domain(host)) and \
                  0 <= port < 65536):
                raise ValueError(address)
            return _socket.AF_INET6, (host, port)
        else:
            return _socket.AF_INET6,  addr
        if _socket.AF_UNIX == family:
            if isinstance(addr_0, int):
                return _socket.AF_UNIX, addr
            elif isinstance(addr, str):
                return _socket.AF_UNIX, addr
            else:
                raise ValueError(address)
        raise ValueError(address)

import re
from socket import getfqdn

port = (
r'6553[0-5]|655[0-2]\d|65[0-4]\d{2}|6[0-4]\d{3}|[1-5]\d{4}|[1-9]\d{0,3}|0')
ipv4 = (r'(?:25[0-4]|2[0-4]\d|1\d\d|[1-9]?\d)(?:\.(?:25[0-4]|2[0-4]\d|1\d\d'
r'|[1-9]?\d)){3}')
ipv6 = (
r'(?!.*::.*::)(?:(?!:)|:(?=:))(?:[0-9a-f]{0,4}(?:(?<=::)|(?<!::):)){6}(?:[0'
r'-9a-f]{0,4}(?:(?<=::)|(?<!::):)[0-9a-f]{0,4}(?:(?<=::)|(?<!:)|(?<=:)(?<!:'
':):))')
domain = (r'(?:[a-z0-9](?:[a-z0-9\-]{0,61}[a-z0-9])?\.)+[a-z]{2,6}')
is_ipv4 = re.compile(r'^\s*(%s)\s*$' % ipv4).match
is_ipv6 = re.compile(r'^\s*(%s)\s*$' % ipv6).match
is_domain = re.compile(r'^\s*(%s)\s*$' % domain).match
is_ipv4_with_port   = re.compile(
    r'^\s*(%s)\s*:\s*(%s)\s*$' % (ipv4, port)).match
is_ipv6_with_port   = re.compile(
    r'^\s*\[\s*(%s)\s*]\s*:\s*(%s)\s*$' % (ipv6, port)).match
is_domain_with_port = re.compile(
    r'^\s*(%s)\s*:\s*(%s)\s*$' % (domain, port)).match

############################################################################

class apply_frame:
    def __init__(self, func, args=(), kwargs={}):
        self.back_ = getcurrent()
        self.func = func
        self.args = args
        self.kwargs = kwargs

    result = exception = None

def apply_(func, args=(), kwargs={}, timeout=-1):
    back_ = getcurrent()
    id_ = c_uint(id(back_)).value
    frame1 = apply_frame(func, args, kwargs)
    objects[id_] = ref(frame1)
    try:
        req = eio_custom(c_execute, 0, c_apply_cb, id_)
        contents = req.contents
        back_.parent.switch()
        if 0 == contents.result:
            return frame1.result
        raise frame1.exception
    finally:
        del objects[id_]

def apply_cb(req):
    id_ = req.contents.data
    try:
        objects[id_]().back_.switch()
    except:
        print_exc(file=sys.stderr)
    return 0

def execute(req):
    contents = req.contents
    id_ = contents.data
    frame1 = objects[id_]()
    try:
        result = frame1.func(*frame1.args, **frame1.kwargs)
    except BaseException as e:
        frame1.exception = e
        contents.result = -1
    except:
        frame1.exception = RuntimeError('unknow error')
        contents.result = -1
    else:
        frame1.result = result
    return 0

c_apply_cb = eio_cb(apply_cb)
c_execute = eio_custom.argtypes[0](execute)

############################################################################

for type_, timer0 in [('', 'timer00'), ('_raise', 'timer01')]:
    for name, args, func in [
        ('switch', 'args=()', 'goto_.switch(*args)'),
        ('throw' , 'args=()', 'goto_.throw (*args)')]:
        exec zlib.decompress(base64.decodestring('''\
eNqtU7tOwzAU3fsVXiLZUhXBisSAoEyMlAVVlutcV4bEruLboPD1+NHm1ZaqCA+JY5/7OidHlsI5
YuCLo66g5hk1ogLmMort1r/vZsSvAhThXBuNnFMHpZqTtZCfnKXrsMJpHnOQexLft34DTcpLWQes
oKpsA3Td1qBoQrI5ydL2hrk5cfobrEqRfWCC5oVA4TPHerrgfpueku+0QaoLmlpjeSPKHXThdv0B
Et27R688PBRPwMGEBZT7AQeT+cMu+FB11d1qNRg9FxJ1A31sWAcOuEO7pYs3/rR4fli+vPLlo6cx
stBnYMN2pCjLjvCNRcs9NyCtKVwgTNQbx9ygUy8l1EiMxeOeJjQeGIxfU4oFxutYaHZiDFHj6Tn2
ag40q9sxGRlVOyNZn1Zp46dsr6ZsVCrQFaET6f5fnFDptFPS33RRp3PW+JMtzuk1tsplf/zujauV
H6k+UvxI7WuVnhoydPwDepluOQ=='''
)) % {'args': args, 'type': type_, 'func': func,
      'name': name, 'timer0': timer0 }

for name, args, func in [
    ('switch', 'args=()', 'goto_.switch(*args)'),
    ('throw' , 'args=()', 'goto_.throw (*args)')]:
    exec zlib.decompress(base64.decodestring('''\
eNqtU8FOxCAUvPsVXDaBpGn0auLB6Hry6HoxmxdKHxuUgilsTf16ga6l3V01TeRQEpjHmzczFZo7
Rwx+gKo1wooa3iBz1xckrBolAVBGeQDqUMuCVFy8ARuu44qnZSwlNyRuV2HHLj1G2YhqsGlsh7Tq
W5Q04ViR8JcFceoTrUwluSJhypp7Hh48NIHUI34F7JXx4SE68GFlx/Uex2pbvaLw7iWgtwEemw7A
yVg16sNUk3HC4Vj83XWbSck8b8mFVx3m0rgOk4Pz9p2un+F+/XC7eXyCzV1QLs0+1rMpF8G1HiXe
WW+hICvK251jbsIuWIWtJ8b6Ex5z4bJmOt9kcrz159kNzmQXfNvPB1xRuTeCufFQKhO490tlmDaK
EiTkkRf/rHZsM8v4EImf9D4f5mVBnoX47+T+ntqF9s2sm9l2Ytkyu45/k8j2C9btQSU='''
)) % {'name': name, 'args': args, 'func': func }

def idle():
    back_ = getcurrent()
    idle_switch(back_, back_.parent)

def sleep(seconds):
    back_ = getcurrent()
    timer_switch(back_, back_.parent, seconds)

def scheduler_cb(l, w, e):
    id_ = w.contents.data
    back_ = objects[id_]()
    try:
        back_.switch()
    except:
        print_exc(file=sys.stderr)

def scheduler_throw_cb(l, w, e):
    id_ = w.contents.data
    back_ = objects[id_]()
    try:
        back_.throw(Timeout, Timeout(ETIMEDOUT, 'operation timed out'))
    except:
        print_exc(file=sys.stderr)

def get_timer0(c_timer_cb):
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

sizeof_timer = sizeof(ev_timer)
c_timer_cb00 = find_cb(ev_timer)(scheduler_cb)
c_timer_cb01 = find_cb(ev_timer)(scheduler_throw_cb)
timer00 = get_timer0(c_timer_cb00)
timer01 = get_timer0(c_timer_cb01)
if hasattr(libev, 'ev_idle_start'):
    sizeof_idle = sizeof(ev_idle)
    c_idle_cb = find_cb(ev_idle)(scheduler_cb)
    idle0 = get_idle0()

############################################################################

class httpfile:
    def __init__(self, s, reuse, **environ):
        tstamp = time()
        while 1:
            data = s.readline(4096, 20.)
            if '' == data:
                raise GreenletExit
            _ = is_first(data)
            if _ is None:
                raise ValueError('invalid http header %r' % data)
            method, uri, version = _.groups()
            if method:
                break
            if time() - tstamp > 20.:
                raise Timeout(ETIMEDOUT, 'read time out')
        self.bgenv = environ
        environ = dict(environ)
        data = s.readline(2048, 10.)
        size = len(data)
        while 1:
            _ = is_header(data)
            if _ is None:
                if '\r\n' == data or '\n' == data:
                    break
                raise ValueError('invalid http header %r' % data)
            key, value = _.groups()
            environ['HTTP_' + key.upper().replace('-', '_')] = value
            data  = s.readline(2048, 10.)
            size += len(data)
            if size > 8192:
                raise ValueError('request header is too large')
        if 'POST' == method or 'HTTP_CONTENT_LENGTH' in environ:
            environ['CONTENT_LENGTH'] = environ['HTTP_CONTENT_LENGTH']
            left = environ['HTTP_CONTENT_LENGTH'].strip()
            if len(left) > 10:
                raise ValueError('content-length %r is too large' % left)
            left = int(left)
            if left < 0 or left > 0xffffffff:
                raise ValueError('invalid content-length %r' % left)
            self.left = left
        else:
            self.left = 0
        p = uri.find('?')
        if p != -1:
            environ['PATH_INFO'] = '%2F'.join(
                unquote(x) for x in quoted_slash_split(uri[:p]))
            environ['QUERY_STRING'] = uri[p+1:]
        else:
            environ['PATH_INFO'] = '%2F'.join(
                unquote(x) for x in quoted_slash_split(uri))
            environ['QUERY_STRING'] = ''
        environ['SCRIPT_NAME'] = ''
        environ['REQUEST_URI'] = uri
        environ['REQUEST_METHOD' ] = method
        environ['SERVER_PROTOCOL'] = version
        environ.setdefault('CONTENT_TYPE',
        environ.setdefault('HTTP_CONTENT_TYPE', ''))
        self.closed = 0
        self.socket = s
        self.reuse = reuse
        self.headers_sent = 0
        self.environ = environ

    def fileno(self):
        return self.socket._sock.fileno()

    def read(self, size, timeout=-1):
        if size > self.left:
            if -1 == timeout:
                timeout = 16. + (self.left >> 10)
            data = self.socket.read(self.left, timeout)
            self.left = 0
            return data
        else:
            if -1 == timeout:
                timeout = 16. + (size >> 10)
            data = self.socket.read(size, timeout)
            self.left -= len(data)
            return data

    def readline(self, size, timeout=-1):
        if size > self.left:
            if -1 == timeout:
                timeout = 16. + (self.left >> 10)
            data = self.socket.readline(self.left, timeout)
        else:
            if -1 == timeout:
                timeout = 16. + (size >> 10)
            data = self.socket.readline(size, timeout)
        self.left -= len(data)
        return data

    def write(self, data, timeout=-1):
        assert self.headers_sent
        data = '%x\r\n%s\r\n' %(len(data), data)
        if -1 == timeout:
            timeout = 16. + (len(data) >> 10)
        self.socket.write(data, timeout)

    def flush(self):
        _sock = self.socket._sock
        _sock.setsockopt(SOL_TCP, TCP_CORK, 0)
        _sock.setsockopt(SOL_TCP, TCP_CORK, 1)

    def start_response(self, status ='200 OK',
        response_headers=[], timeout=-1):
        headers = ['%s: %s' % i for i in response_headers]
        headers.insert(0, '%s %s' % (
            self.environ['SERVER_PROTOCOL'], status))
        headers.append('Transfer-Encoding: chunked')
        headers.append('\r\n')
        headers = '\r\n'.join(headers)
        if -1 == timeout:
            timeout = 16. + (len(headers) >> 10)
        self.socket.write(headers, timeout)
        self.headers_sent = 1

    def close(self, keep_alive=300., timeout=-1):
        if self.closed:
            return
        self.closed = 1
        if 0 == keep_alive:
            return self.socket.close()
        if -1 == timeout:
            timeout = 16.
        if self.headers_sent:
            self.socket.write('0\r\n\r\n', timeout)
        _sock = self.socket._sock
        _sock.setsockopt(SOL_TCP, TCP_CORK, 0)
        _sock.setsockopt(SOL_TCP, TCP_CORK, 1)
        environ = self.environ
        if 'HTTP_KEEP_ALIVE'  in  environ or environ.get(
           'HTTP_CONNECTION', '').lower() == 'keep-alive':
            seconds = environ.get('HTTP_KEEP_ALIVE', '300')
            if is_seconds(seconds):
                seconds = float(seconds)
                if -1 == keep_alive or keep_alive > seconds:
                    keep_alive = seconds
                back_ = getcurrent()
                goto_ = greenlet(httpreuse, back_.parent)
                idle_switch(back_, goto_, (
                    self.socket, self.reuse, self.bgenv, keep_alive))
            else:
                return self.socket.close()
        else:
            return self.socket.close()

def httpreuse(s, reuse, bgenv, keep_alive):
    s.r_wait(keep_alive)
    try:
        http = httpfile(s, reuse, **bgenv)
    except:
        return
    reuse(http)

def httphandler(handler, **environ):
    def wrapper(s, addr):
        s._sock.setsockopt(SOL_TCP, TCP_CORK, 1)
        try:
            http = httpfile(s, handler,
                REMOTE_ADDR=addr[0],
                REMOTE_PORT=addr[1], **environ)
        except:
            return
        handler(http)
    return wrapper

def httphandler_unix(handler, **environ):
    def wrapper(s, addr):
        s._sock.setsockopt(SOL_TCP, TCP_CORK, 1)
        try:
            http = httpfile(s, handler, **environ)
        except:
            return
        handler(http)
    return wrapper

class httpserver(tcpserver):
    def __init__(self, address, handler, **environ):
        tcpserver.__init__(self, address, None)
        if hasattr(_socket, 'AF_UNIX') and \
           _socket.AF_UNIX == self.sock_family:
            self.handler = httphandler_unix(handler, **environ)
        else:
            self.handler = httphandler(handler, **environ)
        self._sock.setsockopt(SOL_TCP, TCP_DEFER_ACCEPT, 1)
        environ.setdefault('SERVER_NAME', self.server_name)
        environ.setdefault('SERVER_PORT', self.server_port)

from time import time
from urllib import unquote
from greenlet import GreenletExit
from _socket import SOL_TCP, TCP_CORK, TCP_DEFER_ACCEPT

is_seconds = re.compile((r'^\s*[1-9][0-9]{0,6}\s*$')).match
is_header = re.compile(
    r'^[\s\t]*([^\r\n:]+)[\s\t]*:[\s\t]*([^\r\n]+)[\s\t]*\r?\n$').match
is_first = re.compile((r'^(?:[ \t]*(\w+)[ \t]+([^\r\n]+)[ \t]+(HTTP/[01]\.['
    r'0-9])[ \t]*|[ \t]*)\r?\n$'), re.I).match

quoted_slash_split = re.compile('(?i)%2F').split
RESPONSES = dict((int(i.split(None, 1)[0]), i) for i in ('''\
100 Continue,101 Switching Protocols,200 OK,201 Created,202 Accepted,203 No\
n-Authoritative Information,204 No Content,205 Reset Content,206 Partial Co\
ntent,300 Multiple Choices,301 Moved Permanently,302 Found,303 See Other,30\
4 Not Modified,305 Use Proxy,307 Temporary Redirect,400 Bad Request,401 Una\
uthorized,402 Payment Required,403 Forbidden,404 Not Found,405 Method Not A\
llowed,406 Not Acceptable,407 Proxy Authentication Required,408 Request Tim\
eout,409 Conflict,410 Gone,411 Length Required,412 Precondition Failed,413 \
Request Entity Too Large,414 Request-URI Too Long,415 Unsupported Media Typ\
e,416 Requested Range Not Satisfiable,417 Expectation Failed,500 Internal S\
erver Error,501 Not Implemented,502 Bad Gateway,503 Service Unavailable,504\
 Gateway Timeout,505 HTTP Version Not Supported''').split(','))

############################################################################

exec ('''\
del __USE_FILE_OFFSET64,args,declare,desc,domain,func,get_cserver0,get_csoc\
ket0,get_idle0,get_timer0,ipv4,ipv6,name,port,re,timer0,type_,where''')
