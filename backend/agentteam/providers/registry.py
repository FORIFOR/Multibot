"""Builds ProviderAdapters from connections; resolves secrets at construction time only."""
from __future__ import annotations

import os
from typing import Any

from ..config.models import AgentTeamConfig, Connection, IMPLEMENTED_DRIVERS
from ..config.secrets import SecretResolutionError, resolve_secret
from .anthropic_driver import AnthropicDriver
from .base import ProviderAdapter, ProviderError
from .openai_compat_driver import OpenAICompatDriver


class ProviderRegistry:
    def __init__(self, config: AgentTeamConfig, *, fake_adapters: dict[str, ProviderAdapter] | None = None):
        self.config = config
        self._adapters: dict[str, ProviderAdapter] = dict(fake_adapters or {})
        self.secret_values: list[str] = []  # for redaction of anything that slips into text

    def allow_fake(self) -> bool:
        return os.environ.get("AGENTTEAM_ALLOW_FAKE_PROVIDER") == "1"

    def adapter(self, connection_id: str) -> ProviderAdapter:
        if connection_id in self._adapters:
            return self._adapters[connection_id]
        conn = self.config.connection(connection_id)
        if conn is None:
            raise ProviderError("bad_request", f"unknown connection {connection_id}")
        self._adapters[connection_id] = self._build(conn)
        return self._adapters[connection_id]

    def _build(self, conn: Connection) -> ProviderAdapter:
        if conn.driver not in IMPLEMENTED_DRIVERS:
            raise ProviderError("unsupported", f"driver {conn.driver} is not implemented in this build")
        if conn.driver == "fake":
            raise ProviderError("unsupported", "fake provider must be injected explicitly (tests only)")
        try:
            key = resolve_secret(conn.api_key_ref)
        except SecretResolutionError as e:
            raise ProviderError("auth", f"cannot resolve api key for connection {conn.id}: {e}")
        if key:
            self.secret_values.append(key)
        if conn.driver == "anthropic_messages":
            return AnthropicDriver(conn.id, key, conn.base_url, refusal_fallback=conn.refusal_fallback)
        if conn.driver in ("openai_compatible_chat", "ollama"):
            return OpenAICompatDriver(conn.id, key, conn.base_url, driver=conn.driver)
        raise ProviderError("unsupported", f"driver {conn.driver} is not implemented")

    def kind(self, connection_id: str) -> str:
        return getattr(self.adapter(connection_id), "kind", "real")

    async def aclose(self) -> None:
        for a in self._adapters.values():
            try:
                await a.aclose()
            except Exception:
                pass
        self._adapters.clear()

    def describe(self, connection_id: str) -> dict[str, Any]:
        conn = self.config.connection(connection_id)
        if not conn:
            return {}
        return {"id": conn.id, "driver": conn.driver, "base_url": conn.base_url, "capability_check": conn.capability_check,
                "api_key_ref": conn.api_key_ref}
