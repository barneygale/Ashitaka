class Message:
	def __init__(self, ident, *args):
		self.ident = ident
		if args:
			self.data = args[0]
