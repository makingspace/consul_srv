#!/usr/bin/python3
# small web server that instruments "GET" but then serves up files
# to server files with zero lines of code,  do
#
#   python -m http.server 8080     # python 3
#
# or
#
#   python -m SimpleHTTPServer 8080 # python 2
#
# Shamelessly snarfed from Gary Robinson
#    http://www.garyrobinson.net/2004/03/one_line_python.html
#
import http.server
import socketserver
import consul_srv
from http import HTTPStatus

class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        consul_srv.AGENT_URI = "host.docker.internal"
        heimdall = consul_srv.service("heimdall-staging", "https")
        print("Got path: {}".format(heimdall._path('/path')))
        self.send_response(HTTPStatus.OK)
        self.end_headers()
        self.wfile.write(b'STATUS OK')

print("starting server...")
httpd = socketserver.TCPServer(('', 8080), Handler)
try:
    httpd.serve_forever()
except KeyboardInterrupt:
    pass
finally:
    print("stoping server...")
    # Clean-up server (close socket, etc.)
    httpd.server_close()
    httpd.shutdown()