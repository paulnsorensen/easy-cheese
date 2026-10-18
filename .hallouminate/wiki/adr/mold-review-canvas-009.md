# ADR: Reach the review canvas over Tailscale through tailscale serve

Status: accepted (2026-10-17). Amends [mold-review-canvas-007](./mold-review-canvas-007.md).

## Context

The review server binds `127.0.0.1` and accepts only `Host: 127.0.0.1:<port>`.
A user on another tailnet device cannot open the canvas.
`tailscale serve` forwards the original `*.ts.net` Host and sets `X-Forwarded-Proto: https` over TLS ([`ipn/ipnlocal/serve.go` in the tailscale/tailscale repository](https://github.com/tailscale/tailscale/blob/main/ipn/ipnlocal/serve.go)).
The browser then sends an `https://` Origin, so the old checks reject every proxied request.

## Decision

`review serve --trusted-host NODE.TAILNET.ts.net` opts in to one tailnet name.
The server still binds loopback only and never runs `tailscale serve` itself.
It accepts that host, with any port, only with `X-Forwarded-Proto: https` and the matching `https://` Origin.
It refuses every request that carries `Tailscale-Funnel-Request`, so a Funnel mapping never exposes the canvas.
The launch token stays mandatory, and the cookie gains `Secure` on the trusted host.
The launch output adds `remote_url` and a `tailscale_serve` command for the user to run.

## Alternatives

- Bind the 100.x tailnet address. Every tailnet peer reaches the port over plain HTTP with no identity headers and no `Secure` cookie.
- Keep the SSH tunnel only. It works but needs the same port on both ends and an SSH session.
- Run `tailscale serve` from the archive. That makes an external executable part of the runtime, which the bundle doctrine prohibits.

## Consequences

The tailnet needs MagicDNS and HTTPS certificates, and the node name appears in public certificate logs.
The printed command replaces an existing HTTPS mapping on port 443; the reference tells the user to pick another port when one exists.
Identity headers such as `Tailscale-User-Login` are not checked; a login allowlist stays open.

## Related records

- [Keep the local review transport bounded](./mold-review-canvas-007.md)
- [Skill Python bundle doctrine](../architecture/skill-python-bundle-doctrine.md)

_Source: `src/easy_cheese/skills/mold/review.py`, `skills/mold/references/review-canvas.md`, and research slug `mold-review-canvas-tailscale-access` · Updated: 2026-10-17_
