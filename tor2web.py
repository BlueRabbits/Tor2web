# Tor2web calamity edition.
# Arturo Filasto' <art@globaleaks.org>
#
# a re-implementation of Tor2web in Python over Tornado

import os
import sys
from mimetypes import guess_type
from pprint import pprint
from urlparse import urlparse
from BeautifulSoup import BeautifulSoup
# import gevent
# from gevent import monkey

import tornado.ioloop
import tornado.web
from tornado import httpclient

http_client = httpclient.HTTPClient()

class Tor2web(object):
    def __init__(self):
        
        # This is the base hostname for
        # the current tor2web node
        self.basehost = "tor2web.org:8888"
        
        # This is set if we are contacting
        # tor2web from x.tor2web.org
        self.xdns = False
        
        # The hostname of the requested HS
        self.hostname = ""

        # The path portion of the URI
        self.path = None
        
        # The full address (hostname + uri) that must be requested
        self.address = None
        
        # The headers to be sent
        self.headers = None

        # DEBUG MODE
        self.debug = True

        # SOCKS proxy
        self.socks = False

    def lookup_petname(self, address):
        """ Do a lookup in the local database
        for an entry in the petname db
        """
        # Currently just dummy
        return address

    def resolve_hostname(self, req):
        """ Resolve the supplied request to a hostname.
        Hostnames are accepted in the <onion_url>.<tor2web_domain>.<tld>/
        or in the x.<tor2web_domain>.<tld>/<onion_url>.onion/ format.
        """
        # Detect x.tor2web.org use mode
        if[req.host.split(".")[0] == "x"]:
            self.xdns = True
            self.hostname = self.lookup_petname(req.uri.split("/")[1])
            if self.debug:
                print "DETECTED x.tor2web Hostname: %s" % self.hostname
        else:
            self.xdns = False
            self.hostname = self.lookup_petname(req.host.split(".")[0])
            if self.debug:
                print "DETECTED <onion_url>.tor2web Hostname: %s" % self.hostname

            
    def get_uri(self, req):
        if self.xdns:
            uri = '/' + '/'.join(req.uri.split("/")[2:])
        else:
            uri = req.uri
        if self.debug:
            print "URI: %s" % uri

        return uri
    
    def get_address(self, req):
        address = req.protocol + "://"
        # Resolve the hostname
        self.resolve_hostname(req)
        # Clean up the uri
        uri = self.get_uri(req)
        
        address += self.hostname + uri
        
        # Get the base path
        self.path = urlparse(address).path
        return address

    def process_request(self, req):
        self.address = self.get_address(req)
        self.headers = req.headers
        self.headers['Host'] = self.hostname
        if self.debug:
            print "Headers:"
            pprint(self.headers) 

    def fix_links(self, data):
        """ Fix all possible links to properly resolve to the
        correct .onion.
        Examples:
        when visiting x.tor2web.org
        /something -> /<onion_url>.onion/something
        <other_onion_url>.onion/something/ -> /<other_onion_url>.onion/something
        
        
        when visiting <onion_url>.tor2web.org
        /something -> /something
        <other_onion_url>/something -> <other_onion_url>.tor2web.org/something
        """
        if data.startswith("/"):
            if self.debug:
                print "LINK starts with /"
            if self.xdns:
                link = "/" + self.hostname + data
            else:
                link = data
                
        elif data.startswith("http"):
            if self.debug:
                print "LINK starts with http://"
            o = urlparse(data)
            if self.xdns:
                link = "/" + o.netloc + o.path
                link += "?" + o.query if o.query else ""
            else:
                if o.netloc.endswith(".onion"):
                    o.netloc.replace(".onion", "")
                link = o.netloc + "." + self.basehost + o.path
                link += "?" + o.query if o.query else ""
        else:
            if self.debug:
                print "LINK starts with "
                print "link: %s" % data
            if self.xdns:
                link = '/' + self.hostname + '/'.join(self.path.split("/")[:-1]) + '/' + data
            else:
                link = data
        
        return link

    def process_links(self, data):
        if self.debug:
            print "processing src attributes"

        for el in data.findAll(['img','script']):
            if self.debug:
                print "el['href'] %s" % el
            try:
                el['src'] = self.fix_links(el['src'])            
            except:
                pass
            
        if self.debug:
            print "processing href attributes"
        for el in data.findAll(['a','link']):
            try:
                el['href'] = self.fix_links(el['href'])
            except:
                pass
        if self.debug:
            print "Finished processing links..."
        return str(data)

    def process_html(self, content):
        soup = BeautifulSoup(content)
        if self.debug:
            print "Now processing head..."
        head = self.process_links(soup.html.head)
        if self.debug:
            print "Now processing body..."
        body = self.process_links(soup.html.body)
        ret = str(head) + str(body)
        return ret
    
    def handle(self, request):      
        self.process_request(request)
        
        try:
            req = httpclient.HTTPRequest(self.address, 
                                         method=request.method,
                                         headers=self.headers,
                                         )
            
            response = http_client.fetch(req)
            try:
                ret = self.process_html(response.body)
                return ret
            except:
                print "%s NOT A HTML FILE" % request.uri
                return response.body
            
        except httpclient.HTTPError, e:
            print "Error:", e
            return "0"

