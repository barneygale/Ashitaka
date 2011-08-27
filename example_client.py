from ashitaka import Ashitaka

def callback(self, packet):
	print "Got packet", packet.ident
	
ashitaka = Ashitaka()

