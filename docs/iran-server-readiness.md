# Iran server readiness

Configure the VPS at purchase time with:

- Region: Iran
- OS: Ubuntu 24.04 LTS preferred (Ubuntu 22.04 and Debian 12 supported)
- Architecture: x86_64
- Public IPv4 and inbound TCP 22
- Outbound TCP 443
- The controller public SSH key injected during server creation
- Root access or passwordless sudo

Minimum sizing for the bounded IRMA bootstrap and local PostgreSQL validation is 1 vCPU, 1 GB RAM,
and 10 GB disk. Recommended sizing is 2 vCPU, 2 GB RAM, and 20 GB disk. A larger host is not
needed for this validation workload.

Before purchase, inspect local readiness and the key to inject:

```bash
python scripts/iran_live_validator.py --doctor
python scripts/iran_live_validator.py --show-public-key
```

The validator never generates or copies a private key. After the provider has installed the
reported public key, validation needs only:

```bash
./scripts/validate_from_iran.sh SERVER_IP
```

An alternate Git ref or immutable SHA may be supplied as the second argument.
