#!/usr/bin/env python3
"""Inject the HiDPI patch into the upstream Flathub manifest.

Run against a freshly cloned flathub/com.freerdp.FreeRDP checkout so we always
track the latest upstream FreeRDP release rather than pinning one ourselves.
"""
import json
import sys

PATCHES = [
    "patches/0001-sdl3-size-desktop-from-mapped-window.patch",
    "patches/0002-sdl3-multimon-per-monitor-scale.patch",
]

# The freedesktop SDK ships no fuse3, which is why Flathub builds FreeRDP with
# WITH_FUSE=OFF. Build libfuse ourselves so clipboard file transfer can be
# enabled. -Duseroot=false keeps meson from trying to set setuid bits, which
# would fail inside the build sandbox.
FUSE_MODULE = {
    "name": "fuse3",
    "buildsystem": "meson",
    "builddir": True,
    "config-opts": [
        "-Dexamples=false",
        "-Dtests=false",
        "-Duseroot=false",
        "-Dinitscriptdir=",
    ],
    "sources": [
        {
            "type": "archive",
            "url": "https://github.com/libfuse/libfuse/releases/download/fuse-3.18.2/fuse-3.18.2.tar.gz",
            "sha256": "f01de85717e20adf5f98aff324acd85dd73d61a5ca3834d573dcf0bd6e54a298",
        }
    ],
    "cleanup": ["/share/man", "/etc/init.d", "/lib/udev"],
}

def main(path: str) -> int:
    with open(path) as fh:
        manifest = json.load(fh)

    names = [m.get("name") for m in manifest["modules"] if isinstance(m, dict)]
    idx = next(i for i, m in enumerate(manifest["modules"])
               if isinstance(m, dict) and m.get("name") == "freerdp")
    if "fuse3" not in names:
        manifest["modules"].insert(idx, FUSE_MODULE)

    for module in manifest["modules"]:
        if not isinstance(module, dict) or module.get("name") != "freerdp":
            continue

        # 1. our patch, applied on top of the upstream release tarball
        sources = module.setdefault("sources", [])
        have = {s.get("path") for s in sources if isinstance(s, dict)}
        for patch in PATCHES:
            if patch not in have:
                sources.append({"type": "patch", "path": patch})

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

    print(f"patched {path}: +fuse3 module, +{len(PATCHES)} patches, WITH_FUSE=ON, "
          "+--device=all +--filesystem=home")
    return 0

if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
