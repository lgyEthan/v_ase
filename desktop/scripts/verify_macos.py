"""Verify every native component, not just the outer Electron signature."""
import argparse
import json
import os
from pathlib import Path
import plistlib
import subprocess


def command(*args):
    return subprocess.run(args, check=True, capture_output=True, text=True)


def verify(app, team, notarized=False):
    app = app.resolve(strict=True)
    with (app / "Contents/Info.plist").open("rb") as stream:
        info = plistlib.load(stream)
    if info["CFBundleIdentifier"] != "org.v-ase.desktop":
        raise ValueError("Not a v_ase desktop application")
    magic = {bytes.fromhex(value) for value in (
        "feedface", "cefaedfe", "feedfacf", "cffaedfe",
        "cafebabe", "bebafeca", "cafebabf", "bfbafeca",
    )}
    binaries = []
    for directory, _, names in os.walk(app):
        for name in names:
            item = Path(directory) / name
            if item.is_symlink():
                continue
            with item.open("rb") as stream:
                if stream.read(4) in magic:
                    binaries.append(item)
    if len(binaries) < 10:
        raise ValueError("Incomplete Electron/Python application")
    for item in [*binaries, app]:
        result = command("codesign", "--display", "--verbose=4", str(item))
        metadata = result.stdout + result.stderr
        for required in (f"TeamIdentifier={team}", "Authority=Developer ID Application:", "Timestamp=", "(runtime)"):
            if required not in metadata:
                raise ValueError(f"Missing {required!r} in {item.relative_to(app)}")
        command("codesign", "--verify", "--strict", str(item))
    command("codesign", "--verify", "--deep", "--strict", str(app))
    if list(app.rglob("*.pyc")):
        raise ValueError("Bytecode caches found in the sealed application")
    if notarized:
        command("xcrun", "stapler", "validate", str(app))
        assessment = command("spctl", "--assess", "--type", "execute", "--verbose=2", str(app))
        if "Notarized Developer ID" not in assessment.stderr + assessment.stdout:
            raise ValueError("Gatekeeper did not report Notarized Developer ID")
    return {
        "bundleId": info["CFBundleIdentifier"],
        "version": info["CFBundleShortVersionString"],
        "teamId": team,
        "nativeBinaries": len(binaries),
        "developerIdSignatures": "verified",
        "secureTimestamps": "verified",
        "hardenedRuntime": "verified",
        "bundleIntegrity": "verified",
        "bytecodeCaches": 0,
        "stapledTicketAndGatekeeper": "verified" if notarized else "not checked",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("app", type=Path)
    parser.add_argument("--team-id", required=True)
    parser.add_argument("--notarized", action="store_true", help="Also require a stapled ticket and Gatekeeper acceptance")
    args = parser.parse_args()
    print(json.dumps(verify(args.app, args.team_id, args.notarized), indent=2))
