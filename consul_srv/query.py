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
        """
        By connecting to consul using it's client on port 8500,
            gets a healthy instance for a given service, or it 
            rises an exception if none of the instances are OK.
        """
        logging.debug('consul_srv: running Consul Client query')
        client = consul.Consul(host=self.nameservers[0], port=self.client_port) # Getting a connection with consul
        service_instances = client.health.service(resource)[1] # Getting the services instances health checks
        service_range = list(range(len(service_instances))) # Generating a random sorted list to interate the checks list
        random.shuffle(service_range)
        for instance in service_range:
            service_instance = service_instances[instance] # Getting a random service instance
            logging.debug('consul_srv: checking consul service instance "{}"'.format(service_instance['Service']['ID']))
            self.checks_passed = True
            for check in service_instance['Checks']: # Checking the instances checks status
                if check['Status'] != 'passing': # If any of the checks fails, it assumes the instances is unavailable
                    self.checks_passed = False
                    break
            if self.checks_passed: # If all checks pass, this instances is healthy
                logging.debug('consul_srv: there is at least one instance healthy.')
                return SRV(service_instance['Service']['Address'], service_instance['Service']['Port'])
        raise Exception("No healthy instaces found for service '{}'.".format(resource))
    
    def check_service_from_consul(self, resource):
        """
        By connecting to consul using it's client on port 8500,
            it verifies if a service is healthy
        """
        logging.debug('consul_srv: checking service {} health on consul'.format(resource))
        client = consul.Consul(host=self.nameservers[0], port=self.client_port)
        service_checks = client.health.checks(resource)[1]

        for check in service_checks:
            if check['Status'] == 'passing':
                return True
        logging.debug('consul_srv: No healthy instaces for service {} found'.format(resource))
        return False

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
        except Exception as dnserr:
            logging.debug('consul_srv: something odd happen while running DNS query')
            if pycares.errno.errorcode[dnserr.args[0]] == 'ARES_ENOTFOUND':
                if not self.check_service_from_consul(resource):
                    raise # 
            try:
                logging.debug('consul_srv: falling back to consul client')
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
