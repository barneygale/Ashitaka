import re
import Queue
import threading
import time
import packet_decoder
import codecs
class Plugin_Chat_Terminal:
	def __init__(self, session):
		self.interestedPackets = []
		self.interestedMessages = ["chatMessage"]
		session.get_plugin("chat").subscribe(self.read)
		self.session = session
		self.log = codecs.open("unknown_chat.log", "w", "utf-8-sig")

		
	def read(self, ident, data):
		if ident == "unknown":
			self.log.write(data['text']+"\n")
		print ident, data
		#if ident == "unknown":
		#	print data['text']
