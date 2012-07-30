def cpu_count():
    import os, sys
    if sys.platform == 'win32':
        return int(os.environ['NUMBER_OF_PROCESSORS'])
    elif sys.platform == 'darwin':
        return int(os.popen('sysctl -n hw.ncpu').read())
    else:
        return os.sysconf('SC_NPROCESSORS_ONLN')

def setuid(user):
    import os, pwd
    try:
        uid = int(user)
    except ValueError:
        try:
            pwrec = pwd.getpwnam(user)
        except KeyError:
            raise OSError('username %r not found' % user)
        uid = pwrec[2]
    else:
        try:
            pwrec = pwd.getpwuid(uid)
        except KeyError:
            raise OSError, 'uid %r not found' % user
    euid = os.geteuid()
    if euid != 0 and euid != uid:
        raise OSError, 'only root can change users'
    os.setgid(pwrec[3])
    os.setuid(uid)

def setprocname(procname, env='__PROCNAME', format='%s '):
    import os, sys
    if not os.environ.has_key(env):
        environ = dict(os.environ)
        environ[env] = procname
        os.execlpe(*([sys.executable, format % procname] + \
                      sys.argv + [environ]))
    import ctypes, ctypes.util
    libc = ctypes.CDLL(ctypes.util.find_library('c'))
    procname = ctypes.create_string_buffer(procname)
    platform = sys.platform.upper()
    if 'LINUX' in platform:
        libc.prctl(15, procname, 0, 0, 0)
    elif 'BSD' in platform:
        libc.setproctitle(procname)

def dummy():
    import os, sys
    if hasattr(os, 'devnull') and os.devnull:
        stdin  = open(os.devnull, 'r')
        stdout = open(os.devnull, 'a+')
        stderr = open(os.devnull, 'a+', 0)
        os.dup2(stdin.fileno(), sys.stdin.fileno())
        os.dup2(stdout.fileno(), sys.stdout.fileno())
        os.dup2(stderr.fileno(), sys.stderr.fileno())
        sys.stdin  = sys.__stdin__  = stdin
        sys.stdout = sys.__stdout__ = stdout
        sys.stderr = sys.__stderr__ = stderr
    else:
        sys.stdin  = sys.__stdin__  = nul
        sys.stdout = sys.__stdout__ = nul
        sys.stderr = sys.__stderr__ = nul

def daemonize(program, *args, **kwargs):
    import os, signal, sys
    def sigchild(sig, frame):
        try:
            pid, sts = os.waitpid(-1, os.WNOHANG)
        except OSError:
            return
    signal.signal(signal.SIGCHLD, sigchild)
    pid = os.fork()
    if pid != 0:
        if  kwargs.get('exit' , True):
            os._exit(0)
        return pid
    chdir = kwargs.get('chdir')
    if chdir:
        os.chdir(chdir)
    os.setsid()
    os.umask(kwargs.get('umask', 022))
    dummy()
    try:
        for i in xrange(3, 100):
            try:
                os.close(i)
            except OSError:
                pass
        os.execv(sys.executable,
          tuple([sys.executable, program] + list(args)))
    finally:
        os._exit(127)

class nul:
    write = staticmethod(lambda s: None)
    flush = staticmethod(lambda  : None)
    read  = staticmethod(lambda n: ''  )
