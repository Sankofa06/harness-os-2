# Security, Privacy, and Permissions

## Network

Default bind: `127.0.0.1`.
User may explicitly bind `0.0.0.0` or another interface.

Remote use requires Harness authentication even over Tailscale/VPN.

Prefer HTTPS for browser clients when feasible. Document Tailscale Serve/reverse-proxy patterns without making Tailscale mandatory.

## Secrets

Backends:
1. OS keychain/keyring
2. encrypted local secret file if configured
3. environment variable reference

Never persist raw API keys in:
- SQLite rows,
- YAML configs,
- logs,
- events,
- screenshots,
- seeded demo data.

## Permissions

Classes:
- read
- write
- execute
- network
- git
- process
- model_lifecycle
- creative_generation
- training
- destructive

Policies:
- allow
- ask
- deny

Permission resolution is explicit and logged.

## Remote execution

- constrain to configured roots,
- canonicalize paths,
- use structured argv where possible,
- never interpolate secrets into shell commands,
- no implicit privilege escalation.

## Web client

- CSP
- no secrets in localStorage
- CSRF protection for cookie auth or bearer-token design with equivalent protections
- session timeout
- origin restrictions configurable
- sanitize rendered model/tool content.

## Local telemetry

No external telemetry by default.
A future opt-in crash/usage system must be separately specified.
