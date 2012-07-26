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

class c_statvfs(Structure):
    pass

c_statvfs_p = POINTER(c_statvfs)
c_statvfs._fields_ = [
    ('f_bsize'   , c_ulong   ), ('f_frsize'  , c_ulong  ),
    ('f_blocks'  , c_ulong   ), ('f_bfree'   , c_ulong  ),
    ('f_bavail'  , c_ulong   ), ('f_files'   , c_ulong  ),
    ('f_ffree'   , c_ulong   ), ('f_favail'  , c_ulong  ),
    ('f_fsid'    , c_ulong   ), ('f_flag'    , c_ulong  ),
    ('f_namemax' , c_ulong   )]

class c_stat(Structure):
    pass

c_stat_p = POINTER(c_stat)
c_stat._fields_ = [
    ('st_dev'    , c_uint    ), ('st_ino'      , c_ulong),
    ('st_nlink'  , c_uint    ), ('pad1'        , c_uint ),
    ('st_mode'   , c_int     ), ('st_uid'      , c_uint ),
    ('st_gid'    , c_uint    ), ('pad0'        , c_int  ),
    ('st_rdev'   , c_uint    ), ('st_size'     , c_ulong),
    ('st_blksize', c_long    ), ('st_blocks'   , c_long ),
    ('st_atime'  , c_long    ), ('st_atimensec', c_ulong),
    ('st_mtime'  , c_long    ), ('st_mtimensec', c_ulong),
    ('st_ctime'  , c_long    ), ('st_ctimensec', c_ulong)]
