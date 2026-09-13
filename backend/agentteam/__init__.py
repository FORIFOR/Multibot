"""Agent Team: one request, a real AI team, verifiable artifacts and a traceable history."""
from importlib.metadata import PackageNotFoundError, version as _pkg_version

try:
    __version__ = _pkg_version("agentteam")  # single source: backend/pyproject.toml
except PackageNotFoundError:  # running from a bare checkout without installation
    __version__ = "0.0.0+unknown"
