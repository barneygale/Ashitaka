import sys
from os import path, environ
import time
import urllib2
from subprocess import Popen, PIPE
from message import Message
import re
import packet_decoder
from threading import Timer

class Plugin_Connect():
	interestedMessages = ["coreClientConnect", "coreClientDisconnect", "coreServerDisconnect", "keyboardInterrupt", "httpReq"]
	interestedPackets = [0x01, 0x05, 0x07, 0x11, 0x12, 0x13, 0x14, 0x15, 0x16, 0x17, 0x18, 0x19, 0x1C, 0x1D, 0x1E, 0x1F, 0x20, 0x21, 0x22, 0x26, 0x27, 0x28, 0x47]
	interestedPackets += [0x02, 0x0D, 0x10, 0x32, 0xFF]
	def __init__(self, session):
		self.mode = "init"
		self.session = session
		self.reconnect_delay = 5
		self.known_entity_ids = set()
		self.client_entity_id = None
		self.server_entity_id = None
		self.session_id = None
		
		self.current_chunks = set()
		self.new_chunks = set()
		self.slot = 0

	def read_message(self, item):
		if item.ident == "keyboardInterrupt":
			#print "connect.read_message"
			self.session.connected[packet_decoder.NODE_SERVER] = False
			self.session.connected[packet_decoder.NODE_CLIENT] = False
			self.session.gen(0xFF, packet_decoder.TO_SERVER, {'reason':'Disconnecting'})
			self.session.gen(0xFF, packet_decoder.TO_CLIENT, {'reason':u'\xa73Ashitaka received Ctrl-C'})
			self.session.flush()
			self.session.socket[packet_decoder.NODE_SERVER].close()
			if packet_decoder.NODE_CLIENT in self.session.socket:
				self.session.socket[packet_decoder.NODE_CLIENT].close()
			return
		if item.ident == "coreClientDisconnect":
			#print "client d/c"
			self.session.gen(0xFF, packet_decoder.TO_SERVER, {'reason':'Disconnecting'})
			self.handle_client_dc()
		if item.ident == "coreServerDisconnect":
			if self.mode == "normal":
				# "Got coreServerDisconnect"
				self.handle_server_dc(u'\xa74Disconnected from server.')
				self.session.gen(0x03, packet_decoder.TO_CLIENT, {'text': "Reconnecting in %ss..." % self.reconnect_delay})
				t = Timer(self.reconnect_delay, self.reconnect)
				t.start()
			return
	def read_packet(self, item):
		if item.ident == 0x10:
			self.slot = item.data["slot"]
		if self.mode == "init":
			if item.ident == 0x02 and item.direction == packet_decoder.CLIENT_TO_SERVER:
				self.username = item.data['username']
				#print "Recorded username: "+self.username
			if item.ident == 0x01 and item.direction == packet_decoder.CLIENT_TO_SERVER:
				self.protocol_version = item.data['protocol_version']
				#print "Protocol version: "+str(self.protocol_version)
			if item.ident == 0x01 and item.direction == packet_decoder.SERVER_TO_CLIENT:
				self.client_entity_id = item.data['entity_id']
				self.server_entity_id = item.data['entity_id']
				self.mode = "normal"
				#print "Client entity id: " + str(self.client_entity_id)
			return
		
		if item.ident == 0xFF and item.direction == packet_decoder.FROM_CLIENT:
			self.handle_client_dc()
			
		if self.mode == "normal" and item.ident == 0xFF and item.direction == packet_decoder.FROM_SERVER:
			#print "Got a D/C from the server"
			item.transmit = False
			item.process = False
			self.session.flush()
			reason = item.data['reason']
			reason = re.sub('\xa7.{1}', '', reason)
			reason = re.sub('^Kicked: ', '', reason)
			self.handle_server_dc(u'\xa74Kicked: \xa7f'+reason)
			self.reconnect()
			return
				
		if self.mode == "disconnect":
			if item.ident == 0x02 and item.direction == packet_decoder.TO_CLIENT:
				print "Received handshake..."
				item.transmit = False
				item.process = False
				url = "http://www.minecraft.net/game/joinserver.jsp?user=%s&sessionId=%s&serverId=%s" % (self.username, self.session.core.get_session_id(self.username), item.data['connection_hash'])
				response = urllib2.urlopen(url).read()
				if response != 'OK':
					print "joinserver.jsp failed!"
					sys.exit(1)
				print "Sending login..."
				self.session.gen(0x01, packet_decoder.TO_SERVER, {'username': self.username, 'protocol_version': self.protocol_version, 'map_seed':0, 'dimension':0})
			if item.ident == 0x01:
				print "Received login..."
				item.transmit = False
				item.process = False
				#self.core.client.listen = True
				self.server_entity_id = item.data['entity_id']
			if item.ident == 0x32:
				#print "Received pre-chunk..."
				item.transmit = False
				item.process = False
				if item.data['load']:
					self.new_chunks.add((item.data['x'], item.data['z']))
				else:
					self.new_chunks.discard((item.data['x'], item.data['z']))
			if item.ident == 0x0D:
				print "Loading/unloading chunks"
				#Load and unload chunks
				unload  = set(self.current_chunks)
				load    = set(self.new_chunks)
				unload -=     self.new_chunks
				load   -=     self.current_chunks
				for i in load:
					self.session.gen(0x32, packet_decoder.TO_CLIENT, {'x': i[0], 'z': i[1], 'load':True})
				for i in unload:
					self.session.gen(0x32, packet_decoder.TO_CLIENT, {'x': i[0], 'z': i[1], 'load':False})
				self.current_chunks = self.new_chunks
				self.new_chunks = set()
				#Set slot
				print "Setting slot"
				self.session.gen(0x10, packet_decoder.TO_SERVER, {'slot': self.slot})
				#Re-engage client
				print "Reconnecting client!"
				self.session.listen[packet_decoder.NODE_CLIENT] = True
				self.mode = "normal"
			return
		if self.mode == "normal" and item.ident == 0x32:
			if item.data['load']:
				self.current_chunks.add((item.data['x'], item.data['z']))
			else:
				self.current_chunks.discard((item.data['x'], item.data['z']))
		if self.mode == "normal":
			for key in ('entity_id', 'subject_entity_id', 'object_entity_id'):
				if key in item.data:
					self.known_entity_ids.add(item.data[key])
					if item.data[key] == self.client_entity_id:
						item.data[key] = self.server_entity_id
					elif item.data[key] == self.server_entity_id:
						item.data[key] = self.client_entity_id
			return
				
	def handle_server_dc(self, message):
		#print "Handling D/C"
		#print "Server d/c!"
		self.mode = "disconnect"
		self.session.listen[packet_decoder.NODE_SERVER] = False
		self.session.listen[packet_decoder.NODE_CLIENT] = False
		self.session.gen(0x00, packet_decoder.TO_CLIENT, {})
		self.session.gen(0x03, packet_decoder.TO_CLIENT, {'text': message})
	def handle_client_dc(self):
		#print "Handling client D/C..."
		self.session.connected[packet_decoder.NODE_SERVER] = False
		self.session.connected[packet_decoder.NODE_CLIENT] = False
		self.session.listen[packet_decoder.NODE_SERVER] = False
		self.session.listen[packet_decoder.NODE_CLIENT] = False
		self.session.flush()
		#self.session.socket[packet_decoder.NODE_SERVER].close()
		self.session.core.destroy_session(self.session)
		#print "Done..."
	#INIT:
	#Step 1: record username in handshake, self.username
	#Step 2: record entity_id in login, self.client_entity_id
	#Step 3: change to NORMAL
	
	#NORMAL:
	
	#DISCONNECT:
	#Step 0: Display message and start timer (also self.keep_alive = True)
	#Step 1: Destroy all known entities, clear list!
	#Step 2a: set server.transmit = False
	#Step 2b: Reconnect to the server
	#Step 3: Send handshake
	#Step 4: Receive handshake response (connection hash) and consume
	#Step 5: Do HTTP GET to joinserver.jsp
	#Step 6: Send login
	#Step 7: Receive login response (self.server_entity_id) and consume
	#Step 8: Receive spawn location and consume
	#Step 9: change to RECONNECTED 
	#Step 10: set server.transmit = True
	
	#RECONNECTED:
	# Transform all entity IDs.
	def reconnect(self):
		print "Clearing entities"
		for entity_id in self.known_entity_ids:
			if entity_id != self.client_entity_id: #Don't destroy the current player in the case of a collision
				self.session.gen(0x1D, packet_decoder.SERVER_TO_CLIENT, {'entity_id': entity_id})
		self.known_entity_ids.clear()
		print "Connecting to server..."
		#self.session.gen(0x03, packet_decoder.SERVER_TO_CLIENT, {'message': u'\xa2Connecting...'})
		self.session.connect()
		self.session.listen[packet_decoder.NODE_SERVER] = True
		print "Sending handshake..."
		self.session.gen(0x02, packet_decoder.CLIENT_TO_SERVER, {'username': self.username})

