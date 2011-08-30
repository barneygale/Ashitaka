import re
import packet_decoder

COLOURS = '(?:(\xa7.{1})+)'

class Plugin_Chat:
	def __init__(self, session):
		self.interestedPackets = [0x03]
		self.interestedMessages = []
		self.detect_bukkit_wrap = True
		self.wrap_moar = False
		self.subscribers = []
		self.packet_buffer = []
		
		triplet = "\((?P<%s>[0-9\.\-]+),\s?(?P<%s>[0-9\.\-]+),\s?(?P<%s>[0-9\.\-]+)\)"
		
		self.handlers = [
			#Basics
			('chat',                {'regex': '^\<(?P<player>[0-9A-Za-z_]{1,16})\> (?P<message>.*)$'}),
			('action',              {'regex': '^\* (?P<player>[0-9A-Za-z_]{1,16}) (?P<action>.*)$'}),
			('player_join',         {'regex': '^\xa7e(?P<player>[0-9A-Za-z_]{1,16}) joined the game\.$'}),
			('player_quit', 	{'regex': '^\xa7e(?P<player>[0-9A-Za-z_\xa7]{1,16}) left the game\.$'}),
			('server_message',      {'regex': '^\xa7d\[Server\] (?P<message>.*)'}),
			
			#Mail
			('mail_count',          {'regex': '^\xa7cYou have (?P<count>\d+) messages!\xa7f Type \xa77/mail read\xa7f to view your mail\.$',
			                         'num'  : ['count']}),
			('mail_count',          {'regex': '^\xa77You have no new mail\.$',
				                 'extra': {'count': 0}}),
			#PVP
			('player_kill',         {'regex': '^\xa74(?P<killer>[0-9A-Za-z_]{1,16}) (?:killed|executed|took down) (?P<victim>[0-9A-Za-z_]{1,16}) using a\(n\) (?P<weapon>.*)\.$'}),
			('player_kill',         {'regex': '^\xa74(?P<killer>[0-9A-Za-z_]{1,16}) showed (?P<victim>[0-9A-Za-z_]{1,16}) the (?:wrong|business) end of a\(n\) (?P<weapon>.*)\.$'}),
			('player_kill_streak',  {'regex': '^\xa72\[(?P<player>[0-9A-Za-z_]{1,16})\] (?P<kill_streak>.*)!$'}),
			
			#Mod tools
			('mod_broadcast',       {'regex': '^\xa7f\[\xa7cMod broadcast\xa7f - \xa7c(?:\xa7a)?(?P<player>[0-9A-Za-z_]{1,16})(?:\xa7f)+\] \xa7a(?P<message>.*)$'}),
			('modmode',             {'regex': '^\xa7cYou are now in mod mode\.$',
				                 'extra': {'enabled': True}}),
			('vanish',              {'regex': '^\xa7cPoof!$',
				                 'extra': {'enabled': True}}),
			('teleport',            {'regex': '^\xa77Teleporting\.\.\.$'}),
			('kit',                 {'regex': '^\xa77Giving kit (?P<kit>.*)\.$'}),
			
			#MCCondom
			('warning',             {'regex': '^\xa7c(?:\xa7a)?(?P<player>[0-9A-Za-z_]{1,16})(?:\xa7f)? \| Time on:(?P<time_on>\d+)mins \| Logins:(?P<logins>[0-9\-]+) \| Warns:(?P<warns>\d+)$',
			                         'num'  : ['time_on', 'logins', 'warns']}),
			
			#MCBouncer
			('notes',               {'regex': '^\xa7a(?P<player>[0-9A-Za-z_]{1,16}) has (?P<count>\d+) notes?\.$',
			                         'num'  : ['count']}),
			
			#ModTRS
			('modtrs',              {'regex': '^\xa7aThere are (?P<count>\d+) open mod requests\. Type /check to see them\.$',
					         'extra': {'type': 'count'},
					         'num'  : ['count']}),
			('modtrs',              {'regex': '^\xa7aNew mod request filed; use /check for more\.$',
				                 'extra': {'type': 'new'}}),
			('modtrs',              {'regex': '^\xa76Request #(?P<req_id>[0-9,]+) has been completed\.$',
				                 'extra': {'type': 'done'},
				                 'num'  : ['req_id']}),
			#Nocheat
			('nocheat',             {'regex': '^\[(?:[A-Z]+)\] NC: Moving violation: (?P<player>[0-9A-Za-z_]{1,16}) from (?P<world>\w+) distance ' + triplet % ('x', 'y', 'z') + '$',
			                         'extra': {'type': 'moving_violation'},
			                         'num'  : ['x','y','z']}),
			('nocheat',             {'regex': '^\[(?:[A-Z]+)\] NC: Moving summary of last ~(?P<time>\d+) seconds: (?P<player>[0-9A-Za-z_]{1,16}) total Violations: ' + triplet % ('x','y','z') + '$',
			                         'extra': {'type': 'moving_summary'},
			                         'num':   ['time','x','y','z']}),
			('nocheat',             {'regex': '^\[(?:[A-Z]+)\] NC: (?P<player>[0-9A-Za-z_]{1,16}) sent (?P<total_events>\d+) move events, but only (?P<allowed_events>\d+) were allowed\. Speedhack\?$',
			                         'extra': {'type': 'speedhack'},
			                         'num':   ['total_events', 'allowed_events']}),
			#Useless shit
			('null',                {'regex': '^\xa75\xa76\xa74\xa75$'}),
			('null',                {'regex': '^\xa7cWelcome, [0-9A-Za-z_]{1,16}\xa7c! $'}),
			('null',                {'regex': '^\xa7fType \xa7c/help\xa7f for a list of commands\. $'}),
			('null',                {'regex': '^Visit nerd\.nu for information on other servers\. $'}),
			('null',                {'regex': '^-$'}),
			('null',                {'regex': '^\xa7b[0-9A-Za-z_]{1,16}, craft a sword or something\.$'}),
			('null',                {'regex': '^\xa7b[0-9A-Za-z_]{1,16} is getting killed out there\.$'})
		]
		deaths = {
			'cactus':        ['got a little too close to a cactus', 'tried to hug a cactus'],
			'creeper':       ['hugged a creeper', 'was creeper bombed'],
			'fall':          ['has fallen to their death', 'leaped before looking'],
			'fire':          ['burned to death', 'just got burned', 'has been set on fire'],
			'lava':          ['became obsidian', 'tried to swim in a pool of lava'],
			'slime':         ['was slimed'],
			'spider':        ['was overtaken by the spiders'],
			'water':         ['needs swimming lessons', 'forgot to come up for air', 'has drowned'],
			'zombie pigman': ['lost the fight against a zombie pig'],
			'zombie':        ['was punched to death by zombies', 'was left 4 dead'],
			'unknown':       ['died from unknown causes']
		}
		for cause, strings in deaths.items():
			for s in strings:
				self.handlers.append(('player_death', {'regex': '^\xa74(?P<player>[0-9A-Za-z_]{1,16}) %s\.$' % s, 'extra': {'cause': cause}}))
		
		self.handlers.append(('unknown', {'regex': '^(?P<text>.*)$'}))
		for h in self.handlers:
			h[1]['regex'] = re.compile(h[1]['regex'])
		self.session = session
	
	
	def detect_wrap(self, *args):
		chat_length = 119
		chat_width = 320
		characters = u' !"#$%&\'()*+,-./0123456789:;<=>?@ABCDEFGHIJKLMNOPQRSTUVWXYZ[\]^_\'abcdefghijklmnopqrstuvwxyz{|}~\xe2\x8c\x82\xc3\x87\xc3\xbc\xc3\xa9\xc3\xa2\xc3\xa4\xc3\xa0\xc3\xa5\xc3\xa7\xc3\xaa\xc3\xab\xc3\xa8\xc3\xaf\xc3\xae\xc3\xac\xc3\x84\xc3\x85\xc3\x89\xc3\xa6\xc3\x86\xc3\xb4\xc3\xb6\xc3\xb2\xc3\xbb\xc3\xb9\xc3\xbf\xc3\x96\xc3\x9c\xc3\xb8\xc2\xa3\xc3\x98\xc3\x97\xc6\x92\xc3\xa1\xc3\xad\xc3\xb3\xc3\xba\xc3\xb1\xc3\x91\xc2\xaa\xc2\xba\xc2\xbf\xc2\xae\xc2\xac\xc2\xbd\xc2\xbc\xc2\xa1\xc2\xab\xc2\xbb#'
		character_widths = [
			1, 9, 9, 8, 8, 8, 8, 7, 9, 8, 9, 9, 8, 9, 9, 9,
			8, 8, 8, 8, 9, 9, 8, 9, 8, 8, 8, 8, 8, 9, 9, 9,
			4, 2, 5, 6, 6, 6, 6, 3, 5, 5, 5, 6, 2, 6, 2, 6,
			6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 2, 2, 5, 6, 5, 6,
			7, 6, 6, 6, 6, 6, 6, 6, 6, 4, 6, 6, 6, 6, 6, 6,
			6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 4, 6, 4, 6, 6,
			3, 6, 6, 6, 6, 6, 5, 6, 6, 2, 6, 5, 3, 6, 6, 6,
			6, 6, 6, 6, 4, 6, 6, 6, 6, 6, 6, 5, 2, 5, 7, 6,
			6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 4, 6, 3, 6, 6,
			6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 4, 6,
			6, 3, 6, 6, 6, 6, 6, 6, 6, 7, 6, 6, 6, 2, 6, 6,
			8, 9, 9, 6, 6, 6, 8, 8, 6, 8, 8, 8, 8, 8, 6, 6,
			9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9, 9,
			9, 9, 9, 9, 9, 9, 9, 9, 9, 6, 9, 9, 9, 5, 9, 9,
			8, 7, 7, 8, 7, 8, 8, 8, 7, 8, 8, 7, 9, 9, 6, 7,
			7, 7, 7, 7, 9, 6, 7, 8, 7, 6, 6, 9, 7, 6, 7, 1]
	
		#PART ONE: examine the first part to see if it wraps
		more = False
		text = args[-1]
		text += "@" 
		if len(text) > chat_length:
			more = True
		else:
			width = 0
			i = 0
			while i < len(text):
				if text[i] == u'\xa7':
					i+=2
					continue
				index = characters.find(text[i])
				width += character_widths[index+32]
				if width >= chat_width:
					more = True
					break
				i+=1
		
		#PART 2: examine the second part (if present) to see if it fits
		if len(args) == 1:
			return more
		else:
			#print "LINE 1: " + args[0]
			#print "LINE 2: " + args[1]
			
			pos = args[0].rfind(u'\xa7')
			if pos != -1: colour = args[0][pos+1]
			else:         colour = 'f'
			
			#print "colour: "+colour
			if colour.lower() == 'f':
				return args[1][0] != u'\xa7', more
			else:   
				return args[1][1] ==  colour, more
	
	def merge(self, lines):
		out = ''
		colour = 'f'
		first_line = True
		#print "MERGING:"
		#print lines
		for l in lines:
			if not first_line and colour != 'f':
				assert l[:2] == u'\xa7%s' % colour
				out += l[2:]
			else:	out += l
			first_line = False
			pos = l.rfind(u'\xa7')
			if pos != -1:
				colour = l[pos+1]
		return out
	def to_num(self, text):
		text = text.replace(',', '')
		if '.' in text: return float(text)
		else:           return int(text)
	def read_packet(self, packet):
		if packet.direction != packet_decoder.TO_CLIENT: return
		if self.detect_bukkit_wrap:
			if self.packet_buffer:   ok, more = self.detect_wrap(self.packet_buffer[-1].data['text'], packet.data['text'])
			else:                    ok, more = True, self.detect_wrap(packet.data['text'])	
			
			#print "BUFF LEN: ", len(self.packet_buffer)
			#print "OK", ok
			#print "MORE", more
			if not ok:
				self.process()
			
			self.packet_buffer.append(packet)
			
			if not more:
				self.process()
		else:
			self.packet_buffer.append(packet)
			self.process()
		
		packet.transmit = False
	
	def process(self):
		text = self.merge([i.data['text'] for i in self.packet_buffer])
		for handler in self.handlers:
			m = re.match(handler[1]['regex'], text)
			if m:
				ident = handler[0]
				data = m.groupdict()
				if 'extra' in handler[1]:
					data = dict(data, **handler[1]['extra'])
				if 'num' in handler[1]:
					for f in handler[1]['num']:
						data[f] = self.to_num(data[f])
				
				for s in self.subscribers:
					if s(ident, data) == False:
						#print "Not transmitting!"
						self.packet_buffer = []
						return
				break
		if self.wrap_moar:
			self.session.gen(0x03, packet_decoder.TO_CLIENT, {'text': text})
		else:
			for p in self.packet_buffer:
				p.transmit = True
				self.session.packet_queue.put(p)
			self.session.flush()
		
		self.packet_buffer = []

			
	def subscribe(self, callback):
		self.subscribers.append(callback)
	
	def unsubscribe(self, callback):
		self.subscribers.remove(callback)	
			
		
