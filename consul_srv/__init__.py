import requests
import dns
import logging

from collections import namedtuple

from dns.resolver import Resolver
from . import query

__all__ = ["service", "register", "mock", "AGENT_URI"]

AGENT_URI = "127.0.0.1"
AGENT_PORT = 8600
AGENT_DC = "service.consul"

TeeConfig = namedtuple('TeeConfig', 'serv_original serv_experimental max_delta fore_service')
DEFAULT_TEE_SERVICE = 'fore'
HEADER_SERVICE = 'X-SERVICE-ORIGINAL'
HEADER_SERVICE_EXP = 'X-SERVICE-EXP'
HEADER_MAX_DELTA_SEC = 'X-SERVICE-MAXDELTA-SEC'

class ConsulClient(object):
    """
    Basic service session, which prepopulates requests with the appropriate
    host/port.
    """

    def __init__(self, host, port, protocol="http", *args, **kwargs):
        self.base_url = "{}://{}:{}/".format(protocol, host, port)
        self.session = requests.Session()
        self.fore_url = None

        tee_config = kwargs.pop('tee_config', None)
        if tee_config:
            self.session.headers.update({HEADER_SERVICE: tee_config.serv_original,
                                        HEADER_SERVICE_EXP: tee_config.serv_experimental,
                                        HEADER_MAX_DELTA_SEC: str(tee_config.max_delta if tee_config.max_delta else 0)})
            self.fore_url = "{}://{}:{}/".format(protocol, tee_config.fore_service.host, tee_config.fore_service.port)

    def _path(self, path):
        base = self.fore_url if self.fore_url else self.base_url
        return base + path.lstrip("/")

    def get(self, path, *args, **kwargs):
        return self.session.get(self._path(path), *args, **kwargs)

    def post(self, path, *args, **kwargs):
        return self.session.post(self._path(path), *args, **kwargs)

    def put(self, path, *args, **kwargs):
        return self.session.put(self._path(path), *args, **kwargs)

    def patch(self, path, *args, **kwargs):
        return self.session.patch(self._path(path), *args, **kwargs)

    def delete(self, path, *args, **kwargs):
        return self.session.delete(self._path(path), *args, **kwargs)

    def run(self, request_method, path, **kwargs):
        request = requests.Request(request_method, self._path(path), **kwargs)
        prepped = self.session.prepare_request(request)
        return self.session.send(prepped)

class Service(object):
    """
    Provides service discovery via Consul, returning some kind of session
    handler for the service.
    """
    MOCK_SERVICES = {"__all__": False}
    SERVICE_MAP = {"default": ConsulClient}
    MOCKED_SERVICE_MAP = {}
    DOCKER_HOST = None

    def resolve(self, service_name):
        server_address = AGENT_URI
        # because of the special case involved with passing host.docker.internal to AGENT_URI
        # we have to resolve this to the ip address as this can/will be different for each docker
        # environment.
        if(server_address=='host.docker.internal'):
            if self.DOCKER_HOST == None:
                logging.debug('consul_srv: SPECIAL CASE FOR AGENT_URI = {}'.format(server_address))
                theresolver = dns.resolver.Resolver()
                try:
                    answer = theresolver.query('{}'.format(server_address))
                except DNSException as e:
                    logging.exception('An exception occurred while trying to find "host.docker.internal" IP.')
                    logging.exception('Exception details: {}'.format(e))
                for ipval in answer:
                    server_address=ipval.to_text()
                logging.debug('consul_srv: RESOLVED AGENT_URI = "{}"'.format(server_address))
                self.DOCKER_HOST = server_address
            else:
                server_address = self.DOCKER_HOST
        resolver = query.Resolver(server_address = server_address, port=AGENT_PORT, consul_domain=AGENT_DC)
        return resolver.srv(service_name)

    def __call__(self, service_name, *args, **kwargs):
        """
        Return a service interface for the requested service.
        """
        service_experimental = kwargs.pop('service_experimental', None)
        max_delta = kwargs.pop('max_delta', None)
        env = kwargs.pop('env', None)
        fore_service = kwargs.pop('fore_service', None)
        if not fore_service:
            fore_service = "{}-{}".format(DEFAULT_TEE_SERVICE, env) if env else DEFAULT_TEE_SERVICE

        should_mock = (
            self.MOCK_SERVICES.get(service_name) or self.MOCK_SERVICES["__all__"]
        )
        tee_config = None
        if should_mock:
            service_map = self.MOCKED_SERVICE_MAP
            server = None
            port = None
        else:
            service_name = "{}-{}".format(service_name, env) if env else service_name
            service_map = self.SERVICE_MAP

            if service_experimental:
                service_experimental = "{}-{}".format(service_experimental, env) if env else service_experimental

                tee_config = TeeConfig(serv_original=service_name,
                                        serv_experimental=service_experimental,
                                        max_delta=max_delta,
                                        fore_service=self.resolve(fore_service))

            host_port = self.resolve(service_name)
            server = host_port.host
            port = host_port.port
        try:
            session_cls = service_map[service_name]
            if issubclass(session_cls, ConsulClient):
                service = service_map[service_name](server, port, tee_config=tee_config, *args)
            else:
                service = service_map[service_name](server, port, *args)
        except KeyError:
            try:
                service = service_map["default"](server, port, tee_config=tee_config, *args)
            except KeyError:
                raise KeyError(
                    "Service {} is not currently available. [MOCKED: {}]".format(
                        service_name, should_mock
                    )
                )

        return service


service = Service()


def register(service_name, handler, mock_handler=None):
    """
    Register a handler with a particular service name.
    """
    service.SERVICE_MAP[service_name] = handler
    if mock_handler is not None:
        service.MOCKED_SERVICE_MAP[service_name] = mock_handler


def mock(service_name, should_mock=True, mock_handler=None):
    """
    Enable/disable mocking of a particular service name.
    """
    service.MOCK_SERVICES[service_name] = should_mock
    if mock_handler is not None:
        service.MOCKED_SERVICE_MAP[service_name] = mock_handler
