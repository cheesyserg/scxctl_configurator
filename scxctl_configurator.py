#!/usr/bin/env python3
"""Configure the active scx_loader scheduler through scxctl.

Presets are intentionally not bundled: the modes and arguments shown here come
from scx_loader's own configuration, queried via `scxctl modes --show-args`.
"""

import os
import re
import shlex
import shutil
import subprocess
import sys
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QIcon, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QStyle,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

SCXCTL = "scxctl"
NO_MODE = "Default (no mode)"
BOOT_UNIT = "scx-profile.service"
BOOT_UNIT_FILE = Path("/etc/systemd/system") / BOOT_UNIT
SYSTEMCTL = shutil.which("systemctl") or "/usr/bin/systemctl"
JOURNALCTL = shutil.which("journalctl") or "/usr/bin/journalctl"
SHELL = shutil.which("sh") or "/bin/sh"

# Lines such as "Modes:" or "Modes for bpfland:" are headers, not mode names.
_HEADER_RE = re.compile(r"^(?:modes?|configured|available|args?|arguments|scheduler|supported)\b", re.I)
_BULLET_RE = re.compile(r"^[-*\u2022]\s*")
_AUTH_RE = re.compile(
    r"authentication|password|not authorized|request dismissed|access denied|permission denied",
    re.I,
)


class ScxctlError(RuntimeError):
    """Raised when scxctl fails in a way the UI should report."""


def parse_modes(text):
    """Parse `scxctl modes` output into (mode_name, resolved_args) pairs.

    Tolerates both a bare list and a `name: args` / `name --args ...` layout,
    since the exact rendering differs between scxctl releases.
    """
    modes = []
    seen = set()

    for raw in text.splitlines():
        line = _BULLET_RE.sub("", raw.strip())
        if not line or line.startswith("#"):
            continue
        if line.endswith(":") and _HEADER_RE.match(line):
            continue

        name, sep, rest = line.partition(":")
        if sep:
            name, args = name.strip(), rest.strip()
        else:
            parts = line.split(None, 1)
            name = parts[0]
            args = parts[1].strip() if len(parts) > 1 else ""

        if not name or name.lower() in seen:
            continue

        args = re.sub(r"^--args\s*", "", args)
        if args.strip(" \"'") in ("", "-", "none", "None"):
            args = ""

        seen.add(name.lower())
        modes.append((name, args))

    return modes


def _result_message(result):
    return (result.stderr or result.stdout or "").strip()


def _combined_message(result):
    parts = [part.strip() for part in (result.stderr, result.stdout) if part and part.strip()]
    return "\n".join(parts)


def _systemd_quote(value):
    if value and not re.search(r"[\s\"'\\]", value):
        return value
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"') + '"'


def boot_unit_text(scheduler, args):
    """Build a oneshot unit that applies scheduler/profile at boot."""
    binary = shutil.which(SCXCTL)
    if not binary:
        raise ScxctlError(f"'{SCXCTL}' was not found on PATH.")

    exec_args = [binary, "start", "--sched", scheduler]
    if args:
        # scxctl rejects "--args VALUE" when VALUE starts with "-", so keep
        # the whole thing in one argv token.
        exec_args.append(f"--args={args}")
    exec_line = " ".join(_systemd_quote(arg) for arg in exec_args)
    binary = _systemd_quote(binary)
    return (
        "[Unit]\n"
        "Description=Apply the configured scx scheduler at boot\n"
        "After=scx_loader.service dbus.service\n"
        "Wants=scx_loader.service\n"
        "\n"
        "[Service]\n"
        "Type=oneshot\n"
        "RemainAfterExit=yes\n"
        f"ExecStartPre=-{binary} stop\n"
        f"ExecStart={exec_line}\n"
        f"ExecStop=-{binary} stop\n"
        "\n"
        "[Install]\n"
        "WantedBy=multi-user.target\n"
    )


def _run_root_script(script, timeout=120):
    """Run a shell snippet as root, using pkexec/sudo when needed."""
    if os.geteuid() == 0:
        result = subprocess.run(
            [SHELL, "-c", script],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=timeout,
            check=False,
        )
        if result.returncode != 0:
            raise ScxctlError(_combined_message(result) or "Command failed.")
        return

    errors = []
    last_result = None
    prefixes = [["pkexec"], ["sudo", "-n"]]
    if sys.stdin is not None and sys.stdin.isatty():
        prefixes.append(["sudo"])

    for prefix in prefixes:
        if shutil.which(prefix[0]) is None:
            continue
        try:
            result = subprocess.run(
                [*prefix, SHELL, "-c", script],
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=timeout,
                check=False,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired) as exc:
            errors.append(str(exc))
            continue
        if result.returncode == 0:
            return
        last_result = result
        errors.append(_combined_message(result))

    if last_result is not None:
        # The command did run; a non-zero exit is usually the command's own
        # failure, but surface an authentication hint when that is the cause.
        detail = _combined_message(last_result) or "Command failed."
        if _AUTH_RE.search(detail):
            raise ScxctlError(
                f"Could not run the systemd command as root ({detail}). "
                "Run the configurator from a terminal with sudo once."
            )
        raise ScxctlError(detail)

    detail = next((error for error in errors if error), "authentication failed")
    raise ScxctlError(
        f"Could not run the systemd command as root ({detail}). "
        "Run the configurator from a terminal with sudo once."
    )


