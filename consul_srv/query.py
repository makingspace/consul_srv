"""
Simple wrapper around dnspython to query a Consul agent over its DNS port and
extract ip address/port information.
"""
from collections import namedtuple
from dns import rdatatype
from dns.resolver import Resolver

SRV = namedtuple("SRV", ["host", "port"])

class Resolver(Resolver):
    """
    Wrapper around the dnspython Resolver class that implements the `srv`
    method. Takes the address and optional port of a DNS server.
    """

    def __init__(self, server_address, port=8600, consul_domain='service.consul'):
        super(Resolver, self).__init__()
        self.nameservers = [server_address]
        self.nameserver_ports = {server_address: port}
        self.consul_domain = consul_domain
        # timeout = The number of seconds to wait for a response from a server, before timing out.
        # lifetime = The total number of seconds to spend trying to get an answer to the question.
        # max_lookup = [ours] Total number of looping loopups to do
        self.timeout = 2
        self.lifetime = 4
        self.max_lookup = 5

    def _get_host(self, answer):
        for resource in answer.response.additional:
            for record in resource.items:
                if record.rdtype == rdatatype.A:
                    return record.address

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
        answer = self.get_service(resource)
        host = self._get_host(answer)
        port = self._get_port(answer)
        return SRV(host, port)
