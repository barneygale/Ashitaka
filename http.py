import urlparse
import urllib
def read(socket, mode):
	data = {}
	buff = ''
	while True:
		d = socket.recv(8192)
		buff += d
		if "\r\n\r\n" in buff: 
			headers, buff = buff.split("\r\n\r\n", 1)
			break
	headers = headers.split("\r\n")
	if mode == "req":
		data['method'], path, data['version'] = headers.pop(0).split(" ")
		path = urlparse.urlsplit(path)
		data['path'] = {
			'path': path.path,
			'query': dict([(a, b) for a, b in urlparse.parse_qsl(path.query.lstrip("?"))]),
			'fragment': path.fragment}
		assert data['method'] == "GET"
	else:
		data['version'], data['code'], data['string'] = headers.pop(0).split(" ", 2)
	data['headers'] = dict([i.split(": ", 1) for i in headers])
	
	if 'Content-Length' in data['headers']:
		data['response'] = buff
		l = int(data['headers']['Content-Length'])
		while len(data['response']) < l:
			data['response'] += socket.recv(min(8192, l - len(data['response'])))
	#Fucking chunk encoding - bane of my life.
	elif 'Transfer-Encoding' in data['headers'] and data['headers']['Transfer-Encoding'] == 'chunked':
		data['response'] = ''
		while True:
			l, buff = buff.split("\r\n", 1)
			l = int(l, 16)
			if l == 0: break
			while len(buff) < l:
				try: buff += socket.recv(l - len(buff))
				except: pass
			data['response'] += buff[:l]
			buff = buff[l:]
			if len(buff) < 32:
				try: buff += socket.recv(32)
				except: pass
			buff = buff[2:] #Read final CRLF at end of chunk
		del data['headers']['Transfer-Encoding']
			
	return data
def write(socket, mode, data):
	if mode == "req":
		query = urllib.urlencode(data['path']['query'])
		if query: query = "?" + query
		path = "%s%s%s" % (data['path']['path'], query, data['path']['fragment'])
		o = "%s %s %s\r\n" % (data['method'], path, data['version'])
	else:
		o = "%s %s %s\r\n" % (data['version'], data['code'], data['string'])
		if 'response' in data:
			data['headers']['Content-Length'] = len(data['response'])
	for k, v in data['headers'].items():
		o += "%s: %s\r\n" % (k, v)
	o += "\r\n"
	if mode == "res" and 'response' in data:
		o += data['response']
	socket.send(o)