def install_boot_unit(content):
    path = shlex.quote(str(BOOT_UNIT_FILE))
    unit = shlex.quote(BOOT_UNIT)
    systemctl = shlex.quote(SYSTEMCTL)
    script = (
        f"printf %s {shlex.quote(content)} > {path} && "
        f"chmod 644 {path} && "
        f"{systemctl} daemon-reload && "
        f"{systemctl} enable {unit} && "
        f"{systemctl} restart {unit} || {{ "
        f"{systemctl} --no-pager --full status {unit}; "
        f"{shlex.quote(JOURNALCTL)} -xeu {unit} -n 20 --no-pager; exit 1; }}"
    )
    _run_root_script(script)


def remove_boot_unit():
    path = shlex.quote(str(BOOT_UNIT_FILE))
    script = (
        f"{shlex.quote(SYSTEMCTL)} disable --now {shlex.quote(BOOT_UNIT)} || true; "
        f"rm -f {path} && "
        f"{shlex.quote(SYSTEMCTL)} daemon-reload"
    )
    _run_root_script(script)


class Scxctl:
    """Thin wrapper around the scxctl CLI."""

    def __init__(self, binary=SCXCTL, timeout=15):
        self.binary = binary
        self.timeout = timeout

    def run(self, *args):
        return subprocess.run(
            [self.binary, *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=self.timeout,
            check=False,
        )

    @staticmethod
    def _message(result):
        return _result_message(result)

    def schedulers(self):
        result = self.run("list")
        if result.returncode != 0:
            raise ScxctlError(self._message(result) or "scxctl list failed")

        bracketed = re.search(r"supported schedulers:\s*\[(.*?)\]", result.stdout, re.S | re.I)
        names = re.findall(r'"([^"]+)"', bracketed.group(1) if bracketed else result.stdout)
        if not names:
            names = [
                token
                for token in re.split(r"[\s,]+", result.stdout)
                if re.fullmatch(r"[A-Za-z0-9_.+-]+", token)
                and not _HEADER_RE.match(token)
            ]
        return names

    def modes(self, scheduler):
        last = None
        for extra in (("--show-args",), ()):
            last = self.run("modes", "--sched", scheduler, *extra)
            if last.returncode == 0:
                return parse_modes(last.stdout)
        raise ScxctlError(self._message(last) or "scxctl modes failed")

    def status(self):
        """Return (running, description); running is True/False/None when unknown."""
        result = self.run("get")
        combined = f"{result.stdout}\n{result.stderr or ''}".strip()

        if "no scx scheduler running" in combined.lower():
            return False, "Stopped"
        if result.returncode != 0:
            return None, self._message(result) or "Unknown state"

        lines = [line.strip() for line in result.stdout.splitlines() if line.strip()]
        if not lines:
            return None, "Unknown state"
        return True, lines[0]


class Configurator(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SCX Scheduler")
        self.setMinimumWidth(480)
        self.client = Scxctl()
        self._mode_args = {}
        self._running = None

        self._build_ui()
        self.reload()

    # --- construction ---

    def _icon(self, name, fallback):
        icon = QIcon.fromTheme(name)
        return icon if not icon.isNull() else self.style().standardIcon(fallback)

    def _set_icon(self, label, name, fallback, extent=16):
        label.setPixmap(self._icon(name, fallback).pixmap(extent, extent))

    def _build_ui(self):
        form = QFormLayout()
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        self.scheduler_combo = QComboBox()
        self.scheduler_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.scheduler_combo.currentIndexChanged.connect(self._scheduler_changed)

        self.reload_button = QToolButton()
        self.reload_button.setIcon(self._icon("view-refresh", QStyle.StandardPixmap.SP_BrowserReload))
        self.reload_button.setToolTip("Reload schedulers and status")
        self.reload_button.setAutoRaise(True)
        self.reload_button.clicked.connect(self.reload)

        scheduler_row = QHBoxLayout()
        scheduler_row.setContentsMargins(0, 0, 0, 0)
        scheduler_row.setSpacing(4)
        scheduler_row.addWidget(self.scheduler_combo, 1)
        scheduler_row.addWidget(self.reload_button)
        form.addRow("Scheduler:", scheduler_row)

        self.mode_combo = QComboBox()
        self.mode_combo.setEditable(True)
        self.mode_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.mode_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        if self.mode_combo.lineEdit():
            self.mode_combo.lineEdit().setPlaceholderText(NO_MODE)
        self.mode_combo.currentTextChanged.connect(self._mode_changed)
        form.addRow("Mode:", self.mode_combo)

        self.args_edit = QLineEdit()
        self.args_edit.setClearButtonEnabled(True)
        self.args_edit.setPlaceholderText("Scheduler arguments, e.g. -m performance -w")
        self.args_edit.setToolTip(
            "Left empty, the selected mode's configured arguments are used.\n"
            "Editing this overrides the mode entirely."
        )
        form.addRow("Arguments:", self.args_edit)

        box = QGroupBox("Configuration")
        box.setLayout(form)

        self.status_icon = QLabel()
        self.status_text = QLabel("Checking status\u2026")
        self.status_text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.status_text.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)

        status_row = QHBoxLayout()
        status_row.setSpacing(6)
        status_row.addWidget(self.status_icon)
        status_row.addWidget(self.status_text, 1)

        self.boot_label = QLabel("At boot: checking\u2026")
        self.boot_label.setWordWrap(True)
        self.boot_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)

        self.message_label = QLabel()
        self.message_label.setWordWrap(True)
        self.message_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.message_label.hide()

        self.stop_button = QPushButton(self._icon("process-stop", QStyle.StandardPixmap.SP_MediaStop), "Stop")
        self.stop_button.clicked.connect(self.stop)

        self.boot_button = QPushButton("Set at boot")
        self.boot_button.setToolTip(
            "Write and enable scx-profile.service so the selected scheduler\n"
            "and profile are applied at boot."
        )
        self.boot_button.clicked.connect(self.set_boot)

        self.boot_off_button = QPushButton("Disable boot")
        self.boot_off_button.setToolTip("Disable and remove scx-profile.service")
        self.boot_off_button.clicked.connect(self.disable_boot)

        self.apply_button = QPushButton(
            self._icon("dialog-ok-apply", QStyle.StandardPixmap.SP_DialogApplyButton), "Apply"
        )
        self.apply_button.setDefault(True)
        self.apply_button.setShortcut(QKeySequence("Ctrl+Return"))
        self.apply_button.clicked.connect(self.apply)

        button_row = QHBoxLayout()
        button_row.setSpacing(6)
        button_row.addWidget(self.stop_button)
        button_row.addWidget(self.boot_button)
        button_row.addWidget(self.boot_off_button)
        button_row.addStretch(1)
        button_row.addWidget(self.apply_button)

        layout = QVBoxLayout(self)
        layout.setSpacing(9)
        layout.addWidget(box)
        layout.addLayout(status_row)
        layout.addWidget(self.boot_label)
        layout.addWidget(self.message_label)
        layout.addLayout(button_row)

    # --- state helpers ---

    def _message(self, text, error=False):
        self.message_label.setText(text)
        self.message_label.setVisible(bool(text))
        self.message_label.setToolTip(text if error else "")

    def _set_status(self, running, text):
        self._running = running
        variants = {
            True: ("dialog-ok", QStyle.StandardPixmap.SP_DialogApplyButton),
            False: ("process-stop", QStyle.StandardPixmap.SP_MediaStop),
            None: ("dialog-warning", QStyle.StandardPixmap.SP_MessageBoxWarning),
        }
        name, fallback = variants[running]
        self._set_icon(self.status_icon, name, fallback)
        self.status_text.setText(text)

    def _error(self, exc):
        self._set_status(None, str(exc))
        self.apply_button.setEnabled(False)
        self.stop_button.setEnabled(False)

    # --- scxctl interaction ---

    def reload(self):
        self.apply_button.setEnabled(True)
        self.stop_button.setEnabled(True)
        self._refresh_boot()

        try:
            running, text = self.client.status()
            self._set_status(running, text)
        except FileNotFoundError:
            self._error(f"'{SCXCTL}' was not found. Install scx-loader.")
            return
        except (subprocess.TimeoutExpired, ScxctlError, OSError) as exc:
            self._error(f"Could not query scheduler state: {exc}")
            return

        try:
            schedulers = self.client.schedulers()
        except (subprocess.TimeoutExpired, ScxctlError, OSError) as exc:
            self._error(f"Could not list schedulers: {exc}")
            return

        if not schedulers:
            self._error("No supported schedulers were reported by scxctl.")
            return

        previous = self.scheduler_combo.currentText()
        self.scheduler_combo.blockSignals(True)
        self.scheduler_combo.clear()
        self.scheduler_combo.addItems(schedulers)
        if previous in schedulers:
            self.scheduler_combo.setCurrentText(previous)
        self.scheduler_combo.blockSignals(False)

        self._scheduler_changed()

    def _scheduler_changed(self):
        scheduler = self.scheduler_combo.currentText().strip()

        modes = []
        if scheduler:
            try:
                modes = self.client.modes(scheduler)
            except FileNotFoundError:
                self._message(f"'{SCXCTL}' was not found. Install scx-loader.")
            except (subprocess.TimeoutExpired, ScxctlError, OSError) as exc:
                self._message(f"Could not read modes for {scheduler}: {exc}")

        self._mode_args = dict(modes)
        self.mode_combo.blockSignals(True)
        self.mode_combo.clear()
        self.mode_combo.addItem(NO_MODE)
        for name, _args in modes:
            self.mode_combo.addItem(name)
        self.mode_combo.setCurrentIndex(0)
        self.mode_combo.blockSignals(False)

        self._mode_changed()

    def _mode_changed(self):
        name = self.mode_combo.currentText().strip()
        if name == NO_MODE:
            self.args_edit.clear()
        elif name in self._mode_args:
            self.args_edit.setText(self._mode_args[name])
        # A hand-typed mode name is left alone; keep whatever arguments were entered.

    # --- actions ---

    def _refresh_status(self):
        try:
            running, text = self.client.status()
            self._set_status(running, text)
        except (FileNotFoundError, subprocess.TimeoutExpired, ScxctlError, OSError):
            pass

    def _failed(self, verb, result):
        detail = Scxctl._message(result) or "unknown error"
        self._message(f"scxctl {verb} failed: {detail}", error=True)

    def _selector(self):
        mode = self.mode_combo.currentText().strip()
        args = self.args_edit.text().strip()

        if mode == NO_MODE:
            mode = ""

        if mode and mode in self._mode_args and (not args or args == self._mode_args[mode]):
            return [f"--mode={mode}"]
        if args:
            return [f"--args={args}"]
        return []

    def apply(self):
        scheduler = self.scheduler_combo.currentText().strip()
        if not scheduler:
            self._message("Select a scheduler first.", error=True)
            return

        selector = self._selector()

        verbs = ("switch", "start") if self._running else ("start", "switch")
        past = {"start": "Started", "switch": "Switched to"}

        for verb in verbs:
            try:
                result = self.client.run(verb, "--sched", scheduler, *selector)
            except subprocess.TimeoutExpired:
                self._message(f"scxctl {verb} timed out.", error=True)
                return
            except (FileNotFoundError, OSError) as exc:
                self._message(f"Could not run scxctl: {exc}", error=True)
                return

            if result.returncode == 0:
                self._message(f"{past[verb]} {scheduler}")
                self._refresh_status()
                return
            if verb == verbs[-1]:
                self._failed(verb, result)

    def stop(self):
        try:
            result = self.client.run("stop")
        except subprocess.TimeoutExpired:
            self._message("scxctl stop timed out.", error=True)
            return
        except (FileNotFoundError, OSError) as exc:
            self._message(f"Could not run scxctl: {exc}", error=True)
            return

        if result.returncode == 0:
            self._message("Scheduler stopped")
            self._refresh_status()
        else:
            self._failed("stop", result)

    def set_boot(self):
        scheduler = self.scheduler_combo.currentText().strip()
        if not scheduler:
            self._message("Select a scheduler first.", error=True)
            return

        args = self.args_edit.text().strip()
        try:
            install_boot_unit(boot_unit_text(scheduler, args))
        except (FileNotFoundError, subprocess.TimeoutExpired, ScxctlError, OSError) as exc:
            self._message(f"Could not set the boot profile: {exc}", error=True)
            return

        target = f"scx_{scheduler}"
        if args:
            target += f" --args={args}"
        self._message(f"Boot profile set: {target}")
        self._refresh_boot()
        self._refresh_status()

    def disable_boot(self):
        try:
            remove_boot_unit()
        except (FileNotFoundError, subprocess.TimeoutExpired, ScxctlError, OSError) as exc:
            self._message(f"Could not disable the boot profile: {exc}", error=True)
            return

        self._message("Boot profile disabled")
        self._refresh_boot()
        self._refresh_status()

    def _refresh_boot(self):
        try:
            text = BOOT_UNIT_FILE.read_text(encoding="utf-8")
        except OSError:
            self.boot_label.setText("At boot: not configured")
            return

        match = re.search(r"^ExecStart=(.+)$", text, re.M)
        if match:
            self.boot_label.setText(f"At boot: {match.group(1)}")
        else:
            self.boot_label.setText("At boot: configured")


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("scxctl-configurator")
    app.setApplicationDisplayName("SCX Scheduler")
    app.setDesktopFileName("scxctl_configurator")

    icon = QIcon.fromTheme("cpu")
    if icon.isNull():
        icon = app.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)
    app.setWindowIcon(icon)

    window = Configurator()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
