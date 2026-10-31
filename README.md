# iPod Transfer

A small GTK 4 app for selecting or dragging audio files and copying them to the mounted volume labeled `IPOD`.

## Launch

From this folder:

```sh
python3 ipod-transfer.py
```

Requires Python 3 and GTK 4 with GObject introspection (`python-gobject`). On Omarchy/Arch, these components are normally provided by the `gtk4` and `python-gobject` packages.

## Important for 5th-generation iPods

Files are copied to `iPod_Control/Music/F00` and remain on the disk. This alone does **not** update the iPod's iTunes database, so new tracks may not appear in the Music menu or be playable. The app displays this note after a transfer; syncing the library requires an iPod/libgpod-compatible program. Always eject the volume from the file manager before disconnecting it.
