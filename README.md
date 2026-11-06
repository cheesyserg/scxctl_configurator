# scxctl_configurator

A small Qt front-end for configuring the active [scx](https://github.com/sched-ext/scx)
scheduler through `scxctl`.

Modes and their arguments are **not** bundled: the list is queried from
`scxctl modes --show-args`, so it always reflects your `scx_loader` configuration
rather than a hardcoded table.

## Requirements

- A running `scx_loader` daemon, reachable over the system D-Bus
  (the same access `scxctl` itself needs).
- `scxctl` on `PATH`.
- PySide6.

## Running it

``pip install PySide6``

``python3 scxctl_configurator.py``

## Applying a profile at boot

The **Set at boot** button writes `/etc/systemd/system/scx-profile.service`
from the current scheduler/mode/arguments selection, enables it, and restarts
it so the profile is applied immediately. At boot it runs `scxctl start` after
`scx_loader` is available:

```ini
[Unit]
Description=Apply the configured scx scheduler at boot
After=scx_loader.service dbus.service
Wants=scx_loader.service

[Service]
Type=oneshot
RemainAfterExit=yes
ExecStartPre=-/usr/bin/scxctl stop
ExecStart=/usr/bin/scxctl start --sched bpfland "--args=-m performance -w"
ExecStop=-/usr/bin/scxctl stop

[Install]
WantedBy=multi-user.target
```

The selected mode's resolved arguments are written directly (`--args=`), so
the boot unit does not depend on the loader still exposing a mode by that
name. `ExecStartPre` stops any scheduler that is already running, because
`scxctl start` refuses to replace one.

Writing and enabling the unit needs root, so the GUI prompts through `pkexec`
(or `sudo`). Use **Disable boot** to remove the unit and disable it, or run:

``sudo systemctl disable --now scx-profile.service``

## Building a standalone binary

``pyinstaller --onefile --windowed scxctl_configurator.py``
