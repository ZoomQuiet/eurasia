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
	devnull = hasattr(os, 'devnull') and os.devnull or '/dev/null'
	stdin  = open(devnull, 'r')
	stdout = open(devnull, 'a+')
	stderr = open(devnull, 'a+', 0)
	os.dup2(stdin.fileno() , sys.stdin.fileno() )
	os.dup2(stdout.fileno(), sys.stdout.fileno())
	os.dup2(stderr.fileno(), sys.stderr.fileno())
	sys.stdin  = sys.__stdin__  = stdin
	sys.stdout = sys.__stdout__ = stdout
	sys.stderr = sys.__stderr__ = stderr

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
