from Queue import Queue
from thread import start_new_thread
from stackless import channel, getcurrent

class nonblocking:
	def __init__(self, n=32):
		self.queue = Queue()

		for i in xrange(n):
			start_new_thread(self.pipe, ())

	def __call__(self, func):
		def wrapper(*args, **kw):
			rst = channel()
			self.queue.put((getcurrent(), rst, func, args, kw))

			return rst.receive()

		return wrapper

	def pipe(self):
		while True:
			curr, rst, func, args, kw = self.queue.get()
			try:
				result = func(*args, **kw)

			except Exception, e:
				curr.raise_exception(e)
			else:
				rst.send(result)
