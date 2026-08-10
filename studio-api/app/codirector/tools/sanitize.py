"""Argument validation and result sanitization for the tool registry.

Two trust boundaries meet here:

1. **Arguments come from the model.** They are validated against the tool's declared
   `ToolParameter` list — unknown keys are dropped, types are coerced or rejected, lengths and
   ranges are enforced. What gets stored on a proposal is the *sanitized* dict, so approving a
   proposal replays only what the registry would accept today.
2. **Results go back to the model and to the browser.** They are scrubbed of secret-shaped
   strings and absolute filesystem paths, capped in breadth and depth, and truncated to the
   tool's character budget with an explicit `truncated` signal rather than a silent cut.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any

from ..errors import TOOL_ARGUMENTS_INVALID, CoDirectorError, redact_secrets
from .definitions import ToolDefinition, ToolParameter

# Absolute Windows (`C:\...`, `\\host\share`) and POSIX (`/usr/...`) paths. Tool results are
# read by a model and rendered in a browser; neither has any business learning the operator's
# directory layout, and a leaked path is a reconnaissance gift in a bug report or screenshot.
_ABS_PATH_RE = re.compile(r"(?:[A-Za-z]:[\\/]|\\\\[^\\/\s]+[\\/]|(?<![\w.])/(?:usr|home|etc|var|opt|mnt|root|tmp|Users)/)[^\s\"'<>|]*")

MAX_STRING_CHARS = 1200
MAX_LIST_ITEMS = 50
MAX_DICT_KEYS = 60
MAX_DEPTH = 6

# Limits for model-supplied JSON arguments of structured types. The model emits
# these as JSON, so they are bounded for sanity, not for security — the sanitizer
# still drops unknown top-level keys, and handlers re-validate meaning.
MAX_ARRAY_ITEMS = 100
MAX_OBJECT_CHARS = 8000
MAX_OBJECT_DEPTH = 6
_ALLOWED_SCALAR_ITEM_TYPES = (str, int, float, bool)


# --------------------------------------------------------------------------
# Arguments
# --------------------------------------------------------------------------


def _invalid(tool_id: str, message: str, **details: Any) -> CoDirectorError:
    return CoDirectorError(
        TOOL_ARGUMENTS_INVALID,
        message,
        details={"toolId": tool_id, **details},
        recoverable=True,
        recommended_action="revise_arguments",
    )


def _json_compatible(value: Any) -> bool:
    """True if the value survives a round-trip through json.dumps without change.

    Callables, sets, custom objects, and bytes are not JSON-compatible; rejecting
    them keeps structured arguments within the contract the model actually emits.
    """

    try:
        json.dumps(value)
    except (TypeError, ValueError):
        return False
    return True


def _object_depth(value: Any) -> int:
    depth = 0
    cur = value
    while isinstance(cur, dict):
        if not cur:
            break
        depth += 1
        cur = next(iter(cur.values()))
    return depth


def _coerce(param: ToolParameter, raw: Any, tool_id: str) -> Any:
    if param.type == "string":
        if isinstance(raw, bool) or not isinstance(raw, (str, int, float)):
            raise _invalid(tool_id, f"'{param.name}' must be text.", parameter=param.name)
        value = str(raw).strip()
        if param.max_length is not None and len(value) > param.max_length:
            raise _invalid(
                tool_id,
                f"'{param.name}' is longer than the {param.max_length}-character limit.",
                parameter=param.name,
            )
        if param.choices and value not in param.choices:
            raise _invalid(
                tool_id,
                f"'{param.name}' must be one of: {', '.join(param.choices)}.",
                parameter=param.name,
            )
        return value

    if param.type == "boolean":
        if isinstance(raw, bool):
            return raw
        if isinstance(raw, str) and raw.strip().lower() in ("true", "false"):
            return raw.strip().lower() == "true"
        raise _invalid(tool_id, f"'{param.name}' must be true or false.", parameter=param.name)

    if param.type == "array":
        if isinstance(raw, dict) or not isinstance(raw, (list, tuple)):
            raise _invalid(tool_id, f"'{param.name}' must be a JSON array.", parameter=param.name)
        items = list(raw)
        if len(items) > MAX_ARRAY_ITEMS:
            raise _invalid(
                tool_id,
                f"'{param.name}' has {len(items)} items; the limit is {MAX_ARRAY_ITEMS}.",
                parameter=param.name,
            )
        out: list[Any] = []
        for item in items:
            if not isinstance(item, _ALLOWED_SCALAR_ITEM_TYPES) and not isinstance(item, dict):
                raise _invalid(
                    tool_id,
                    f"'{param.name}' contains an item that is not a string, number, boolean, or object.",
                    parameter=param.name,
                )
            if not _json_compatible(item):
                raise _invalid(
                    tool_id,
                    f"'{param.name}' contains an item that is not JSON-compatible.",
                    parameter=param.name,
                )
            out.append(item)
        return out

    if param.type == "object":
        if not isinstance(raw, dict):
            raise _invalid(tool_id, f"'{param.name}' must be a JSON object.", parameter=param.name)
        if not _json_compatible(raw):
            raise _invalid(
                tool_id,
                f"'{param.name}' contains values that are not JSON-compatible.",
                parameter=param.name,
            )
        serialized = json.dumps(raw, default=str)
        if len(serialized) > MAX_OBJECT_CHARS:
            raise _invalid(
                tool_id,
                f"'{param.name}' is larger than the {MAX_OBJECT_CHARS}-character limit.",
                parameter=param.name,
            )
        if _object_depth(raw) > MAX_OBJECT_DEPTH:
            raise _invalid(
                tool_id,
                f"'{param.name}' nests deeper than {MAX_OBJECT_DEPTH} levels.",
                parameter=param.name,
            )
        return raw

    # integer / number
    if isinstance(raw, bool):
        raise _invalid(tool_id, f"'{param.name}' must be a number.", parameter=param.name)
    try:
        value = int(raw) if param.type == "integer" else float(raw)
    except (TypeError, ValueError) as exc:
        raise _invalid(tool_id, f"'{param.name}' must be a number.", parameter=param.name) from exc
    if param.minimum is not None and value < param.minimum:
        raise _invalid(tool_id, f"'{param.name}' must be at least {param.minimum}.", parameter=param.name)
    if param.maximum is not None and value > param.maximum:
        raise _invalid(tool_id, f"'{param.name}' must be at most {param.maximum}.", parameter=param.name)
    return value


def sanitize_arguments(definition: ToolDefinition, raw: Any) -> dict[str, Any]:
    """Validate model-supplied arguments against a tool's declared schema.

    Unknown keys are dropped rather than rejected: a model inventing an extra field should not
    fail an otherwise valid call, but that field must never reach a handler.
    """

    if raw is None:
        raw = {}
    if not isinstance(raw, dict):
        raise _invalid(definition.tool_id, "Tool arguments must be a JSON object.")

    declared = {p.name: p for p in definition.parameters}
    out: dict[str, Any] = {}
    for name, param in declared.items():
        if name not in raw or raw[name] is None or raw[name] == "":
            if param.required:
                raise _invalid(definition.tool_id, f"'{name}' is required.", parameter=name)
            continue
        out[name] = _coerce(param, raw[name], definition.tool_id)
    return out


def compute_input_hash(
    *,
    tool_id: str,
    schema_version: int,
    arguments: dict[str, Any],
    base_resource_versions: dict[str, Any],
) -> str:
    """Idempotency key for a tool proposal: same tool + args + base state = same execution."""

    canonical = json.dumps(
        {
            "toolId": tool_id,
            "toolSchemaVersion": schema_version,
            "arguments": arguments,
            "baseResourceVersions": base_resource_versions,
        },
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# --------------------------------------------------------------------------
# Results
# --------------------------------------------------------------------------


def scrub_text(text: str) -> str:
    """Redact secret-shaped substrings and absolute filesystem paths from a string."""

    return _ABS_PATH_RE.sub("<path>", redact_secrets(text))


def _scrub(value: Any, depth: int) -> Any:
    if depth > MAX_DEPTH:
        return "<nested>"
    if isinstance(value, str):
        scrubbed = scrub_text(value)
        if len(scrubbed) > MAX_STRING_CHARS:
            return scrubbed[:MAX_STRING_CHARS] + "…"
        return scrubbed
    if isinstance(value, bool) or value is None or isinstance(value, (int, float)):
        return value
    if isinstance(value, (list, tuple)):
        items = [_scrub(v, depth + 1) for v in list(value)[:MAX_LIST_ITEMS]]
        if len(value) > MAX_LIST_ITEMS:
            items.append(f"<{len(value) - MAX_LIST_ITEMS} more omitted>")
        return items
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for i, (key, val) in enumerate(value.items()):
            if i >= MAX_DICT_KEYS:
                out["_omittedKeys"] = len(value) - MAX_DICT_KEYS
                break
            out[scrub_text(str(key))] = _scrub(val, depth + 1)
        return out
    return scrub_text(str(value))


def sanitize_result(value: Any, *, char_budget: int) -> tuple[dict[str, Any], bool]:
    """Scrub and size-cap a handler's result.

    Returns `(payload, truncated)`. `truncated` is surfaced to the caller as a
    `tool_result_truncated` event so neither the model nor the user is silently handed a
    partial answer they think is complete.
    """

    scrubbed = _scrub(value if isinstance(value, dict) else {"value": value}, 0)
    serialized = json.dumps(scrubbed, default=str)
    if len(serialized) <= char_budget:
        return scrubbed, False

    # Shed whole top-level keys, largest first, until the payload fits. Dropping entire keys
    # keeps the remaining JSON valid and self-describing, unlike slicing the serialized string.
    kept = dict(scrubbed)
    dropped: list[str] = []
    by_size = sorted(kept.items(), key=lambda kv: len(json.dumps(kv[1], default=str)), reverse=True)
    for key, _ in by_size:
        if len(json.dumps(kept, default=str)) <= char_budget:
            break
        if len(kept) <= 1:
            break
        kept.pop(key, None)
        dropped.append(key)
    kept["_truncated"] = True
    if dropped:
        kept["_omittedFields"] = dropped
    if len(json.dumps(kept, default=str)) > char_budget:
        return {"_truncated": True, "_reason": "Result exceeded this tool's size budget."}, True
    return kept, True


def result_hash(payload: dict[str, Any]) -> str:
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode("utf-8")).hexdigest()


def render_result_for_model(tool_id: str, payload: dict[str, Any], *, truncated: bool) -> str:
    """Format a sanitized result for injection back into the model's transcript."""

    note = "\n(Result was truncated to fit its size budget.)" if truncated else ""
    return f"Tool result for `{tool_id}`:\n```json\n{json.dumps(payload, indent=2, default=str)}\n```{note}"
