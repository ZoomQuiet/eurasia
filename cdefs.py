from ctypes import *

NULL = c_void_p(None)
c_uchar  = c_ubyte
assert sizeof(c_size_t) == sizeof(c_ulong)
c_ssize_t = c_ulong

def __USE_FILE_OFFSET64():
    import os
    fd = os.popen(('grep CONFIG_LARGEFILE=y '
        '/lib/modules/`uname -r`/build/.config'))
    res = fd.read().strip()
    if not fd.close() and res:
        return True
    return False

if sizeof(c_long) == sizeof(c_longlong):
    c_off_t = c_long
elif __USE_FILE_OFFSET64():
    c_off_t = c_int64
else:
    c_off_t = c_long  # XXX failback
c_mode_t = c_uint
c_sig_atomic_t = c_int
