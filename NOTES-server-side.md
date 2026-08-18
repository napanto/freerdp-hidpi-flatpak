# The other half: patching a Linux RDP *server*

The patch in `patches/` fixes the **client**. Everything below is the server-side
counterpart, written down because it is only worth doing against a Linux/Wayland
RDP server (gnome-remote-desktop, Weston's RDP backend, FreeRDP shadow) — a
Windows server cannot benefit, for a reason that is structural rather than a bug.

## Why the server side matters

RDP describes monitors in **device pixels**, with `DesktopScaleFactor` as a
separate per-monitor hint. Windows uses that hint only as a per-window DPI
setting on a pixel-addressed desktop; it has no logical coordinate space to put
the monitors in. A Wayland compositor *does*, so it can take (pixel size + scale)
and reconstruct a real output — recovering information the protocol flattened.

## What is already there

* FreeRDP's server parses the per-monitor scale — `channels/disp/server/disp_main.c`:

      Stream_Read_UINT32(s, monitor->DesktopScaleFactor);
      Stream_Read_UINT32(s, monitor->DeviceScaleFactor);

* Weston's RDP backend already uses it — `libweston/backend-rdp/rdpdisp.c`:

      scale = config->attributes.desktopScaleFactor / 100;
      scale = scale ? scale : 1;

## What needs patching

1. **Weston truncates fractional scales.** That `/ 100` is integer division, so
   150 becomes 1 and a 1.5-scaled monitor arrives unscaled (correct pixels, tiny
   UI). 200 → 2 works, so integer scales are fine. Not a one-liner: libweston's
   output scale is an `int`, so real support means fractional output scale in the
   compositor, not just in the RDP backend.

2. **The client sends nonsense physical sizes.** `PhysicalWidth`/`PhysicalHeight`
   are millimetres in the protocol (valid 10..10000, see
   `DISPLAY_CONTROL_MIN/MAX_PHYSICAL_MONITOR_WIDTH`). FreeRDP's SDL client fills
   them with pixel counts — we observed `PhysicalWidth: 3840 PhysicalHeight: 2160`
   going out, i.e. a claimed 3.8 m wide monitor. They pass the range check, so
   nothing complains. Fixing this needs a physical-size source: SDL3 exposes none
   (`SDL_GetDisplayBounds`, `ContentScale`, `Name`, `Properties`, `UsableBounds` —
   no millimetres), so it means an SDL addition or reading `wl_output.geometry`
   directly.

3. **Then the server can reconstruct instead of replay.** Given per-monitor pixel
   size, true millimetres and the scale, a compositor can lay its outputs out
   physically correctly in its own logical space, using the client's pixel
   positions only as a topology hint (who is left/right/above/below). That would
   remove the position drift entirely — see below.

## What cannot be patched

`Left`/`Top` in the monitor layout are device pixels in one shared coordinate
space. With mixed densities no assignment of those values is physically
continuous: the same physical span needs a different number of pixels on each
monitor, so the mismatch grows linearly across a shared edge whatever offset is
chosen. Measured on the apollo layout (4K@1.5 primary, 1440p@1.0 above it): the
best convention still drifts **±559 logical px** at the extremes, which is why the
client aligns the *centres* of shared edges — it halves the worst case and puts
zero error where the pointer usually crosses.

Only a protocol change — positions in a density-independent unit — fixes that at
the source. Against a Windows server it is permanent. Against a Wayland server
item 3 above sidesteps it, because the server stops replaying the client's pixel
geometry and rebuilds it.
