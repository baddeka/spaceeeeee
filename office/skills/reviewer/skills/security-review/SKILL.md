---
name: security-review
description: Use when the change handles user input, files, shell commands, network, auth, secrets, or serialization. A checklist of security defects to look for.
---

# Security review

For each item, trace a real path from an input the code receives to the dangerous operation. Report only paths that exist.

- **Injection:** user data reaching SQL, shell (`subprocess` with `shell=True`, `os.system`, backticks), `eval`/`exec`, templates, or HTML without escaping or parameters.
- **Paths:** user-controlled paths reaching file reads or writes without resolving and checking they stay inside the allowed directory (`../`, absolute paths, symlinks).
- **Secrets:** keys, tokens, or passwords in code, logs, error messages, or committed config.
- **Deserialization:** `pickle`, `yaml.load` without a safe loader, or similar on untrusted data.
- **Auth and access:** endpoints or actions missing a permission check; checks done on the client only.
- **Network:** requests to user-supplied URLs (SSRF), disabled TLS verification, missing timeouts.
- **Resource use:** unbounded reads, loops, or uploads that a single request can make huge.

Rate a reachable injection, path traversal, or secret leak as critical.
