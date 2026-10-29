"""Standalone Vainah Messenger launcher for Windows."""
from pathlib import Path
import sys

if not getattr(sys, "frozen", False):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from apps.desktop.run import launch

if __name__ == "__main__":
    if "--app" not in sys.argv:
        sys.argv.extend(["--app", "messenger"])
    launch()
