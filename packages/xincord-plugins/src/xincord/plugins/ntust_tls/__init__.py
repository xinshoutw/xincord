"""TLS for NTUST's hosts, whose certificate chains Python's strict X.509 checks refuse.

NtustAnnouncements reads NTUST's announcement pages and NtustCourseWatch asks its course query;
both use this context. This package is no plugin: it has no entry point, and the plugins that use
it import it.
"""

import ssl
from importlib.resources import files

INTERMEDIATE = "twca-secure-ssl-ca.pem"  # TWCA's intermediate, which one NTUST host leaves out


def ntust_context() -> ssl.SSLContext:
    """TLS for NTUST's hosts: certificates and host names verified, without the strict X.509 checks.

    Python 3.13 made ``VERIFY_X509_STRICT`` a default, and the certificate chains of NTUST's hosts
    (``student``, ``www.academic``, ``lc`` and ``querycourse``) lack a Subject Key Identifier, which
    those checks refuse (checked on 2026-10-11): no page would load. Clients without these checks
    accept them. ``www.academic.ntust.edu.tw`` also leaves out TWCA's intermediate certificate,
    which OpenSSL needs to reach the root: the context holds that public certificate (valid until
    2030-10-16). Other hosts keep Python's default context.
    """
    context = ssl.create_default_context()
    context.verify_flags &= ~ssl.VERIFY_X509_STRICT
    context.load_verify_locations(
        cadata=files(__package__).joinpath(INTERMEDIATE).read_text("ascii")
    )
    return context
