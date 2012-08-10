def open(path, flag, mode=0777, timeout=-1):
    return apply(os.open, (path, flag, mode), {}, timeout)

def chown(path, uid, gid, timeout=-1):
    return apply(os.chown, (path, uid, gid), {}, timeout)

def chmod(path, mode, timeout=-1):
    return apply(os.chmod, (path, mode), {}, timeout)

def mkdir(path, mode=0777, timeout=-1):
    return apply(os.mkdir, (path, mode), {}, timeout)

def rmdir(path, timeout=-1):
    return apply(os.rmdir, (path, ), {}, timeout)

def unlink(path, timeout=-1):
    return apply(os.unlink, (path, ), {}, timeout)

def utime(path, utim=None, timeout=-1):
    return apply(os.utime, (path, utim), {}, timeout)

def mknod(path, mode=0600, dev=0, timeout=-1):
    return apply(os.mknod, (path, mode, dev), {}, timeout)

def link(path, new_path, timeout=-1):
    return apply(os.link, (path, new_path), {}, timeout)

def symlink(path, new_path, timeout=-1):
    return apply(os.symlink, (path, new_path), {}, timeout)

def rename(path, new_path, timeout=-1):
    return apply(os.rename, (path, new_path), {}, timeout)

def close(fd, timeout=-1):
    return apply(os.close, (fd, ), {}, timeout)

def fsync(fildes, timeout=-1):
    return apply(os.fsync, (), {}, timeout)

def fdatasync(fildes, timeout=-1):
    return apply(os.fdatasync, (), {}, timeout)

def ftruncate(fd, size, timeout=-1):
    return apply(os.ftruncate, (fd, size), {}, timeout)

def fchmod(fd, mode, timeout=-1):
    return apply(os.fchmod, (fd, mode), {}, timeout)

def fchown(fd, uid, gid, timeout=-1):
    return apply(os.fchown, (fd, uid, gid), {}, timeout)

def dup2(fd, fd2, timeout=-1):
    return apply(os.dup2, (fd, fd2), {}, timeout)

def read(fd, size, timeout=-1):
    return apply(os.read, (fd, size), {}, timeout)

def write(fd, buf, timeout=-1):
    return apply(os.write, (fd, buf), {}, timeout)

def readlink(path, timeout=-1):
    return apply(os.readlink, (path, ), {}, timeout)

def realpath(path, timeout=-1):
    return apply(posixpath.realpath, (path, ), {}, timeout)

def stat(path, timeout=-1):
    return apply(os.stat, (path, ), {}, timeout)

def lstat(path, timeout=-1):
    return apply(os.lstat, (path, ), {}, timeout)

def fstat(fd, timeout=-1):
    return apply(os.fstat, (fd, ), {}, timeout)

def statvfs(path, timeout=-1):
    return apply(os.statvfs, (path, ), {}, timeout)

def fstatvfs(fd, timeout=-1):
    return apply(os.fstatvfs, (fd, ), {}, timeout)

def listdir(path, timeout=-1):
    return apply(os.listdir, (path, ), {}, timeout)

def exists(path, timeout=-1):
    return apply(posixpath.exists, (path, ), {}, timeout)

def isfile(path, timeout=-1):
    return apply(posixpath.isfile, (path, ), {}, timeout)

def isdir(path, timeout=-1):
    return apply(posixpath.isdir, (path, ), {}, timeout)

def islink(path, timeout=-1):
    return apply(posixpath.islink, (path, ), {}, timeout)

def ismount(path, timeout=-1):
    return apply(posixpath.ismount, (path, ), {}, timeout)

def samefile(f1, f2):
    return apply(posixpath.samefile, (f1, f2), {}, timeout)

import os, posixpath
from pool import apply
try:
    from pyeio import eio_sendfile_sync
except ImportError:
    def eio_sendfile_sync(*args):
        raise NotImplementedError

def sendfile(out_fd, in_fd, in_offset, size, timeout=-1):
    return apply(eio_sendfile_sync,
        (out_fd, in_fd, in_offset, size), {}, timeout)
