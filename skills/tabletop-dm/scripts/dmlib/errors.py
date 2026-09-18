"""The one error shape, and the one success shape, that every command prints."""
from typing import Any, Dict


class DmError(Exception):
    """A refusal. The command changed nothing on disk."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def error_envelope(command: str, err: DmError) -> Dict[str, Any]:
    return {"ok": False, "command": command, "error": {"code": err.code, "message": err.message}}


def success_envelope(command: str, **fields: Any) -> Dict[str, Any]:
    env = {"ok": True, "command": command}  # type: Dict[str, Any]
    env.update(fields)
    return env
