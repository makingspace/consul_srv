# consul_srv

This is a thin Python layer around interaction with consul for service discovery. In application code, it can be used to attain a service handler by calling `service`:

```
import consul_srv
euclid = consul_srv.service("euclid", "ny")
```

This returns an object which provides an interface to the requested service.

By default `consul_srv` looks for a DNS server at `127.0.0.1`. Depending on your development environment, you can configure it two different ways:

```
import consul_srv
consul_srv.AGENT_URI = '192.168.111.222'
```

This specifies where `consul_srv` should look for a consul agent serving DNS.

```
import consul_srv
consul_srv.mock("euclid")
```

This will set `consul_srv` to serve a mocked service handler when `service("euclid")` is called, bypassing any calls to a consul agent.


By default `consul_srv` looks at the `service.consul` "TLD" for service discovery/resolution.  You can modify this, for example for cross Datacenter Resolution with:

```
import consul_srv
consul_srv.AGENT_DC = 'service.remotedatacenter.consul'
```


## Build and deploy

I've created a helper directory called build.  This assumes you can SSH to baikonur because it populates `PIPY_URL` from there.

 - upate the `setup.py` for version number

 - `./build_helper/image_build.sh` quickly builds a python 2.7 container with current source

 - `./build_helper/image_run.sh` runs that container

now we're in a python 2.7 shell we can build the package with

 - `python setup.py bdist_wheel --universal`

 - `curl -F package=@dist/consul_srv-*{version}*-py2.py3-none-any.whl $PYPI_URL`
