import pytest

from agentteam.config.loader import ConfigError, load_config_text, DEFAULT_CONFIG_YAML
from agentteam.config.models import Limits, ModelPrice
from agentteam.contracts import TeamPlan, TaskSpec
from agentteam.providers.base import ProviderUsage
from agentteam.providers.pricing import price_for
from agentteam.runtime.planner import validate_plan, plan_from_output
from agentteam.runtime.policy import PolicyEngine, PolicyViolation
from agentteam.runtime.redaction import Redactor
from tests.conftest import FAKE_CONFIG, PLAN


def test_budget_reservation_blocks_parallel_overrun():
    p = PolicyEngine(limits=Limits(budget_usd=0.01, max_model_calls=10))
    price = ModelPrice(input_per_mtok=5.0, output_per_mtok=25.0)
    r1 = p.reserve_model_call(price, est_input_tokens=100, max_output_tokens=200)  # ~0.0055
    with pytest.raises(PolicyViolation) as ei:
        p.reserve_model_call(price, est_input_tokens=100, max_output_tokens=200)  # would exceed with reservation
    assert ei.value.code == "budget"
    p.settle_model_call(r1, price, ProviderUsage(input_tokens=100, output_tokens=10))
    assert p.usage.reserved_usd == 0 and 0 < p.usage.cost_usd < 0.001
    p.reserve_model_call(price, 100, 200)  # fits after the real (smaller) cost settled


def test_unknown_pricing_is_not_free():
    assert price_for("some-cloud-model") is None
    assert price_for("llama3", driver="ollama").input_per_mtok == 0.0
    p = PolicyEngine(limits=Limits())
    with pytest.raises(PolicyViolation) as ei:
        p.reserve_model_call(None, 10, 10)
    assert ei.value.code == "unknown_pricing"


def test_model_call_limit_and_tool_scope():
    p = PolicyEngine(limits=Limits(max_model_calls=1))
    price = ModelPrice(input_per_mtok=1, output_per_mtok=1)
    p.reserve_model_call(price, 10, 10)
    with pytest.raises(PolicyViolation):
        p.reserve_model_call(price, 10, 10)
    with pytest.raises(PolicyViolation) as ei:
        p.check_tool_allowed(["read_artifact"], "sandbox_run")
    assert ei.value.code == "tool_scope"


def test_peer_message_and_revision_limits():
    p = PolicyEngine(limits=Limits(max_peer_messages_per_task=2, max_revision_rounds=1))
    p.count_peer_message("t1"); p.count_peer_message("t1")
    with pytest.raises(PolicyViolation):
        p.count_peer_message("t1")
    assert p.next_revision_round("t2") == 1
    assert p.next_revision_round("t2") is None


@pytest.mark.parametrize("bad", ["../x", "/etc/passwd", "a/../../b", "~/x", ""])
def test_write_path_scope(bad):
    with pytest.raises(PolicyViolation):
        PolicyEngine.check_write_path(bad)
    assert PolicyEngine.check_write_path("site/index.html") == "site/index.html"


def test_redaction_masks_known_and_pattern_secrets():
    r = Redactor(["hunter2hunter2"])
    out = r({"err": "401 x-api-key: sk-ant-api03-abcdefghijklmnop with hunter2hunter2 and Bearer abcdefghijklmnopqrstuv"})
    assert "sk-ant" not in out["err"] and "hunter2" not in out["err"] and "abcdefghijklmnopqrstuv" not in out["err"]


def _plan(**over):
    d = {k: (v.copy() if isinstance(v, (list, dict)) else v) for k, v in PLAN.items()}
    d["tasks"] = [dict(t) for t in PLAN["tasks"]]
    d.update(over)
    return plan_from_output(d)


ENABLED = ["master", "researcher", "builder", "reviewer"]
ROLES = {"master": "master", "researcher": "researcher", "builder": "builder", "reviewer": "reviewer"}


def test_plan_validation_accepts_good_plan():
    assert validate_plan(_plan(), ENABLED, ROLES, 12) == []


def test_plan_rejects_cycle_unknown_owner_and_duplicates():
    p = _plan()
    p.tasks[0].depends_on = ["t3"]
    assert any("cyclic" in e for e in validate_plan(p, ENABLED, ROLES, 12))
    p = _plan()
    p.tasks[1].owner = "designer"
    errs = validate_plan(p, ENABLED, ROLES, 12)
    assert any("owner designer" in e for e in errs)
    p = _plan()
    p.tasks[1].output_paths = ["brief.md", "posts.md"]
    assert any("also produced" in e for e in validate_plan(p, ENABLED, ROLES, 12))
    p = _plan()
    p.tasks[2].depends_on = []
    assert any("reviewer task must depend" in e for e in validate_plan(p, ENABLED, ROLES, 12))
    assert any("too many tasks" in e for e in validate_plan(_plan(), ENABLED, ROLES, 2))
    p = _plan()
    p.tasks[1].depends_on = ["t9"]
    assert any("unknown dependency" in e for e in validate_plan(p, ENABLED, ROLES, 12))


def test_fake_driver_not_selectable_from_config():
    with pytest.raises((ConfigError, Exception)):
        load_config_text(FAKE_CONFIG)  # allow_fake defaults to False
    cfg = load_config_text(DEFAULT_CONFIG_YAML)
    assert cfg.defaults.connection_id == "claude_cli" and cfg.connection("anthropic").capability_check == "not_run"
    assert cfg.connection("claude_cli").capability_check == "not_run"  # never runnable before a real probe


def test_default_reviewer_can_fetch_cited_sources():
    """All three research re-runs ended partial because the reviewer, asked to check claims against their sources,
    had no web_fetch; the Master then added workaround tasks that hit the budget."""
    from agentteam.config.loader import DEFAULT_CONFIG_YAML, load_config_text
    cfg = load_config_text(DEFAULT_CONFIG_YAML)
    reviewer = next(a for a in cfg.agents if a.id == "reviewer")
    assert "web_fetch" in reviewer.tools
