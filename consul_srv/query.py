"""
Simple wrapper around dnspython to query a Consul agent over its DNS port and
extract ip address/port information.
"""
from collections import namedtuple
from typing import (
    Any,
    Optional,
    Set
)

import asyncio
import aiodns
import consul
import pycares
import time
import random
import logging

SRV = namedtuple("SRV", ["host", "port"])

class Resolver(aiodns.DNSResolver):
    """
    Wrapper around the dnspython Resolver class that implements the `srv`
    method. Takes the address and optional port of a DNS server.
    """

    def __init__(self, server_address: Optional[str] = None,
                 loop: Optional[asyncio.AbstractEventLoop] = None,
                 port = 53,
                 client_port = 8500,
                 timeout=1,
                 consul_domain='service.consul',
                 **kwargs: Any) -> None:
        self.loop = loop or asyncio.get_event_loop()
        assert self.loop is not None
        kwargs.pop('sock_state_cb', None)
        self._channel = pycares.Channel(sock_state_cb=self._sock_state_cb, tries=1, timeout=timeout, udp_port=port, **kwargs)
        if server_address:
            self.nameservers = [server_address]
        self._read_fds = set() # type: Set[int]
        self._write_fds = set() # type: Set[int]
        self._timer = None  # type: Optional[asyncio.TimerHandle]

        self.consul_address = '{}:{}'.format(server_address,port)
        self.consul_domain = consul_domain
        self.max_lookup = 5
        self.client_port = client_port

    async def runQuery(self, name, query_type):
        return await self.query(name, query_type)

    def _get_host(self, answer):
        for record in answer[1]: 
            logging.debug('consul_srv: looking for host at {}'.format(record))
            if type(record) == pycares.ares_query_a_result:
                return record.host

        raise ValueError("No host information.")

    def _get_port(self, answer):
        for record in answer[0]: 
            logging.debug('consul_srv: looking for port at {}'.format(record))
            if type(record) == pycares.ares_query_srv_result:
                return record.port

        raise ValueError("No port information.")

    def get_service_from_consul(self, resource):
        logging.debug('consul_srv: running Consul Client query')
        client = consul.Consul(host=self.nameservers[0], port=self.client_port)
        service_instances = client.catalog.service(resource)[1]
        rand_instance = random.randint(0, len(service_instances)-1)
        service_instance = service_instances[rand_instance]
        return SRV(service_instance['ServiceAddress'], service_instance['ServicePort'])

    def get_service_from_dns(self, resource):
        logging.debug('consul_srv: running DNS query')
        domain_name = "{}.{}".format(resource, self.consul_domain)
        coroSRV = self.runQuery(domain_name, 'SRV')
        coroA = self.runQuery(domain_name, 'A')
        answer = self.loop.run_until_complete(asyncio.gather(
            coroSRV,
            coroA
        ))
        return SRV(self._get_host(answer), self._get_port(answer))

    def get_service(self, resource, count=0):
        
        try:
            logging.debug('consul_srv: requesting entries for {}'.format(resource))
            answer = self.get_service_from_dns(resource)
        except:
            try:
                logging.debug('consul_srv: something odd happen while running DNS query, falling back to consul client')
                answer = self.get_service_from_consul(resource)
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
        logging.debug('consul_srv: asked to lookup {} from {}'.format( resource, self.consul_address ))
        answer = self.get_service(resource)
        logging.info('consul_srv: recieved answer for {} as {}\n'.format( resource, answer ))
        return answer
