import requests

from . import query

__all__ = ["service", "register", "mock", "AGENT_URI"]

AGENT_URI = "127.0.0.1"


class GenericSession(object):
    """
    Basic service session, which prepopulates requests with the appropriate
    host/port.
    """

    def __init__(self, host, port, protocol="http"):
        self.base_url = "{}://{}:{}/".format(protocol, host, port)
        self.session = requests.Session()

    def get(self, path, *args, **kwargs):
        return self.session.get(self.base_url + path, *args, **kwargs)

    def post(self, path, *args, **kwargs):
        return self.session.post(self.base_url + path, *args, **kwargs)

    def put(self, path, *args, **kwargs):
        return self.session.put(self.base_url + path, *args, **kwargs)

    def patch(self, path, *args, **kwargs):
        return self.session.patch(self.base_url + path, *args, **kwargs)

    def delete(self, path, *args, **kwargs):
        return self.session.delete(self.base_url + path, *args, **kwargs)


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

    def __call__(self, service_name, *args):
        """
        Return a service interface for the requested service.
        """
        should_mock = (self.MOCK_SERVICES.get(service_name) or
                       self.MOCK_SERVICES["__all__"])
        if should_mock:
            service_map = self.MOCKED_SERVICE_MAP
            server = None
            port = None
        else:
            service_map = self.SERVICE_MAP
            host_port = self.resolve(service_name)
            server = host_port.host
            port = host_port.port
        try:
            service = service_map[service_name](server, port, *args)
        except KeyError:
            try:
                service = service_map["default"](server, port)
            except KeyError:
                raise KeyError(
                    "Service {} is not currently available. [MOCKED: {}]".format(
                        service_name, should_mock))

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
