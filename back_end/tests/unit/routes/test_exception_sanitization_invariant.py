# tests/unit/routes/test_exception_sanitization_invariant.py
"""
Source-level invariant scan (Verification C, error_sanitization plan).

Within an `except ... as e` handler, the bound exception object may flow
only into a known-safe form: logger.*(...), api_error(...), `raise ... from e`,
an attribute read (e.message, e.response.status_code), or type(e).__name__.
Anything else is a leak of raw exception text into an HTTP response, SSE
event, or LLM tool_result — unless the handler catches ProviderConfigError,
which is deliberately exempt (static, user-actionable config guidance with
nothing else riding that channel after Step 1 of the plan).

type(e).__name__ must stay allowed: it's Step 3's own prescribed fix
(shared/llm_tool_loop.py, routes/chat.py) — the exception *class* is
deliberately preserved while its text is dropped, so the scan has to say so
or it rejects the plan's own fix.

Handlers with no `as e` are invisible to this scan, correctly — after Step 4
the SSE handlers bind nothing, so nothing can leak.

This scan tracks only the *exception object*. It does not cover other
sensitive data reaching a response (e.g. subprocess stderr in
routes/db_backup.py) — that is what the dedicated test in test_db_backup.py
guards.
"""
import ast
from pathlib import Path

import pytest

BACK_END = Path(__file__).resolve().parents[3]

SCAN_TARGETS = [
    BACK_END / "routes",
    BACK_END / "shared" / "llm_tool_loop.py",
    BACK_END / "utils" / "llm_provider.py",
    BACK_END / "utils" / "openai_provider.py",
    BACK_END / "db_connector" / "connection.py",
]

SAFE_CALL_NAMES = {"api_error"}
LOGGER_NAME = "logger"

# Transparent to the "does e flow into a safe sink" climb: f-string plumbing
# and simple literal containers, not sinks in their own right.
_TRANSPARENT = (ast.JoinedStr, ast.FormattedValue, ast.keyword, ast.Dict, ast.List, ast.Tuple, ast.Starred)


def _iter_py_files(paths):
    for p in paths:
        if p.is_dir():
            yield from sorted(p.rglob("*.py"))
        elif p.suffix == ".py":
            yield p


def _catches_provider_config_error(handler: ast.ExceptHandler) -> bool:
    if handler.type is None:
        return False
    names = {n.id for n in ast.walk(handler.type) if isinstance(n, ast.Name)}
    attrs = {n.attr for n in ast.walk(handler.type) if isinstance(n, ast.Attribute)}
    return "ProviderConfigError" in names or "ProviderConfigError" in attrs


def _is_logger_call(call: ast.Call) -> bool:
    func = call.func
    return isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name) and func.value.id == LOGGER_NAME


def _is_safe_call(call: ast.Call, name_node: ast.Name) -> bool:
    """Does this call neutralize the exception object passed to it?"""
    # Logging is a safe sink however the exception is embedded — the log is
    # server-side, and f-string interpolation there is the intended idiom.
    if _is_logger_call(call):
        return True

    if isinstance(call.func, ast.Name) and call.func.id in SAFE_CALL_NAMES:
        # api_error sanitizes the exception it is HANDED, but interpolates its
        # `operation` argument into the client-visible detail verbatim. So the
        # exception is only safe as a direct argument — nested inside an f-string
        # it rides `operation` straight into the response body:
        #   api_error(f"Fetch {e}", e)  ->  detail "Fetch <exception text> failed"
        # Both positional and keyword forms count as direct.
        return any(a is name_node for a in call.args) or any(
            k.value is name_node for k in call.keywords
        )

    return False


def _build_parent_map(tree: ast.AST) -> dict:
    parents = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            parents[child] = node
    return parents


def _is_safe_use(name_node: ast.Name, parents: dict) -> bool:
    """Classify one Load-context use of a bound exception name."""
    parent = parents.get(name_node)

    # Direct attribute read: e.message, e.response.status_code
    if isinstance(parent, ast.Attribute) and parent.value is name_node:
        return True

    # type(e) — the class name only, no text
    if (
        isinstance(parent, ast.Call)
        and isinstance(parent.func, ast.Name)
        and parent.func.id == "type"
        and len(parent.args) == 1
        and parent.args[0] is name_node
        and not parent.keywords
    ):
        return True

    # Climb through f-string / literal-container plumbing to the nearest
    # Call or Raise boundary.
    node, prev = parent, name_node
    while node is not None:
        if isinstance(node, ast.Call):
            return _is_safe_call(node, name_node)
        if isinstance(node, ast.Raise):
            return node.cause is prev
        if not isinstance(node, _TRANSPARENT):
            return False
        prev, node = node, parents.get(node)
    return False


def _scan_source(source: str, label: str) -> list[str]:
    tree = ast.parse(source, filename=label)
    parents = _build_parent_map(tree)
    violations = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.ExceptHandler) or node.name is None:
            continue
        if _catches_provider_config_error(node):
            continue
        bound = node.name
        for sub in ast.walk(node):
            if isinstance(sub, ast.Name) and sub.id == bound and isinstance(sub.ctx, ast.Load):
                if not _is_safe_use(sub, parents):
                    violations.append(f"{label}:{sub.lineno}")

    return violations


def _scan_file(path: Path) -> list[str]:
    return _scan_source(path.read_text(encoding="utf-8"), str(path.relative_to(BACK_END)))


# Cases the rule itself must classify correctly, independent of the current tree.
# The scan below only asserts the tree is clean, so a future change that made the
# rule permissive would still pass it — these are what catch that.
_LEAKS = [
    'raise api_error(f"Fetch {e}", e)',   # e rides `operation` into the response detail
    'yield str(e)',
    'yield f"boom {e}"',
    'return {"error": repr(e)}',
]

_SAFE = [
    'raise api_error("Fetch", e)',
    'raise api_error("Fetch", e=e)',
    'raise api_error(f"Fetch {language}", e)',   # interpolates context, not the exception
    'logger.error(f"boom {e}")',                 # log is a server-side sink
    'logger.exception("boom")',
    'raise ValueError("x") from e',
    'name = type(e).__name__',
    'msg = e.message',
]


def _wrap(body: str) -> str:
    return f"try:\n    pass\nexcept Exception as e:\n    {body}\n"


@pytest.mark.parametrize("body", _LEAKS)
def test_rule_flags_leaking_forms(body):
    assert _scan_source(_wrap(body), "<probe>"), f"should have been flagged: {body}"


@pytest.mark.parametrize("body", _SAFE)
def test_rule_allows_safe_forms(body):
    assert not _scan_source(_wrap(body), "<probe>"), f"should not have been flagged: {body}"


def test_rule_exempts_provider_config_error_handlers():
    source = 'try:\n    pass\nexcept ProviderConfigError as e:\n    yield str(e)\n'
    assert not _scan_source(source, "<probe>")


def test_exception_text_does_not_leak_from_except_handlers():
    violations = []
    for path in _iter_py_files(SCAN_TARGETS):
        violations.extend(_scan_file(path))

    assert not violations, (
        "Bound exception object flows into an unsafe sink (raw exception text "
        "may leak into an HTTP response, SSE event, or LLM tool_result):\n"
        + "\n".join(violations)
    )
