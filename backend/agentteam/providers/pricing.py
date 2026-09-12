"""Model pricing (USD per million tokens). Unknown cloud models are NOT treated as free."""
from __future__ import annotations

from ..config.models import ModelPrice
from .base import ProviderUsage

# Anthropic first-party API rates (cached 2026-06-24 via the claude-api reference). Override in config `pricing:`.
KNOWN_PRICES: dict[str, ModelPrice] = {
    "claude-fable-5-1": ModelPrice(input_per_mtok=10.0, output_per_mtok=50.0),
    "claude-fable-5": ModelPrice(input_per_mtok=10.0, output_per_mtok=50.0),
    "claude-opus-5": ModelPrice(input_per_mtok=5.0, output_per_mtok=25.0),
    "claude-opus-4-8": ModelPrice(input_per_mtok=5.0, output_per_mtok=25.0),
    "claude-opus-4-7": ModelPrice(input_per_mtok=5.0, output_per_mtok=25.0),
    "claude-opus-4-6": ModelPrice(input_per_mtok=5.0, output_per_mtok=25.0),
    "claude-sonnet-5": ModelPrice(input_per_mtok=2.0, output_per_mtok=10.0),
    "claude-sonnet-4-6": ModelPrice(input_per_mtok=3.0, output_per_mtok=15.0),
    "claude-haiku-4-5": ModelPrice(input_per_mtok=1.0, output_per_mtok=5.0),
}


def price_for(model: str, overrides: dict[str, ModelPrice] | None = None, *, driver: str = "") -> ModelPrice | None:
    if overrides and model in overrides:
        return overrides[model]
    if driver == "ollama":
        return ModelPrice(input_per_mtok=0.0, output_per_mtok=0.0, cache_read_per_mtok=0.0, cache_write_per_mtok=0.0)
    if driver == "fake":
        return ModelPrice(input_per_mtok=1.0, output_per_mtok=5.0)
    return KNOWN_PRICES.get(model)


def cost_of(usage: ProviderUsage, price: ModelPrice) -> float:
    cr = price.cache_read_per_mtok if price.cache_read_per_mtok is not None else price.input_per_mtok * 0.1
    cw = price.cache_write_per_mtok if price.cache_write_per_mtok is not None else price.input_per_mtok * 1.25
    return (
        usage.input_tokens * price.input_per_mtok
        + usage.output_tokens * price.output_per_mtok
        + usage.cache_read_tokens * cr
        + usage.cache_write_tokens * cw
    ) / 1_000_000


def estimate_max_cost(price: ModelPrice, est_input_tokens: int, max_output_tokens: int) -> float:
    return (est_input_tokens * price.input_per_mtok + max_output_tokens * price.output_per_mtok) / 1_000_000
