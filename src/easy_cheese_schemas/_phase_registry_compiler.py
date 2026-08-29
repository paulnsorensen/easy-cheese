"""Dependency-free compiler for authored phase contract declarations.

This module is intentionally private.  Build tooling imports it directly from
source so a clean checkout can regenerate the phase registry before the
checked-in generated module exists.  Runtime consumers use the generated
resolver instead; this module contains no runtime transition lookup.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import cast
from urllib.parse import urlparse
try:
    from ._schema_catalog import (
        PHASE_CONTRACT_SCHEMA_URI,
        REGISTERED_CONTRACT_SCHEMA_URIS as REGISTERED_SCHEMA_URIS,
    )
except ImportError:
    from _schema_catalog import (
        PHASE_CONTRACT_SCHEMA_URI,
        REGISTERED_CONTRACT_SCHEMA_URIS as REGISTERED_SCHEMA_URIS,
    )

SUPPORTED_PHASE_CONTRACT_MAJOR = "1"
SUPPORTED_PHASE_CONTRACT_MINOR = "0"


_PHASE_KEYS = frozenset({"contract_version", "source", "input_schema_uris", "outputs"})
_VERSION_KEYS = frozenset({"schema_uri", "major", "minor"})
_OUTPUT_KEYS = frozenset({"destination", "payload_schema_uri"})


@dataclass(frozen=True, order=True)
class CompiledTransition:
    source: str
    destination: str
    payload_schema_uri: str


@dataclass(frozen=True, order=True)
class CompiledPhase:
    source: str
    contract_schema_uri: str
    contract_major: str
    contract_minor: str
    input_schema_uris: tuple[str, ...]
    outputs: tuple[CompiledTransition, ...]


@dataclass(frozen=True)
class TransitionRegistry:
    phases: tuple[CompiledPhase, ...]

    def phase(self, source: str) -> CompiledPhase | None:
        return next((phase for phase in self.phases if phase.source == source), None)

    @property
    def sources(self) -> tuple[str, ...]:
        return tuple(phase.source for phase in self.phases)

    def to_data(self) -> list[dict[str, object]]:
        return [
            {
                "contract_version": {
                    "major": phase.contract_major,
                    "minor": phase.contract_minor,
                    "schema_uri": phase.contract_schema_uri,
                },
                "input_schema_uris": list(phase.input_schema_uris),
                "outputs": [
                    {
                        "destination": route.destination,
                        "payload_schema_uri": route.payload_schema_uri,
                    }
                    for route in phase.outputs
                ],
                "source": phase.source,
            }
            for phase in self.phases
        ]

    def to_json(self) -> str:
        return json.dumps(
            {"phases": self.to_data()}, sort_keys=True, separators=(",", ":")
        )


def _require_mapping(value: object, field: str) -> Mapping[object, object]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field} must be a mapping")
    return cast("Mapping[object, object]", value)


def _require_keys(
    value: Mapping[object, object], expected: frozenset[str], field: str
) -> None:
    keys = set(value)
    unknown = keys - expected
    missing = expected - keys
    if unknown:
        names = ", ".join(sorted(str(name) for name in unknown))
        raise ValueError(f"{field} has unknown fields: {names}")
    if missing:
        names = ", ".join(sorted(str(name) for name in missing))
        raise ValueError(f"{field} is missing fields: {names}")


def _require_string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field} must be a non-empty string")
    return value


def _require_version_component(value: object, field: str) -> str:
    if (
        not isinstance(value, str)
        or not value.isascii()
        or not value.isdecimal()
        or (value != "0" and value.startswith("0"))
    ):
        raise ValueError(f"{field} must be a canonical decimal string")
    return value


def _require_registered_schema(value: object, field: str) -> str:
    uri = _require_string(value, field)
    parsed = urlparse(uri)
    if parsed.scheme != "https" or parsed.netloc != "schemas.easy-cheese.dev":
        raise ValueError(f"{field} must be a schema URI")
    if uri not in REGISTERED_SCHEMA_URIS:
        raise ValueError(f"{field} must be a registered canonical schema URI")
    return uri


def _require_list(value: object, field: str) -> list[object]:
    if not isinstance(value, list) or not value:
        raise ValueError(f"{field} must be a non-empty list")
    return cast("list[object]", value)


def _compile_declaration(raw: object) -> CompiledPhase:
    data = _require_mapping(raw, "phase contract")
    _require_keys(data, _PHASE_KEYS, "phase contract")
    version = _require_mapping(data["contract_version"], "contract_version")
    _require_keys(version, _VERSION_KEYS, "contract_version")
    schema_uri = _require_string(version["schema_uri"], "contract_version.schema_uri")
    if schema_uri != PHASE_CONTRACT_SCHEMA_URI:
        raise ValueError(
            "contract_version.schema_uri must be the canonical PhaseContract schema URI"
        )
    major = _require_version_component(version["major"], "contract_version.major")
    minor = _require_version_component(version["minor"], "contract_version.minor")
    if major != SUPPORTED_PHASE_CONTRACT_MAJOR:
        raise ValueError(f"unsupported phase contract major {major!r}")
    if int(minor) > int(SUPPORTED_PHASE_CONTRACT_MINOR):
        raise ValueError(f"future phase contract minor {minor!r}")

    source = _require_string(data["source"], "source")
    inputs = tuple(
        sorted(
            _require_registered_schema(uri, f"input_schema_uris[{index}]")
            for index, uri in enumerate(
                _require_list(data["input_schema_uris"], "input_schema_uris")
            )
        )
    )
    if len(set(inputs)) != len(inputs):
        raise ValueError(f"phase {source!r} has duplicate input schema URIs")

    outputs: list[CompiledTransition] = []
    for index, item in enumerate(_require_list(data["outputs"], "outputs")):
        output = _require_mapping(item, f"outputs[{index}]")
        _require_keys(output, _OUTPUT_KEYS, f"outputs[{index}]")
        outputs.append(
            CompiledTransition(
                source=source,
                destination=_require_string(
                    output["destination"], f"outputs[{index}].destination"
                ),
                payload_schema_uri=_require_registered_schema(
                    output["payload_schema_uri"],
                    f"outputs[{index}].payload_schema_uri",
                ),
            )
        )
    compiled_outputs = tuple(sorted(outputs))
    if len(set(compiled_outputs)) != len(compiled_outputs):
        raise ValueError(f"phase {source!r} has duplicate output transitions")

    return CompiledPhase(
        source=source,
        contract_schema_uri=schema_uri,
        contract_major=major,
        contract_minor=minor,
        input_schema_uris=inputs,
        outputs=compiled_outputs,
    )


def _registry(phases: Iterable[CompiledPhase]) -> TransitionRegistry:
    compiled = tuple(sorted(phases))
    if not compiled:
        raise ValueError("at least one phase contract is required")
    for previous, current in zip(compiled, compiled[1:], strict=False):
        if previous.source == current.source:
            raise ValueError(f"duplicate phase source {current.source!r}")

    by_source = {phase.source: phase for phase in compiled}
    for phase in compiled:
        for route in phase.outputs:
            destination = by_source.get(route.destination)
            if destination is not None and route.payload_schema_uri not in destination.input_schema_uris:
                raise ValueError(
                    f"payload schema {route.payload_schema_uri!r} for {phase.source} -> "
                    + f"{route.destination} is not declared as a destination input"
                )
    return TransitionRegistry(phases=compiled)


def compile_phase_declarations(declarations: Iterable[object]) -> TransitionRegistry:
    return _registry(_compile_declaration(declaration) for declaration in declarations)


def _yaml_scalar(value: str) -> object:
    value = value.strip()
    if not value:
        return None
    if len(value) >= 2 and value[0] == value[-1] == '"':
        return cast(object, json.loads(value))
    if len(value) >= 2 and value[0] == value[-1] == "'":
        return value[1:-1].replace("''", "'")
    return value


def _yaml_pair(text: str, line_number: int) -> tuple[str, object]:
    key, separator, value = text.partition(":")
    if not separator or not key.strip():
        raise ValueError(f"invalid phase contract YAML at line {line_number}")
    return key.strip(), _yaml_scalar(value)


def parse_phase_yaml(text: str) -> dict[str, object]:
    """Parse the deliberately small phase-contract YAML vocabulary.

    Phase declarations are data-only and intentionally use no YAML features
    beyond mappings, scalar lists, and mappings in the outputs list.  Keeping
    this parser in the source tree makes bootstrap generation independent of
    PyYAML and of the generated registry itself.
    """
    data: dict[str, object] = {}
    section: str | None = None
    current_output: dict[str, object] | None = None
    for line_number, raw_line in enumerate(text.splitlines(), 1):
        line = raw_line.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or stripped == "---":
            continue
        indent = len(line) - len(line.lstrip(" "))
        if indent % 2:
            raise ValueError(f"invalid phase contract YAML at line {line_number}")
        if indent == 0:
            key, value = _yaml_pair(stripped, line_number)
            if key in data:
                raise ValueError(f"duplicate field {key!r} at line {line_number}")
            current_output = None
            if key == "contract_version":
                if value is not None:
                    raise ValueError(f"contract_version must be a mapping at line {line_number}")
                data[key] = {}
                section = key
            elif key == "input_schema_uris":
                if value is not None:
                    raise ValueError(f"input_schema_uris must be a list at line {line_number}")
                data[key] = []
                section = key
            elif key == "outputs":
                if value is not None:
                    raise ValueError(f"outputs must be a list at line {line_number}")
                data[key] = []
                section = key
            else:
                data[key] = value
                section = None
            continue

        if indent == 2 and section == "contract_version":
            key, value = _yaml_pair(stripped, line_number)
            section_data = data[section]
            assert isinstance(section_data, dict)
            if key in section_data:
                raise ValueError(f"duplicate field {key!r} at line {line_number}")
            section_data[key] = value
            continue

        if indent == 2 and section == "input_schema_uris":
            if not stripped.startswith("- "):
                raise ValueError(f"invalid input schema list at line {line_number}")
            values = data[section]
            assert isinstance(values, list)
            cast("list[object]", values).append(_yaml_scalar(stripped[2:]))
            continue

        if indent == 2 and section == "outputs":
            if not stripped.startswith("- "):
                raise ValueError(f"invalid output list at line {line_number}")
            key, value = _yaml_pair(stripped[2:], line_number)
            current_output = {key: value}
            outputs = data[section]
            assert isinstance(outputs, list)
            cast("list[object]", outputs).append(current_output)
            continue

        if indent == 4 and section == "outputs" and current_output is not None:
            key, value = _yaml_pair(stripped, line_number)
            if key in current_output:
                raise ValueError(f"duplicate field {key!r} at line {line_number}")
            current_output[key] = value
            continue

        raise ValueError(f"invalid phase contract YAML at line {line_number}")

    return data


def compile_phase_files(paths: Iterable[Path]) -> TransitionRegistry:
    return compile_phase_declarations(
        parse_phase_yaml(path.read_text(encoding="utf-8")) for path in paths
    )




def render_registry_source(registry: TransitionRegistry) -> str:
    return (
        '"""Generated phase registry data; edit skills/*/phase-contract.yaml instead."""\n\n'
        + "from __future__ import annotations\n\n"
        + "PHASE_REGISTRY_DATA = "
        + json.dumps(registry.to_data(), indent=4, sort_keys=True)
        + "\n\nPHASE_REGISTRY_JSON = "
        + repr(registry.to_json())
        + "\n"
    )


def compile_phase_files_to_source(paths: Iterable[Path]) -> str:
    return render_registry_source(compile_phase_files(paths))
