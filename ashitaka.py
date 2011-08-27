#!/usr/bin/python
from socks import SOCKSServer
from session import Session_Socket, Session_Bot
import time
import os
import sys
from message import Message
import cProfile
import pstats

class Ashitaka:
	known_session_ids = {}
	current_session_id = {}
	sessions = []
	def __init__(self):
		self.socks = SOCKSServer(self)
		if sys.platform == 'win32':
			self.minecraft_path = os.environ['APPDATA']
		else:
			self.minecraft_path = os.path.expanduser("~")
		self.minecraft_path = os.path.join(self.minecraft_path, ".minecraft")
	
	def get_session_id(self, username, *args):
		if len(args):
			if username not in self.known_session_ids:
				self.known_session_ids[username] = [args[0]]
				self.current_session_id[username] = args[0]
			elif args[0] not in self.known_session_ids[username]:
				self.known_session_ids[username].append(args[0])
				self.current_session_id[username] = args[0]
		return self.current_session_id[username]
	
	def new_session(self, *args):
		if len(args) == 2:
			option = "lastServer:"
			f = file(os.path.join(self.minecraft_path, "options.txt"))
			line = "..."
			while line != "" and not line.startswith(option):
				line = f.readline()
			line = line[len(option):].strip().split("_")
			host = line[0]
			if len(line)>1: port = int(line[1])
			else:           port = 25565
			f.close()
		
			s = Session_Socket(self, host, port, *args)
			self.sessions.append(s)
			s.join()
			return
		if len(args) == 3:
			s = Session_Bot(self, *args)
			self.sessions.append(s)
			return s
				
	def destroy_session(self, session):
		session.stop()
		self.sessions.remove(session)
		#print "Destroyed session..."
		#print "Sessions len: ", len(self.sessions)
	
	def stop(self):
		#print "Ashitaka.stop()"
		#print "Sessions len: ", len(self.sessions)
		for session in self.sessions:
			#session.process_message(Message("keyboardInterrupt"))
			session.process_message(Message("keyboardInterrupt"))
			session.stop()
		#print "Waiting for sessions to die..."
		for session in self.sessions:
			session.join()
		#print "killing socks..."
		self.socks.stop()
def launch():
	app = Ashitaka()
	try:
		while True:
			time.sleep(1000)
	except KeyboardInterrupt:
		app.stop()
if __name__ == "__main__":
	launch()
	#cProfile.run('launch()', 'prof')
	#p = pstats.Stats('prof')
	#p.sort_stats('cumulative').print_stats(100)
