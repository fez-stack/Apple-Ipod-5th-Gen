#!/usr/bin/env python3
"""A small file transfer utility for FAT-formatted iPods."""
import os
import shutil
import threading
from pathlib import Path

import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk, Gio, GLib


APP_ID = "local.ipod.Transfer"
AUDIO = {".mp3", ".m4a", ".m4b", ".aac", ".wav", ".aif", ".aiff", ".ogg", ".flac"}


def find_ipod():
    """Return a mounted volume named IPOD, checking desktop and common mounts."""
    monitor = Gio.VolumeMonitor.get()
    for mount in monitor.get_mounts():
        root = mount.get_root()
        path = root.get_path() if root else None
        name = mount.get_name() or ""
        if path and name.strip().upper() == "IPOD":
            return Path(path)
    user = os.environ.get("USER", "")
    for base in (Path("/run/media") / user, Path("/media") / user, Path("/mnt")):
        for candidate in (base / "IPOD",):
            if candidate.is_dir():
                return candidate
        if base.is_dir():
            try:
                for candidate in base.iterdir():
                    if candidate.is_dir() and candidate.name.upper() == "IPOD":
                        return candidate
            except OSError:
                pass
    return None


class TransferWindow(Gtk.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app, title="iPod Transfer")
        self.set_default_size(680, 610)
        self.set_resizable(False)
        self.files = []
        self.device = None
        self._style()

        outer = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)
        outer.add_css_class("window-card")
        self.set_child(outer)
        header = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
        header.set_margin_top(28); header.set_margin_start(32); header.set_margin_end(32)
        icon = Gtk.Label(label="♫"); icon.add_css_class("brand-icon")
        header.append(icon)
        names = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
        title = Gtk.Label(label="iPod Transfer", xalign=0); title.add_css_class("title")
        subtitle = Gtk.Label(label="Your music, back in your pocket.", xalign=0); subtitle.add_css_class("subtle")
        names.append(title); names.append(subtitle); header.append(names)
        outer.append(header)

        content = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        content.set_margin_top(28); content.set_margin_start(32); content.set_margin_end(32)
        outer.append(content)
        self.device_card = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=14)
        self.device_card.add_css_class("device-card"); self.device_card.set_margin_bottom(4)
        disk = Gtk.Label(label="▣"); disk.add_css_class("disk-icon")
        self.device_card.append(disk)
        info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=4)
        self.device_name = Gtk.Label(xalign=0); self.device_name.add_css_class("device-title")
        self.device_path = Gtk.Label(xalign=0); self.device_path.add_css_class("subtle")
        info.append(self.device_name); info.append(self.device_path); self.device_card.append(info)
        self.device_status = Gtk.Label(); self.device_card.append(self.device_status)
        content.append(self.device_card)

        row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        section = Gtk.Label(label="FILE DA TRASFERIRE", xalign=0); section.add_css_class("eyebrow")
        row.append(section)
        self.count = Gtk.Label(label="0 items"); self.count.add_css_class("subtle")
        row.append(self.count); content.append(row)

        self.drop = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=9)
        self.drop.add_css_class("drop-zone"); self.drop.set_vexpand(True)
        music = Gtk.Label(label="♫"); music.add_css_class("music-icon")
        self.drop.append(music)
        self.drop_title = Gtk.Label(label="Drop tracks here"); self.drop_title.add_css_class("drop-title")
        self.drop.append(self.drop_title)
        self.drop_hint = Gtk.Label(label="or choose files from your computer"); self.drop_hint.add_css_class("subtle")
        self.drop.append(self.drop_hint)
        self.file_list = Gtk.Label(label="No files selected", xalign=0, wrap=True)
        self.file_list.add_css_class("file-list"); self.drop.append(self.file_list)
        content.append(self.drop)
        target = Gtk.DropTarget.new(Gio.File, GdkAction.COPY)
        target.connect("drop", self.on_drop)
        self.drop.add_controller(target)

        actions = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
        self.choose_btn = Gtk.Button(label="Choose files…"); self.choose_btn.add_css_class("secondary")
        self.choose_btn.connect("clicked", self.choose_files); actions.append(self.choose_btn)
        self.transfer_btn = Gtk.Button(label="Transfer to iPod  →"); self.transfer_btn.add_css_class("suggested-action")
        self.transfer_btn.set_hexpand(True); self.transfer_btn.connect("clicked", self.transfer); actions.append(self.transfer_btn)
        content.append(actions)

        self.progress = Gtk.ProgressBar(show_text=True); self.progress.set_visible(False); content.append(self.progress)
        self.status = Gtk.Label(label="Audio files will be copied to the iPod's Music folder.", xalign=0)
        self.status.add_css_class("subtle"); self.status.set_wrap(True); content.append(self.status)
        footer = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        footer.set_margin_top(5)
        foot = Gtk.Label(label="iPod 5th generation  ·  FAT32  ·  80 GB", xalign=0); foot.add_css_class("footer")
        footer.append(foot)
        refresh = Gtk.Button(label="Refresh device"); refresh.add_css_class("flat")
        refresh.connect("clicked", lambda *_: self.refresh_device()); footer.append(refresh)
        content.append(footer)
        self.refresh_device()

    def _style(self):
        css = b"""
        window { background: #111318; color: #f2f3f7; }
        .window-card { background: #111318; }
        label { color: #f2f3f7; }
        .title { font-size: 24px; font-weight: 700; }
        .subtle { color: #a2a8b5; font-size: 13px; }
        .brand-icon { background: #8b7cff; color: #111318; border-radius: 12px; padding: 7px 13px; font-size: 25px; font-weight: 800; }
        .device-card { background: #1c2028; border: 1px solid #2e3440; border-radius: 14px; padding: 15px; }
        .disk-icon { color: #a99dff; font-size: 24px; padding: 3px 8px; }
        .device-title { font-weight: 700; font-size: 15px; }
        .eyebrow { color: #969cac; font-size: 11px; font-weight: 800; letter-spacing: 1px; }
        .drop-zone { background: #191c24; border: 1px dashed #4a5060; border-radius: 16px; padding: 18px; }
        .music-icon { color: #a99dff; font-size: 30px; }
        .drop-title { font-size: 17px; font-weight: 700; }
        .file-list { color: #c9cbd3; font-size: 12px; }
        button { border-radius: 10px; padding: 10px 14px; font-weight: 650; }
        .suggested-action { background: #a99dff; color: #171522; }
        .suggested-action:hover { background: #b9b0ff; }
        .secondary { background: #252a34; color: #f2f3f7; }
        .footer { color: #727987; font-size: 11px; }
        progressbar trough { min-height: 8px; background: #292e39; border-radius: 10px; }
        progressbar progress { background: #a99dff; border-radius: 10px; }
        """
        provider = Gtk.CssProvider(); provider.load_from_data(css)
        Gtk.StyleContext.add_provider_for_display(GdkDisplay.get_default(), provider, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

    def refresh_device(self):
        self.device = find_ipod()
        if self.device:
            self.device_name.set_text("iPod 80 GB · Connected")
            self.device_path.set_text(str(self.device))
            self.device_status.set_text("●  Ready"); self.device_status.add_css_class("success")
            self.transfer_btn.set_sensitive(bool(self.files))
            self.status.set_text("Audio files will be copied to iPod_Control/Music.")
        else:
            self.device_name.set_text("iPod not mounted")
            self.device_path.set_text("Connect the iPod and wait for the IPOD volume to mount.")
            self.device_status.set_text("○  Offline")
            self.transfer_btn.set_sensitive(False)
            self.status.set_text("The IPOD disk was detected but isn't mounted. Mount it in your file manager, then click Refresh device.")

    def choose_files(self, *_):
        dialog = Gtk.FileChooserNative(title="Choose audio files", transient_for=self, action=Gtk.FileChooserAction.OPEN, accept_label="Add", cancel_label="Cancel")
        dialog.set_select_multiple(True)
        filt = Gtk.FileFilter(); filt.set_name("Audio files");
        for ext in AUDIO: filt.add_pattern("*" + ext)
        dialog.add_filter(filt)
        dialog.connect("response", self.on_file_response)
        dialog.show()

    def on_file_response(self, dialog, response):
        if response == Gtk.ResponseType.ACCEPT:
            self.set_files([f.get_path() for f in dialog.get_files() if f.get_path()])
        dialog.destroy()

    def on_drop(self, _target, value, _x, _y):
        paths = [value.get_path()] if value.get_path() else []
        if paths: self.set_files(paths)
        return bool(paths)

    def set_files(self, paths):
        self.files = [Path(p) for p in paths if Path(p).is_file() and Path(p).suffix.lower() in AUDIO]
        self.count.set_text(f"{len(self.files)} items")
        self.file_list.set_text("\n".join(f"♫  {p.name}" for p in self.files[:5]) + (f"\n… and {len(self.files)-5} more" if len(self.files) > 5 else "") if self.files else "No audio files selected")
        self.transfer_btn.set_sensitive(bool(self.files) and self.device is not None)

    def transfer(self, *_):
        self.refresh_device()
        if not self.device or not self.files: return
        dest = self.device / "iPod_Control" / "Music" / "F00"
        try: dest.mkdir(parents=True, exist_ok=True)
        except OSError as e:
            self.status.set_text(f"Couldn't write to the iPod: {e}"); return
        self.transfer_btn.set_sensitive(False); self.choose_btn.set_sensitive(False)
        self.progress.set_visible(True); self.progress.set_fraction(0); self.progress.set_text("Preparing…")
        files = list(self.files)
        def worker():
            errors = []; copied = 0
            for i, source in enumerate(files):
                try:
                    target = dest / source.name
                    if target.exists():
                        stem, suffix, n = source.stem, source.suffix, 2
                        while (dest / f"{stem} ({n}){suffix}").exists(): n += 1
                        target = dest / f"{stem} ({n}){suffix}"
                    shutil.copy2(source, target); copied += 1
                except OSError as e: errors.append(f"{source.name}: {e}")
                GLib.idle_add(self.update_progress, (i + 1) / len(files), i + 1, len(files))
            GLib.idle_add(self.finish_transfer, copied, errors, dest)
        threading.Thread(target=worker, daemon=True).start()

    def update_progress(self, fraction, done, total):
        self.progress.set_fraction(fraction); self.progress.set_text(f"{done} / {total}")
        return GLib.SOURCE_REMOVE

    def finish_transfer(self, copied, errors, dest):
        self.transfer_btn.set_sensitive(bool(self.files) and self.device is not None)
        self.choose_btn.set_sensitive(True)
        self.status.set_text(f"Copied {copied} files to {dest}." + (f" Errors: {'; '.join(errors[:2])}" if errors else ""))
        self.progress.set_text("Complete"); self.refresh_device()
        self.status.set_text(f"Copied {copied} files to iPod_Control/Music/F00." + (f" Errors: {'; '.join(errors[:2])}" if errors else "") + " Note: to show them in the iPod's Music menu, the iTunesDB database must be updated.")
        return GLib.SOURCE_REMOVE


from gi.repository import Gdk
GdkAction = Gdk.DragAction
GdkDisplay = Gdk.Display

class Application(Gtk.Application):
    def __init__(self): super().__init__(application_id=APP_ID, flags=Gio.ApplicationFlags.DEFAULT_FLAGS)
    def do_activate(self):
        window = self.props.active_window or TransferWindow(self)
        window.present()

if __name__ == "__main__":
    raise SystemExit(Application().run())
