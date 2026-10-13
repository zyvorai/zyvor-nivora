# Contributing

Run `./scripts/test.sh` before opening a pull request. Keep the dependency-free collector and web dashboard dependency-free unless a change has a strong operational reason. macOS-specific functionality must fail closed to observation-only when the relevant Apple entitlement or API is unavailable.

Do not add payload inspection, credential capture, argv/environment collection, or a remote command channel to the base product.
