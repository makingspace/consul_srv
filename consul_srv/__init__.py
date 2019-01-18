import requests

from . import query

__all__ = ["service", "register", "mock", "AGENT_URI"]

AGENT_URI = "127.0.0.1"

TeeConfig = namedtuple('TeeConfig', 'serv_original serv_experimental latency_delta')
DEFAULT_TEE_SERVICE = 'fore'

class GenericSession(object):
    """
    Basic service session, which prepopulates requests with the appropriate
    host/port.
    """

    def __init__(self, host_port, tee_config=None, protocol="http"):
        self.base_url = "{}://{}:{}/".format(protocol, host_port.host, host_port.port)
        self.session = requests.Session()
        if tee_config:
            self.session.headers.update({'x-service-original': tee_config.serv_original})
            self.session.headers.update({'x-service-experimental': tee_config.serv_experimental})
            self.session.headers.update({'x-service-latency_delta': tee_config.latency_delta})

    def _path(self, path):
        return self.base_url + path.lstrip("/")

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


class Service(object):
    """
    Provides service discovery via Consul, returning some kind of session
    handler for the service.
    """

    MOCK_SERVICES = {"__all__": False}
    SERVICE_MAP = {"default": GenericSession}
    MOCKED_SERVICE_MAP = {}

    def resolve(self, service_name):
        resolver = query.Resolver(AGENT_URI)
        return resolver.srv(service_name)

    def __call__(self, service_name, service_experimental=None, latency_delta=None, *args):
        """
        Return a service interface for the requested service.
        """
        should_mock = (
            self.MOCK_SERVICES.get(service_name) or self.MOCK_SERVICES["__all__"]
        )
        tee_config = None
        if should_mock:
            service_map = self.MOCKED_SERVICE_MAP
            server = None
            port = None
        else:
            service_map = self.SERVICE_MAP
            if service_experimental:
                tee_config = TeeConfig(serv_original=service_name,
                                        serv_experimental=service_experimental,
                                        latency_delta=latency_delta)
                host_port = self.resolve(DEFAULT_TEE_SERVICE)
            else:
                host_port = self.resolve(service_name)
        try:
            service = service_map[service_name](host_port, tee_config=tee_config, *args)
        except KeyError:
            try:
                service = service_map["default"](host_port)
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
