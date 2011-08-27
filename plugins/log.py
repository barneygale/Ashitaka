from packet_decoder import *
from time import gmtime, strftime

class Plugin_Log:
	def __init__(self, core):
		self.interestedPackets = [ident for ident, name in names.items()]
		self.interestedMessages = []
		self.format = "[%s] 0x%02x: %-"+str(max([len(i) for i in names.values()])+1)+"s%s\n"
		#print self.interestedPackets
		self.f = {
			SERVER_TO_CLIENT: open('server_to_client.log', 'w'),
			CLIENT_TO_SERVER: open('client_to_server.log', 'w')
		}
	def read_packet(self, item):
		self.f[item.direction].write(self.format % (strftime("%H:%M:%S", gmtime()), item.ident, names[item.ident], str(item.data)))
		self.f[item.direction].flush()
