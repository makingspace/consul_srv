"""
Simple wrapper around dnspython to query a Consul agent over its DNS port and
extract ip address/port information.
"""
from collections import namedtuple
from dns import rdatatype
from dns.resolver import Resolver
import dns
import time
import random
import logging

SRV = namedtuple("SRV", ["host", "port"])

class Resolver(Resolver):
    """
    Wrapper around the dnspython Resolver class that implements the `srv`
    method. Takes the address and optional port of a DNS server.
    """

    def __init__(self, server_address, port=8600, consul_domain='service.consul'):
        super(Resolver, self).__init__()
        self.consul_server = server_address
        self.consul_port = port
        self.nameservers = [server_address]
        self.nameserver_ports = {server_address: port}
        self.consul_domain = consul_domain
        # timeout = The number of seconds to wait for a response from a server, before timing out.
        # lifetime = The total number of seconds to spend trying to get an answer to the question.
        # max_lookup = [ours] Total number of looping loopups to do
        self.timeout = 2
        self.lifetime = 4
        self.max_lookup = 6

    def _lookup_host(self, hostname):
        # quick resolver for a hostname with special case if it's a consul hostname
        # for best results, we remove the trailing period and make sure it is a string
        # in a couple cases this comes in as type "NAME" whatever that is
        thehostname = hostname.to_text().rstrip('.')
        # this should probably be "ends with consul." which would be more accurate 
        if 'consul' in thehostname:
            # if consul is in the host name we ask the consul DNS which we are already
            # configured for...
            logging.debug('consul_srv: lookup "{}" in consul dns'.format(thehostname))
            theanswer=self.query(hostname, "A", tcp=True)
        else:
            # otherwise we ask for a new dns.resolver.Resolver which we have not
            # overridden the nameserver list (comes from host) to resolve the hostname
            logging.debug('consul_srv: lookup for "{}" in local dns'.format(thehostname))
            theresolver = dns.resolver.Resolver()
            theanswer = theresolver.query(thehostname, 'A', tcp=True)
        iplist=[]
        for ipval in theanswer:
            foundip=ipval.to_text()
            iplist.append(foundip)
            logging.debug('consul_srv: lookup found {}'.format(foundip))
        if len(iplist) > 0:
            return iplist[random.randint(0,len(iplist)-1)]
        raise ValueError("Lookup did not return information.")

    def _get_host(self, answer):
        # changing this functionality from the non-compliant get info from the additional
        # section, to the more compliant do a lookup from host provided by SRV record
        #for resource in answer.response.additional:
        #    for record in resource.items:
        #        if record.rdtype == rdatatype.A:
        #            return record.address
        for resource in answer:
            if resource.rdtype == rdatatype.SRV:
                hostip = self._lookup_host(resource.target)
                if hostip is not False:
                    logging.debug('consul_srv: going with {}'.format(hostip))
                    return hostip
        raise ValueError("No host information.")

    def _get_port(self, answer):
        for resource in answer:
            if resource.rdtype == rdatatype.SRV:
                return resource.port
        raise ValueError("No port information.")

    def get_service(self, resource, count=0):
        domain_name = "{}.{}".format(resource, self.consul_domain)
        try:
            answer = self.query(domain_name, "SRV", tcp=True)
        except:
            if(count<self.max_lookup):
                count = count + 1
                logging.debug('consul_srv: exception, sleeping random 0-1 sec to try again, try {} of {}'.format(count, self.max_lookup))
                time.sleep(random.random())
                answer = self.get_service(resource, count)
            else:
                raise

        return answer

    def srv(self, resource):
        """
        Query this resolver's nameserver for the name consul service. Returns a
        named host/port tuple from the first element of the response.
        """
        logging.debug('consul_srv: asked to lookup {} from {}:{}'.format( resource, self.consul_server, self.consul_port ))
        answer = self.get_service(resource)
        host = self._get_host(answer)
        port = self._get_port(answer)
        logging.debug('consul_srv: recieved answer for {} as {}:{}'.format( resource, host, port ))
        return SRV(host, port)
