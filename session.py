import threading
from packet_decoder import *
from plugins.log import Plugin_Log
from plugins.connect import Plugin_Connect
from plugins.chat import Plugin_Chat
from plugins.chat_terminal import Plugin_Chat_Terminal
from plugins.respawn import Plugin_Respawn
import Queue
import time
import select
import socket as libsocket

class Session(threading.Thread):
	def __init__(self, core, host, port):
		threading.Thread.__init__(self)
		#print host
		#print port
		self.core = core
		#self.logger = Plugin_Log(self)
		self.logger = None
		self.plugins = []
		self.plugins.append(("connect", Plugin_Connect(self)))
		self.plugins.append(("chat", Plugin_Chat(self)))
		self.plugins.append(("chat_terminal", Plugin_Chat_Terminal(self)))
		self.plugins.append(("respawn", Plugin_Respawn(self)))
		
		self.plugin_packets = {}
		self.plugin_messages = {}
		for name, p in self.plugins:
			for i in p.interestedPackets:
				if not i in self.plugin_packets: self.plugin_packets[i] = [p]
				else:                            self.plugin_packets[i].append(p)
			for i in p.interestedMessages:
				if not i in self.plugin_messages: self.plugin_messages[i] = [p]
				else:                             self.plugin_messages[i].append(p)
		#print self.plugin_messages
		self.socket = {}
		self.decoder =   {NODE_CLIENT: PacketDecoder(NODE_CLIENT),      NODE_SERVER: PacketDecoder(NODE_SERVER)}
		self.other =     {NODE_CLIENT: NODE_SERVER,                     NODE_SERVER: NODE_CLIENT}
		self.connected = {NODE_CLIENT: False,                           NODE_SERVER: False}
		self.listen =    {NODE_CLIENT: True,                            NODE_SERVER: True}
		self.packet_queue = Queue.Queue()
		
		self.host = host
		self.port = port
		self.running = True
	def get_plugin(self, name):
		for n, p in self.plugins:
			if n == name:
				return p
		raise Exception("Plugin not found: %s" % name)
	def connect(self):
		#print (self.host, self.port)
		server = libsocket.socket(libsocket.AF_INET, libsocket.SOCK_STREAM)
		server.connect((self.host, self.port))
		server.settimeout(0)
		self.socket[NODE_SERVER] = server
		self.connected[NODE_SERVER] = True
	def process_packet(self, packet):
		#TODO: Sort this hack out
		#Always pass through the packet loggers
		if self.logger:
			self.logger.read_packet(packet)
		try:
			for plugin in self.plugin_packets[packet.ident]:
				if not packet.process: break
				plugin.read_packet(packet)
		except KeyError: pass
		return packet
	
	#Process a message
	def process_message(self, message):
		try:
			for plugin in self.plugin_messages[message.ident]:
				plugin.read_message(message)
		except KeyError: pass
	
	#Flush packet queue to sockets
	#TODO: Experiment with buffering

	
	#Generate a packet
	def gen(self, ident, direction, data):
		p = Packet()
		p.ident = ident
		p.data = data
		p.direction = direction
		p.process = False
		p.transmit = True
		self.process_packet(p) #Still need to pass thru logger...
		self.packet_queue.put(p)
	def stop(self):
		#print "session.stop()"
		self.running = False
	def run(self):
		while self.running:
			self.flush()
			rr = select.select(self.socket.values(),[],[], 0)[0]
			#Loop through sockets ready to be read
			for socket in rr:
				#Get node type, e.g. NODE_CLIENT
				
				for n, s in self.socket.items():
					if s == socket:
						node = n
				
				#Read data from the socket
				try:
					data = socket.recv(2048)
				except: 
					print "Can't read..."
					continue
				
				#DISCONNECT
				if data == "":
					#Generate messages
					if self.decoder[node].node == NODE_CLIENT: self.process_message(Message('coreClientDisconnect'))
					if self.decoder[node].node == NODE_SERVER: self.process_message(Message('coreServerDisconnect'))
					self.connected[node] = False
					#Destroy socket
					self.socket[node].close()
					del self.socket[node]
					break
				#CONNECT
				elif not self.connected[node]:
					#Generate messages
					if self.decoder[node].node == NODE_CLIENT: self.process_message(Message('coreClientConnect'))
					if self.decoder[node].node == NODE_SERVER: self.process_message(Message('coreServerConnect'))
					self.connected[node] = True
				
				#Append data
				self.decoder[node].buff += data
				
				#Read packets
				packet = self.decoder[node].read_packet()
				while packet:
					packet.transmit = self.listen[node]
					self.process_packet(packet)
					if packet.transmit:
						self.packet_queue.put(packet)
					packet = self.decoder[node].read_packet()
			if len(rr) == 0:
				time.sleep(0.05) #TODO: Experiment

class Session_Socket(Session):
	def __init__(self, core, host, port, client, server):
		Session.__init__(self, core, host, port)
		self.socket =    {NODE_CLIENT: client, NODE_SERVER: server}
		client.settimeout(0)
		server.settimeout(0)
		self.start()
		
	def flush(self):
		try:
			while True:
				packet = self.packet_queue.get_nowait()
				data = self.decoder[packet.direction].encode_packet(packet)
				try:
					self.socket[self.other[packet.direction]].send(data)
				except: pass
		except Queue.Empty:
			pass
		
class Session_Bot(Session):
	def __init__(self, core, host, port, callback):
		Session.__init__(self, core, host, port)
		self.connect()
		self.callback = callback
	
	def flush(self):
		try:
			while True:
				packet = self.packet_queue.get_nowait()
				self.callback(packet)
		except Queue.Empty:
			pass
