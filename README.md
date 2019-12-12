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
