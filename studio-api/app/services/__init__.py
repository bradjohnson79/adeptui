"""Application services.

A service here owns one domain's rules and is callable without an HTTP request. Routers
become thin translation layers, and any future in-process caller (Co-Director M2.2's tool
dispatch, a CLI, a background job) can reach the same behaviour without going through the
network. The capability registry records the service entry point in `service_ref`.
"""
