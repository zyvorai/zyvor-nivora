# Security

Nivora is local-first. The collector binds to loopback by default, `/v1/*` uses a bearer token, and the macOS installer stores that token in Login Keychain. Do not bind Nivora to a non-loopback address without an authenticated TLS reverse proxy.

The browser keeps the token in JavaScript memory only. The convenience URL uses a URL fragment (`#token=...`), which is not sent in the HTTP request; the page removes it after reading it.

The base collector runs read-only commands (`nettop`, `lsof`, `ifconfig`, `netstat`, `scutil`). It does not require root. Rule mutations only update Nivora's local rule file. Actual traffic blocking occurs only through the signed NetworkExtension when the user enables it.

Nivora does not intentionally collect application payloads, command-line arguments, environment variables, credentials, browser content or packet bodies.

Report security issues privately through the contact route at https://zyvor.dev.
