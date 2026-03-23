from __future__ import annotations

import base64


class Apps:
    """macOS pre-installed application names."""

    Safari = "Safari"
    Mail = "Mail"
    Maps = "Maps"
    Notes = "Notes"
    Calendar = "Calendar"
    Reminders = "Reminders"
    Messages = "Messages"
    Photos = "Photos"
    Music = "Music"
    Finder = "Finder"
    Terminal = "Terminal"
    TextEdit = "TextEdit"
    Preview = "Preview"
    Calculator = "Calculator"
    SystemPreferences = "System Preferences"


class Seed:
    """Helpers for building seed commands to run at sandbox creation.

    Usage::

        sandbox = client.create(seed=[
            Seed.launch(Apps.Safari),
            Seed.open("https://google.com"),
            Seed.shell("mkdir -p ~/Documents/project"),
            Seed.write_file("~/Desktop/data.csv", csv_bytes),
        ])
    """

    @staticmethod
    def shell(command: str) -> dict:
        """Run a shell command."""
        return {"command": "shell", "params": {"command": command}}

    @staticmethod
    def open(target: str) -> dict:
        """Open a URL or file path (macOS ``open`` command)."""
        return {"command": "shell", "params": {"command": f"open {target}"}}

    @staticmethod
    def launch(app: str) -> dict:
        """Launch an application by name. Use ``Apps.*`` constants."""
        return {"command": "shell", "params": {"command": f"open -a '{app}'"}}

    @staticmethod
    def write_file(path: str, data: bytes) -> dict:
        """Write binary data to a file on the VM."""
        return {
            "command": "write_bytes",
            "params": {"path": path, "data": base64.b64encode(data).decode()},
        }

    @staticmethod
    def type_text(text: str) -> dict:
        """Type text via the keyboard."""
        return {"command": "type_text", "params": {"text": text}}
