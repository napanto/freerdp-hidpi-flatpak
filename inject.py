#!/usr/bin/env python3
"""Inject the HiDPI patch into the upstream Flathub manifest.

Run against a freshly cloned flathub/com.freerdp.FreeRDP checkout so we always
track the latest upstream FreeRDP release rather than pinning one ourselves.
"""
import json
import sys

PATCH = "patches/0001-sdl3-size-desktop-from-mapped-window.patch"

def main(path: str) -> int:
    with open(path) as fh:
        manifest = json.load(fh)

    for module in manifest["modules"]:
        if not isinstance(module, dict) or module.get("name") != "freerdp":
            continue

        # 1. our patch, applied on top of the upstream release tarball
        sources = module.setdefault("sources", [])
        if not any(s.get("path") == PATCH for s in sources if isinstance(s, dict)):
            sources.append({"type": "patch", "path": PATCH})

        # 2. FUSE is what makes clipboard *file* transfer work
        opts = module.setdefault("config-opts", [])
        module["config-opts"] = [
            "-DWITH_FUSE:BOOL=ON" if o == "-DWITH_FUSE:BOOL=OFF" else o for o in opts
        ]
        if "-DWITH_FUSE:BOOL=ON" not in module["config-opts"]:
            module["config-opts"].append("-DWITH_FUSE:BOOL=ON")
        break
    else:
        print("error: no 'freerdp' module in manifest", file=sys.stderr)
        return 1

    # 3. sandbox needs /dev/fuse for the clipboard FUSE mount, and $HOME for /drive
    finish = manifest.setdefault("finish-args", [])
    for arg in ("--device=all", "--filesystem=home"):
        if arg not in finish:
            finish.append(arg)

    with open(path, "w") as fh:
        json.dump(manifest, fh, indent=4)
        fh.write("\n")

    print(f"patched {path}: +{PATCH}, WITH_FUSE=ON, +--device=all +--filesystem=home")
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
