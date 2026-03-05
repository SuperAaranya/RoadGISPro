#!/usr/bin/env python3
import argparse
import json
import os
import platform
import shutil
from datetime import datetime


DEFAULTS = {
    "allow_rust_router": True,
    "allow_javascript_metrics": True,
    "allow_go_metrics": True,
    "allow_csharp_metrics": True,
    "allow_ruby_metrics": False,
    "allow_java_metrics": False,
    "allow_rust_validator": True,
    "allow_go_validator": True,
    "allow_plugins": True,
}

TOKEN_MAP = {
    "rust_router": "allow_rust_router",
    "js_metrics": "allow_javascript_metrics",
    "go_metrics": "allow_go_metrics",
    "csharp_metrics": "allow_csharp_metrics",
    "ruby_metrics": "allow_ruby_metrics",
    "java_metrics": "allow_java_metrics",
    "rust_validator": "allow_rust_validator",
    "go_validator": "allow_go_validator",
    "plugins": "allow_plugins",
}


def parse_selected_languages(raw):
    if not raw:
        return set(TOKEN_MAP.keys())
    selected = set()
    for token in raw.split(","):
        t = token.strip().lower()
        if t in TOKEN_MAP:
            selected.add(t)
    return selected


def toolchain_report():
    return {
        "go": bool(shutil.which("go")),
        "cargo": bool(shutil.which("cargo")),
        "dotnet": bool(shutil.which("dotnet")),
        "node": bool(shutil.which("node")),
        "ruby": bool(shutil.which("ruby")),
        "java": bool(shutil.which("java")),
        "python": bool(shutil.which("python") or shutil.which("python3")),
    }


def build_config(selected_tokens):
    cfg = dict(DEFAULTS)
    for token, key in TOKEN_MAP.items():
        cfg[key] = token in selected_tokens
    return cfg


def main():
    parser = argparse.ArgumentParser(description="RoadGIS polyglot setup")
    parser.add_argument("--languages", default="", help="Comma-separated language/features tokens")
    parser.add_argument("--write-config", default="", help="Path to runtime_config.json")
    args = parser.parse_args()

    selected = parse_selected_languages(args.languages)
    config = build_config(selected)
    report = {
        "ok": True,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "os": platform.system(),
        "selected": sorted(selected),
        "config": config,
        "toolchains": toolchain_report(),
    }
    if args.write_config:
        os.makedirs(os.path.dirname(os.path.abspath(args.write_config)), exist_ok=True)
        with open(args.write_config, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)
        report["config_written_to"] = os.path.abspath(args.write_config)

    print(json.dumps(report))


if __name__ == "__main__":
    main()
