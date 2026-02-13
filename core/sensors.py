"""
Reality Feedback Collection Layer.

Implements sensors to automatically perceive world state changes,
reducing the need for manual user input.
"""
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, Optional
from datetime import datetime


class Sensor(ABC):
    """Base class for reality sensors."""

    @abstractmethod
    def verify(self, target: Any) -> Dict[str, Any]:
        """
        Verify if the target state has been achieved.

        Returns:
            Dict containing:
            - verified (bool): Whether the condition is met
            - value (Any): The observed value
            - evidence (str): Description of the evidence
        """
        pass


class FileSensor(Sensor):
    """
    Monitors file system changes.

    Target format: "path/to/file"
    Checks if file exists and was modified today.
    """

    def __init__(self, base_dir: Path):
        self.base_dir = base_dir

    def verify(self, target: str) -> Dict[str, Any]:
        file_path = self.base_dir / target

        if not file_path.exists():
            return {
                "verified": False,
                "evidence": f"File not found: {target}"
            }

        # Check modification time
        mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
        today = datetime.now().date()

        if mtime.date() == today:
            return {
                "verified": True,
                "value": file_path.read_text(encoding="utf-8")[:100] + "...",
                "evidence": f"File modified today at {mtime.strftime('%H:%M')}"
            }

        return {
            "verified": False,
            "evidence": f"File exists but not modified today (Last: {mtime.strftime('%Y-%m-%d')})"
        }


# Factory
def get_sensor(name: str) -> Optional[Sensor]:
    # In a real app, this would be dependency injected
    from main import PROJECT_ROOT

    if name == "file_system":
        return FileSensor(PROJECT_ROOT)
    return None
