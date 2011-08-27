#!/usr/bin/python
import SocketServer
import socket
import struct
import threading
import time
import http
import select
import re

SocketServer.TCPServer.allow_reuse_address = True

"""
    0x00 = request granted
    0x01 = general failure
    0x02 = connection not allowed by ruleset
    0x03 = network unreachable
    0x04 = host unreachable
    0x05 = connection refused by destination host
    0x06 = TTL expired
    0x07 = command not supported / protocol error
    0x08 = address type not supported
"""
class SOCKSServer(threading.Thread, SocketServer.ThreadingMixIn, SocketServer.TCPServer):
	def __init__(self, core):
		threading.Thread.__init__(self)
		SocketServer.TCPServer.__init__(self, ('localhost', 1080), SOCKSHandler)
		self.core = core
		self.start()
	def run(self):
		self.serve_forever()
	def stop(self):
		self.shutdown()
		self.socket.close()

class SOCKSHandler(SocketServer.BaseRequestHandler):
	def handle(self):
		#CLIENT: Greeting
		client = self.request
		assert client.recv(1) == '\x05'
		c = client.recv(1)
		assert '\x00' in client.recv(ord(c))
		
		#SERVER: Choice of auth
		client.send('\x05\x00')
		
		#CLIENT: Connection req
		assert client.recv(3) == '\x05\x01\x00'
		address_type_raw = client.recv(1)
		#IPv4:
		if address_type_raw == '\x01':
			address_type = socket.AF_INET
			address_raw = client.recv(4)
			address = socket.inet_ntop(socket.AF_INET, address_raw)
		#IPv6:
		if address_type_raw == '\x04': 
			address_type = socket.AF_INET6
			address_raw = client.recv(16)
			address = socket.inet_ntop(socket.AF_INET6, address_raw)
		#Domain name
		if address_type_raw == '\x03':
			address_type = socket.AF_INET
			address_raw = ''
			while True:
				d = client.recv(1)
				address_raw += d
				if d == '\x00':
					break
			address = address_raw[:-1]
		
		port_raw = client.recv(2)
		port = struct.unpack('!h', port_raw)[0]
		
		
		#SERVER: Connection response
		
		status = '\x01'
		server = socket.socket(address_type, socket.SOCK_STREAM)
		server.settimeout(25)
		try:
			#print address, port
			server.connect((address, port))
			status = '\x00'
			#print "Request OK"
		except socket.error, e:
			#print "Request failed..."
			e = re.sub('^\[.*\]\s*', '', str(e).lower())
			if e == 'connection refused':
				status = '\x05'
			if e == 'timed out':
				status = '\x04'
		client.send('\x05'+status+'\x00'+address_type_raw+address_raw+port_raw)
		
		if status != '\x00':
			client.close()
			return
		#HTTP
		if port == 80:
			time.sleep(0.0001)
			data = http.read(client, "req")
			if data['headers']['Host'].endswith("minecraft.net") and data['path']['path'] == '/game/joinserver.jsp':
				data['path']['query']['sessionId'] = self.server.core.get_session_id(data['path']['query']['user'], data['path']['query']['sessionId'])
			http.write(server, "req", data)
			data = http.read(server, "res")
			#print data
			#TODO: Processing
			http.write(client, "res", data)
			client.close()
			server.close()
		
		#HTTPS (pass thru)
		elif port == 443:
			sockets = (client, server)
			m = {client: server, server: client}
			while True:
				ready = select.select(sockets, [], [])[0]
				for s in ready:
					d = s.recv(8192)
					if d == '':
						server.close()
						client.close()
						return
					m[s].send(d)
		
		#Minecraft
		else:
			self.server.core.new_session(client, server)
