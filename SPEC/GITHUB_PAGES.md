# GitHub Pages Strategy

GitHub Pages is static hosting and MUST NOT pretend to host the Harness runtime.

## Deliverables

`site/` contains:
- product landing page,
- docs/getting-started links,
- screenshots,
- architecture overview,
- optional static remote-client build.

## Remote client behavior

A static Pages client MAY let the user enter an HTTPS Harness API endpoint.

Constraints:
- browser mixed-content restrictions mean an HTTPS Pages site cannot call arbitrary plain-HTTP local endpoints.
- recommended remote configuration is an HTTPS endpoint exposed by the user's secure network/reverse proxy (for example Tailscale Serve, user-managed TLS, or another HTTPS gateway).
- credentials are stored only in session memory or a secure user-approved browser mechanism; never committed.

The primary reliable phone path remains:
- Harness WebUI served directly by Harness API/server over the user's secure network.

## GitHub Actions

On main:
- test
- build web
- build docs/site
- deploy Pages
