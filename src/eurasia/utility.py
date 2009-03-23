class nul:
	write = staticmethod(lambda s: None)
	flush = staticmethod(lambda  : None)
	read  = staticmethod(lambda n: ''  )

def cpu_count():
	import os, sys
	if sys.platform == 'win32':
		try:
			return int(os.environ['NUMBER_OF_PROCESSORS'])
		except (ValueError, KeyError):
			return 0

	elif sys.platform == 'darwin':
		try:
			return int(os.popen('sysctl -n hw.ncpu').read())
		except ValueError:
			return 0
	else:
		try:
			return os.sysconf('SC_NPROCESSORS_ONLN')
		except (ValueError, OSError, AttributeError):
			return 0

def setuid(user):
	import os, pwd
	try:
		uid = int(user)

	except ValueError:
		try:
			pwrec = pwd.getpwnam(user)
		except KeyError:
			raise OSError, 'username %r not found' % user

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

def setprocname(procname, libc='/lib/libc.so.6', env='__PROCNAME', format='%s:'):
	import os, sys
	if not os.environ.has_key(env):
		kw = dict(os.environ); kw[env] = procname
		os.execlpe(*([sys.executable, format%procname] + sys.argv + [kw]))

	import dl
	libc = dl.open(libc)

	platform = sys.platform.upper()
	if 'LINUX' in platform:
		libc.call('prctl', 15, '%s\0' %procname, 0, 0, 0)
	elif 'BSD' in platform:
		libc.call('setproctitle', '%s\0' %procname)

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

def daemonize(program, *args):
	import os, signal, sys
	def sigchild(sig, frame):
		try: pid, sts = os.waitpid(-1, os.WNOHANG)
		except OSError: return
	signal.signal(signal.SIGCHLD, sigchild)

	pid = os.fork()
	if pid != 0:
		os._exit(0)

	os.setsid(); os.umask(022); dummy()

	try:
		for i in xrange(3, 100):
			try: os.close(i)
			except OSError: pass

		os.execv(sys.executable, tuple(
			[sys.executable, program] + list(args) ) )
	finally:
		os._exit(127)
