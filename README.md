# FreeRDP (HiDPI patched) — Flatpak

Rebuild of Flathub's [`com.freerdp.FreeRDP`](https://github.com/flathub/com.freerdp.FreeRDP)
with two changes:

1. **A patch so the remote desktop matches the physical panel on fractionally
   scaled Wayland outputs**, instead of coming up at the logical size.
2. **`-DWITH_FUSE:BOOL=ON`** plus `--device=all`, which is what makes clipboard
   *file* transfer (`/clipboard:files-to:all`) work. Flathub builds it off.

Nothing is pinned: CI clones the current Flathub manifest on each run, so this
follows whatever FreeRDP release upstream ships.

## The bug

FreeRDP's SDL3 client is HiDPI-aware where it draws — it blits 1:1 into device
pixels via `SDL_GetWindowSizeInPixels()`, so output is pixel-perfect. But it
takes the *requested desktop size* and the *DPI* from `FreeRDP_MonitorDefArray`,
which `sdl_monitor.cpp` enumerates through **unmapped dummy windows**
(`SdlWindow::query()` → `createDummy()`).

`wp_fractional_scale_v1` is a **per-surface** protocol. An unmapped surface never
receives the compositor's preferred fractional scale, and `wl_output` only
advertises an integer scale. So the monitor definition ends up with the logical
size and `desktopScaleFactor = 100`.

On a 3840×2160 output at scale 1.5 that means:

| | value |
|---|---|
| real window, mapped | `3840x2160 {2560x1440}{scale=1.500000}` |
| monitor def (dummy) | `2560x1440`, `desktopScaleFactor 100` |
| result | sharp, but covering 2/3 of each axis, Windows at 100% DPI |

Forcing `/size:3840x2160` does not help: `/f` and `/monitors:` re-derive from the
monitor def, and the server then maps the surface scaled
(`MapSurfaceToScaledOutput: targetWidth: 2560`), which is worse — a 4K desktop
downscaled into the same 2/3 region.

## The fix

`patches/0001-sdl3-size-desktop-from-mapped-window.patch` takes both the size and
the DPI from the **mapped** window in `sdlDispContext::sendLayout()`:

* size from `SdlWindow::rect()` → `SDL_GetWindowSizeInPixels()`
* DPI from `SdlWindow::scale()` → `SDL_GetWindowDisplayScale()`, clamped to the
  `[100, 500]` range MS-RDPBCGR 2.2.1.3.2 allows

So the scale is **auto-derived from whichever monitor the session is on** rather
than hardcoded. An explicit `/scale-desktop:` still wins, via the existing
`MonitorOverrideFlags` handling. Delivery is the DisplayControl channel, so
**`/dynamic-resolution` is required** for it to take effect.

Scoped to the single-monitor case; `/multimon` would need a per-monitor window
lookup and is deliberately untouched.

## Install

```sh
flatpak remote-add --user --no-gpg-verify freerdp-hidpi \
  https://napanto.github.io/freerdp-hidpi-flatpak/
flatpak install --user freerdp-hidpi com.freerdp.FreeRDP
```

The repo is unsigned — CI has no signing key, so `--no-gpg-verify` is required.
(Git commits in this repo *are* GPG-signed; the OSTree repo is not.)

Each run also uploads a `.flatpak` bundle as a workflow artifact if you would
rather install a single file.

## Upstreaming

Not submitted upstream yet. The diagnosis and the diff are both in this repo, so
the patch should be presentable to FreeRDP roughly as-is.
