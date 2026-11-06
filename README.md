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

## Building a standalone binary

``pyinstaller --onefile --windowed scxctl_configurator.py``
