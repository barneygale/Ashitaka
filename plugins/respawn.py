import packet_decoder

class Plugin_Respawn:
	def __init__(self, session):
		self.interestedPackets = [0x08]
		self.interestedMessages = []
		self.session = session
	def read_packet(self, item):
		if item.data['health'] == 0:
			self.session.gen(0x09, packet_decoder.TO_SERVER, {'dimension': 0})
