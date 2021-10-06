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
                 timeout=2.0,
                 consul_domain='service.consul',
                 **kwargs: Any) -> None:
        self.loop = loop or asyncio.get_event_loop()
        assert self.loop is not None
        kwargs.pop('sock_state_cb', None)
        self._channel = pycares.Channel(sock_state_cb=self._sock_state_cb, timeout=timeout, udp_port=port, **kwargs)
        if server_address:
            self.nameservers = [server_address]
        self._read_fds = set() # type: Set[int]
        self._write_fds = set() # type: Set[int]
        self._timer = None  # type: Optional[asyncio.TimerHandle]

        self.consul_address = '{}:{}'.format(server_address,port)
        self.consul_domain = consul_domain
        self.max_lookup = 5

    async def runQuery(self, name, query_type):
        return await self.query(name, query_type)

    def _get_host(self, answer):
        logging.debug('Got these: {}'.format(answer))
        for record in answer[1]: 
            logging.debug('Looking for host at {}'.format(record))
            if type(record) == pycares.ares_query_a_result:
                return record.host

        raise ValueError("No host information.")

    def _get_port(self, answer):
        for record in answer[0]: 
            logging.debug('Looking for port at {}'.format(record))
            if type(record) == pycares.ares_query_srv_result:
                return record.port

        raise ValueError("No port information.")

    def get_service(self, resource, count=0):
        domain_name = "{}.{}".format(resource, self.consul_domain)
        try:
            coroSRV = self.runQuery(domain_name, 'SRV')
            coroA = self.runQuery(domain_name, 'A')
            answer = self.loop.run_until_complete(asyncio.gather(
                coroSRV,
                coroA
            ))
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
        logging.debug('consul_srv: asked to lookup {} from {}\n'.format( resource, self.consul_address ))

        answer = self.get_service(resource)
        host = self._get_host(answer)
        port = self._get_port(answer)
        logging.debug('consul_srv: recieved answer for {} as {}:{}\n'.format( resource, host, port ))
        return SRV(host, port)
