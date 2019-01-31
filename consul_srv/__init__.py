import requests

from collections import namedtuple

from . import query

__all__ = ["service", "register", "mock", "AGENT_URI"]

AGENT_URI = "127.0.0.1"

TeeConfig = namedtuple('TeeConfig', 'serv_original serv_experimental max_delta')
DEFAULT_TEE_SERVICE = 'fore'
HEADER_SERVICE = 'X-SERVICE-ORIGINAL'
HEADER_SERVICE_EXP = 'X-SERVICE-EXP'
HEADER_MAX_DELTA_SEC = 'X-SERVICE-MAXDELTA-SEC'

class GenericSession(object):
    """
    Basic service session, which prepopulates requests with the appropriate
    host/port.
    """

    def __init__(self, host, port, protocol="http", *args, **kwargs):
        self.base_url = "{}://{}:{}/".format(protocol, host, port)
        self.session = requests.Session()
        tee_config = kwargs.pop('tee_config', None)
        if tee_config:
            self.session.headers.update({HEADER_SERVICE: tee_config.serv_original,
                                        HEADER_SERVICE_EXP: tee_config.serv_experimental,
                                        HEADER_MAX_DELTA_SEC: str(tee_config.max_delta)})

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
    SERVICE_MAP = {"default": GenericSession}
    MOCKED_SERVICE_MAP = {}

    def resolve(self, service_name):
        resolver = query.Resolver(AGENT_URI)
        return resolver.srv(service_name)

    def __call__(self, service_name, *args, **kwargs):
        """
        Return a service interface for the requested service.
        """

        service_experimental = kwargs.pop('service_experimental', None)
        max_delta = kwargs.pop('max_delta', None)
        env = kwargs.pop('env', None)
        fore_service = kwargs.pop('fore_service', None)
        fore_client = kwargs.pop('fore_client', None)

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
                                        max_delta=max_delta)
                service_name = "{}-{}".format(DEFAULT_TEE_SERVICE, env) if env else DEFAULT_TEE_SERVICE
                service_name = fore_service if fore_service else service_name

            host_port = self.resolve(service_name)
            server = host_port.host
            port = host_port.port

        if fore_service and fore_client:
            return fore_client(server, port, tee_config=tee_config, *args, **kwargs)

        try:
            session_cls = service_map[service_name]
            if issubclass(session_cls, GenericSession):
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
