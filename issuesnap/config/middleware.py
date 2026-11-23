"""
IssueSnap Custom Middleware
"""


class ReferrerPolicyMiddleware:
    """
    Adds the HTTP Referrer-Policy response header to every page.

    Why this is needed:
    OpenStreetMap's tile usage policy requires that web applications send a
    valid HTTP Referer header when requesting tiles from tile.openstreetmap.org.
    Without an explicit Referrer-Policy, some browsers (especially on localhost
    or when navigating from HTTPS → HTTP contexts) suppress the Referer header,
    causing OSM's servers to return 403 "Access Blocked" tiles.

    The value 'strict-origin-when-cross-origin':
    - Sends the full URL as Referer for same-origin requests.
    - Sends only the origin (scheme + host) as Referer for cross-origin
      requests such as tile downloads — this satisfies OSM's requirement.
    - Sends nothing when navigating from HTTPS to HTTP (security-safe).

    This is the browser default in modern Chrome/Firefox, but setting it
    explicitly overrides any more-restrictive policy that could have been
    inherited from SecurityMiddleware or other layers.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        # Only set if not already present (don't override a stricter policy
        # intentionally set elsewhere).
        if 'Referrer-Policy' not in response:
            response['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        return response
