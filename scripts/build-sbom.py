#!/usr/bin/env python3
# SPDX-License-Identifier: BUSL-1.1
"""Write a CycloneDX 1.5 SBOM for the release (stdlib only).

Nivora ships no third-party runtime dependencies: the collector is Python stdlib and the web UI
is dependency-free. The SBOM records the application and its build-time tools by name only.
"""
import json
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def build():
    pkg = json.loads((ROOT / "package.json").read_text())
    return {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": f"urn:uuid:{uuid.uuid4()}",
        "version": 1,
        "metadata": {
            "component": {
                "type": "application",
                "name": pkg["name"],
                "version": pkg["version"],
                "licenses": [{"license": {"id": "BUSL-1.1"}}],
            }
        },
        "components": [],
    }


if __name__ == "__main__":
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "sbom.cdx.json"
    out.write_text(json.dumps(build(), indent=2) + "\n")
    print(out)
