#!/usr/bin/env python3
# SPDX-License-Identifier: BUSL-1.1
"""Generate the nivoractl(1) man page from the CLI's argparse definition. usage: build-man.py [OUT]"""
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "agent"))
import nivoractl  # noqa: E402


def esc(text):
    return str(text).replace("\\", "\\\\").replace("-", "\\-")


def render():
    parser = nivoractl.build_parser()
    out = [f'.TH NIVORACTL 1 "{date.today():%Y-%m-%d}" "Nivora {esc(nivoractl.VERSION)}"', ".SH NAME",
           "nivoractl \\- command line client for the local Nivora collector", ".SH SYNOPSIS",
           ".B nivoractl\n[\\fIOPTIONS\\fR] \\fICOMMAND\\fR [\\fIARGS\\fR]", ".SH DESCRIPTION",
           "Talks to the Nivora collector API on loopback (default http://127.0.0.1:9857) and prints the result.",
           "Output is JSON, or a table for apps and flows; use \\-\\-json for compact JSON everywhere.", ".SH OPTIONS"]
    for a in parser._actions:
        if a.option_strings and a.dest != "help":
            out += [".TP", ".B " + esc(", ".join(a.option_strings)), esc(a.help or "")]
    out.append(".SH COMMANDS")
    helps = {ca.dest: ca.help for act in parser._actions
             if isinstance(act, nivoractl.argparse._SubParsersAction) for ca in act._choices_actions}
    for name, sp in nivoractl.subcommands(parser).items():
        out += [".TP", ".B " + esc(name), esc(helps.get(name) or "")]
        for a in sp._actions:
            if a.option_strings and a.dest != "help":
                out.append(f".br\n\\fB{esc(a.option_strings[0])}\\fR  {esc(a.help or '')}".rstrip())
    out += [".SH ENVIRONMENT", ".TP", ".B NIVORA_URL", "Collector base URL.", ".TP", ".B NIVORA_TOKEN",
            "Bearer token. Without it the token is read from the login Keychain.", ".SH SEE ALSO",
            "https://zyvorai.github.io/zyvor-nivora/"]
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    text = render()
    if len(sys.argv) > 1:
        Path(sys.argv[1]).parent.mkdir(parents=True, exist_ok=True)
        Path(sys.argv[1]).write_text(text)
        print(sys.argv[1])
    else:
        sys.stdout.write(text)
