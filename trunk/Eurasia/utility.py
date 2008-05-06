def setprocname(procname, libc='/lib/libc.so.6', env='__PROCNAME'):
	import os, sys
	if not os.environ.has_key(env):
		kw = dict(os.environ); kw[env] = procname
		os.execlpe(*([sys.executable, procname] + sys.argv + [kw]))

	import dl
	libc = dl.open(libc)

	platform = sys.platform.upper()
	if 'LINUX' in platform:
		libc.call('prctl', 15, '%s\0' %procname, 0, 0, 0)
	elif 'BSD' in platform:
		libc.call('setproctitle', '%s\0' %procname)
