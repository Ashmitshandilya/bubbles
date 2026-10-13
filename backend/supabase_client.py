import os

import env_compat  # noqa: F401  (loads .env and maps legacy COCO_* names to BUBBLES_*)
import httpx
from dotenv import load_dotenv
from supabase import Client, create_client
from supabase.lib.client_options import SyncClientOptions

load_dotenv()

# Backend credentials are intentionally server-only.


SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SECRET_KEY = os.getenv("SUPABASE_SECRET_KEY")

if not SUPABASE_URL:
    raise RuntimeError("SUPABASE_URL is missing from .env")

if not SUPABASE_SECRET_KEY:
    raise RuntimeError("SUPABASE_SECRET_KEY is missing from .env")

class _RetryStaleConnection(httpx.HTTPTransport):
    """Sends a read once more on a fresh connection when the kept-open one turned out to be closed.

    Supabase (behind its proxy) closes idle connections without notice; the next request on such a connection fails
    with "Server disconnected" although the database is fine. Only reads are sent again: a write may already have run."""

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        try:
            return super().handle_request(request)
        except (httpx.RemoteProtocolError, httpx.ReadError):
            if request.method not in {"GET", "HEAD", "OPTIONS"}:
                raise
            return super().handle_request(request)


def _http_client() -> httpx.Client:
    """One HTTP client for the database and the sign-in service, safe to share between the server's worker threads.

    The library default is a single HTTP/2 client shared by every thread; one dropped HTTP/2 connection then fails
    every request in flight at once, which the app reports as "Bubbles' database isn't answering" while Supabase
    itself is healthy. HTTP/1.1 gives each request its own connection, idle ones are dropped before Supabase drops
    them, a failed connect is tried again, and nothing waits longer than the timeouts below."""
    return httpx.Client(
        http2=False,
        follow_redirects=True,
        timeout=httpx.Timeout(float(os.getenv("SUPABASE_HTTP_TIMEOUT_S", "20")), connect=5.0),
        # The limits belong to the transport: a client given its own transport ignores client-level limits.
        transport=_RetryStaleConnection(
            retries=2, limits=httpx.Limits(max_connections=50, max_keepalive_connections=20, keepalive_expiry=15.0),
        ),
    )


supabase: Client = create_client(
    SUPABASE_URL,
    SUPABASE_SECRET_KEY,
    options=SyncClientOptions(httpx_client=_http_client()),
)