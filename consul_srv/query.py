"""
Simple wrapper around dnspython to query a Consul agent over its DNS port and
extract ip address/port information.
"""
import asyncio
from async_dns.core import types, Address
from async_dns.resolver import DNSClient
from collections import namedtuple
from dns.resolver import Resolver
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
        self.consul_address = '{}:{}'.format(server_address, port)
        self.nameservers = [server_address]
        self.nameserver_ports = {server_address: port}
        self.consul_domain = consul_domain
        # timeout = The number of seconds to wait for a response from a server, before timing out.
        # lifetime = The total number of seconds to spend trying to get an answer to the question.
        # max_lookup = [ours] Total number of looping loopups to do
        self.timeout = 2
        self.lifetime = 4
        self.max_lookup = 6

    def _get_host(self, answer):
        for record in answer.ar:
            if record.qtype == types.A:
                return record.data.data

        raise ValueError("No host information.")

    def _get_port(self, answer):
        for record in answer.an:
            if record.qtype == types.SRV:
                return record.data.port

        raise ValueError("No port information.")

    async def query(self, domain, rtype):
        logging.debug('Trying to get IP for {} from {}'.format(domain, self.consul_address))
        client = DNSClient()
        res = await client.query(domain, rtype, Address.parse(self.consul_address))
        from async_dns.request import clean
        clean() # Need to clean up before running the next query
        return res

    def get_service(self, resource, count=0):
        domain_name = "{}.{}".format(resource, self.consul_domain)
        try:
            answer = asyncio.run(self.query(domain_name, types.SRV))
        except:
            if(count<self.max_lookup):
                count = count + 1
                logging.debug('consul_srv: exception, sleeping random 0-1 sec to try again, try {} of {}\n'.format(count, self.max_lookup))
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
        # Get the host from the ADDITIONAL section
        logging.debug('consul_srv: asked to lookup {} from {}:{}\n'.format( resource, self.consul_server, self.consul_port ))

        answer = self.get_service(resource)
        host = self._get_host(answer)
        port = self._get_port(answer)
        logging.debug('consul_srv: recieved answer for {} as {}:{}\n'.format( resource, host, port ))
        return SRV(host, port)
