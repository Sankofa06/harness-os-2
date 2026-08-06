# Deployment

## Local developer mode

Expected final commands (implementation may wrap these):
```bash
harness serve --host 127.0.0.1 --port 4096
harness tui --api http://127.0.0.1:4096
```

## Private-network phone access

Bind intentionally:
```bash
harness serve --host 0.0.0.0 --port 4096
```

Use Harness authentication. Prefer an HTTPS exposure method for browser access where possible.

## Remote machines

No clone required for agentless mode:
- enable/configure SSH,
- make LM/creative server reachable over the private network if desired,
- add Host and provider endpoint in Harness.

## Node mode

Optional:
```bash
harness-node start
```

Pair from Harness UI.

## GitHub Pages

Static site/client only. Use GitHub Actions from `site/`.

## Git

The implementation agent must:
```bash
git init
git add .
git commit -m "Build Harness OS"
```

If a remote exists and credentials are available:
```bash
git push -u origin <branch>
```
Otherwise leave the repo ready to push and document the exact command.
