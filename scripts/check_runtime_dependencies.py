"""Validate the offline dependency inventory without loading application configuration."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import math
import re
import sys
from pathlib import Path, PurePosixPath
from typing import Any

from jsonschema import Draft202012Validator
from referencing import Registry

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = "docs/runtime-dependencies.json"
SCHEMA = "docs/runtime-dependencies.schema.json"
MATRIX = "docs/runtime-dependencies.md"
PROFILE = "docs/runtime-dependencies.local-profile.json"
MAX_BYTES = 2_000_000
MAX_DEPTH = 64
SETTINGS_ROOT = "services/api/src/axis_api/settings"
PYTHON_ROOTS = ("services/api/src/axis_api", "services/worker/src/axis_worker")
WEB_ROOTS = ("apps/web/app", "apps/web/lib", "apps/web/components", "apps/web/providers")
TOPOLOGY_GLOBS = (
    "infra/docker/docker-compose*.yml",
    "infra/docker/docker-compose*.yaml",
    "infra/helm/*/Chart.yaml",
    "infra/helm/*/templates/**/*.yaml",
    "infra/helm/*/templates/**/*.yml",
    "infra/helm/*/templates/**/*.tpl",
)
REQUIRED_FILES = (
    "services/api/src/axis_api/config.py",
    "services/api/src/axis_api/s3_source_profile.py",
    "services/worker/src/axis_worker/runtime.py",
    "apps/web/app/layout.tsx",
    "apps/web/lib/api-status.ts",
    "infra/docker/docker-compose.yml",
    "infra/helm/limes-axis/Chart.yaml",
    "infra/helm/limes-axis/templates/configmap.yaml",
)
REQUIRED_COMPONENTS = frozenset(
    ("api", "web", "worker", "postgres", "valkey", "typedb", "temporal", "temporal-ui",
     "minio", "keycloak")
)
NETWORK_WORDS = frozenset(
    ("URL", "URLS", "URI", "URIS", "DSN", "ADDRESS", "ADDRESSES", "HOST", "HOSTS",
     "HOSTNAME", "HOSTNAMES", "ENDPOINT", "ENDPOINTS", "ISSUER", "ORIGIN", "ORIGINS")
)
ENV_TOKEN = re.compile(r"\b(?:NEXT_PUBLIC_)?AXIS_[A-Z0-9_]+\b")


class InventoryError(ValueError):
    """A fixed diagnostic that never includes configuration values or source excerpts."""


def relative_path(value: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if (
        not value or path.is_absolute() or "\\" in value or ":" in value
        or any(part in {"", ".", ".."} for part in value.split("/"))
    ):
        raise InventoryError("invalid_repository_path")
    return path


def safe_path(root: Path, value: str) -> Path:
    relative = relative_path(value)
    current = root.resolve()
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise InventoryError("symlink_not_allowed")
    return current


def read_bytes(root: Path, value: str) -> bytes:
    path = safe_path(root, value)
    try:
        if not path.is_file():
            raise InventoryError("required_file_missing")
        with path.open("rb") as stream:
            data = stream.read(MAX_BYTES + 1)
    except OSError:
        raise InventoryError("file_read_failed") from None
    if len(data) > MAX_BYTES:
        raise InventoryError("file_size_limit")
    return data


def read_text(root: Path, value: str) -> str:
    try:
        return read_bytes(root, value).decode("utf-8")
    except UnicodeError:
        raise InventoryError("invalid_utf8") from None


def read_json(root: Path, value: str) -> Any:
    def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result = {}
        for key, item in pairs:
            if key in result:
                raise InventoryError("duplicate_json_key")
            result[key] = item
        return result

    def nonfinite(_value: str) -> None:
        raise InventoryError("nonfinite_json_number")

    try:
        result = json.loads(
            read_text(root, value), object_pairs_hook=unique, parse_constant=nonfinite
        )
    except (json.JSONDecodeError, RecursionError):
        raise InventoryError("invalid_json") from None
    pending = [(result, 0)]
    while pending:
        item, depth = pending.pop()
        if depth > MAX_DEPTH:
            raise InventoryError("json_depth_limit")
        if isinstance(item, float) and not math.isfinite(item):
            raise InventoryError("nonfinite_json_number")
        if isinstance(item, dict):
            children = item.values()
        elif isinstance(item, list):
            children = item
        else:
            children = ()
        pending.extend((child, depth + 1) for child in children)
    return result


def validate_schema(schema: dict[str, Any], value: Any, definition: str) -> None:
    # Never retrieve a schema URL, even when a future manifest changes a reference.
    pending: list[Any] = [schema]
    while pending:
        item = pending.pop()
        if isinstance(item, dict):
            for key in ("$ref", "$dynamicRef"):
                if key in item and not str(item[key]).startswith("#/"):
                    raise InventoryError("nonlocal_schema_reference")
            pending.extend(item.values())
        elif isinstance(item, list):
            pending.extend(item)
    try:
        Draft202012Validator.check_schema(schema)
        selected = {**schema, "$ref": f"#/$defs/{definition}"}
        validator = Draft202012Validator(selected, registry=Registry())
        if next(validator.iter_errors(value), None) is not None:
            raise InventoryError("schema_validation_failed")
    except InventoryError:
        raise
    except Exception:
        # jsonschema diagnostics may contain the rejected value.
        raise InventoryError("invalid_schema") from None


def endpoint_name(name: str) -> bool:
    return bool(NETWORK_WORDS.intersection(re.split(r"[^A-Z0-9]+", name.upper())))


def parse_python(root: Path, path: str) -> ast.Module:
    try:
        return ast.parse(read_text(root, path), feature_version=(3, 12))
    except (SyntaxError, RecursionError, ValueError):
        raise InventoryError("python_source_parse_failed") from None


def field_key(node: ast.AnnAssign) -> str:
    for candidate in ast.walk(node):
        if isinstance(candidate, ast.Call) and (
            isinstance(candidate.func, ast.Name) and candidate.func.id == "Field"
            or isinstance(candidate.func, ast.Attribute) and candidate.func.attr == "Field"
        ):
            aliases = [
                keyword.value for keyword in candidate.keywords
                if keyword.arg in {"alias", "validation_alias"}
            ]
            if aliases:
                if not all(isinstance(alias, ast.Constant) and isinstance(alias.value, str)
                           for alias in aliases):
                    raise InventoryError("dynamic_setting_alias_requires_review")
                values = {alias.value for alias in aliases}
                if len(values) != 1:
                    raise InventoryError("multiple_setting_aliases_require_review")
                return next(iter(values))
    return node.target.id if isinstance(node.target, ast.Name) else ""


def declared_endpoints(tree: ast.Module, *, prefix: str = "") -> set[str]:
    result = set()
    for owner in tree.body:
        if not isinstance(owner, ast.ClassDef):
            continue
        for field in owner.body:
            if not isinstance(field, ast.AnnAssign) or not isinstance(field.target, ast.Name):
                continue
            if field.target.id == "model_config":
                continue
            key = field_key(field)
            has_url_default = field.value is not None and any(
                isinstance(item, ast.Constant) and isinstance(item.value, str)
                and "://" in item.value
                for item in ast.walk(field.value)
            )
            if endpoint_name(key) or endpoint_name(field.target.id) or has_url_default:
                result.add(f"{prefix}{owner.name}.{field.target.id}" if prefix else key)
            if key == "AXIS_S3_SOURCE_PROFILES":
                result.add(key)
    return result


def environment_endpoints(tree: ast.Module) -> set[str]:
    result = set()
    getters = {"getenv"}
    environments = {"environ"}
    for item in tree.body:
        if isinstance(item, ast.ImportFrom) and item.module == "os":
            getters.update(alias.asname or alias.name for alias in item.names
                           if alias.name == "getenv")
            environments.update(alias.asname or alias.name for alias in item.names
                                if alias.name == "environ")

    def is_environment(node: ast.expr) -> bool:
        return (isinstance(node, ast.Name) and node.id in environments
                or isinstance(node, ast.Attribute) and node.attr == "environ")

    for item in ast.walk(tree):
        key = None
        if isinstance(item, ast.Subscript) and is_environment(item.value):
            key = item.slice
        elif isinstance(item, ast.Call) and item.args:
            function = item.func
            if (isinstance(function, ast.Name) and function.id in getters
                or isinstance(function, ast.Attribute) and function.attr == "getenv"
                or isinstance(function, ast.Attribute) and function.attr == "get"
                and is_environment(function.value)):
                key = item.args[0]
        if (
            isinstance(key, ast.Constant) and isinstance(key.value, str)
            and endpoint_name(key.value)
        ):
            result.add(key.value)
        # Also catch known Axis aliases referenced by wrappers, without executing
        # their source or trying to infer dynamically constructed key names.
        if (
            isinstance(item, ast.Constant) and isinstance(item.value, str)
            and ENV_TOKEN.fullmatch(item.value) and endpoint_name(item.value)
        ):
            result.add(item.value)
    return result


def source_paths(root: Path, directory: str, suffixes: set[str]) -> list[str]:
    base = safe_path(root, directory)
    if not base.is_dir():
        raise InventoryError("required_source_root_missing")
    paths = []
    for path in sorted(base.rglob("*")):
        if path.is_symlink():
            raise InventoryError("symlink_not_allowed")
        if path.suffix not in suffixes or not path.is_file():
            continue
        if any(part in {"__pycache__", "node_modules", ".next", "__tests__"}
               for part in path.relative_to(base).parts):
            continue
        if ".test." in path.name or ".spec." in path.name:
            continue
        paths.append(path.relative_to(root).as_posix())
    return paths


def discover_settings(root: Path) -> set[str]:
    endpoints: set[str] = set()
    settings_paths = source_paths(root, SETTINGS_ROOT, {".py"})
    if not settings_paths:
        raise InventoryError("empty_settings_inventory")
    settings_paths.append("services/api/src/axis_api/config.py")
    for path in settings_paths:
        endpoints.update(declared_endpoints(parse_python(root, path)))
    for directory in PYTHON_ROOTS:
        for path in source_paths(root, directory, {".py"}):
            endpoints.update(environment_endpoints(parse_python(root, path)))
    endpoints.update(declared_endpoints(
        parse_python(root, "services/api/src/axis_api/s3_source_profile.py"), prefix="model:"
    ))
    for directory in WEB_ROOTS:
        for path in source_paths(root, directory, {".ts", ".tsx", ".js", ".jsx", ".mjs"}):
            endpoints.update(key for key in ENV_TOKEN.findall(read_text(root, path))
                             if endpoint_name(key))
    return endpoints


def git_blob_digest(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode("ascii") + b"\0" + data).hexdigest()


def topology_paths(root: Path) -> set[str]:
    paths: set[str] = set()
    for pattern in TOPOLOGY_GLOBS:
        for path in root.glob(pattern):
            relative = path.relative_to(root).as_posix()
            safe_path(root, relative)
            if not path.is_file():
                raise InventoryError("invalid_topology_file")
            paths.add(relative)
    if not paths:
        raise InventoryError("empty_topology_inventory")
    return paths


def validate_inventory(manifest: dict[str, Any], profile: dict[str, Any]) -> None:
    components = [component["id"] for component in manifest["components"]]
    dependencies = [dependency["id"] for dependency in manifest["dependencies"]]
    if len(components) != len(set(components)) or len(dependencies) != len(set(dependencies)):
        raise InventoryError("duplicate_inventory_id")
    if not REQUIRED_COMPONENTS.issubset(components):
        raise InventoryError("required_component_unclassified")
    settings = [key for dependency in manifest["dependencies"] for key in dependency["settings"]]
    if len(settings) != len(set(settings)):
        raise InventoryError("duplicate_setting_owner")
    reviewed = [entry["path"] for entry in manifest["baseline_topology"]]
    if len(reviewed) != len(set(reviewed)):
        raise InventoryError("duplicate_topology_path")
    covered: set[str] = set()
    for dependency in manifest["dependencies"]:
        if not set(dependency["components"]).issubset(components):
            raise InventoryError("unknown_component_reference")
        covered.update(dependency["components"])
        if dependency["requirement"] == "conditional" and not dependency["condition"].strip():
            raise InventoryError("missing_dependency_condition")
        for item in dependency["evidence"]:
            relative_path(item["path"])
        for connection in dependency["connections"]:
            if len(connection["ports"]) != len(set(connection["ports"])):
                raise InventoryError("duplicate_port")
    if covered != set(components):
        raise InventoryError("component_without_dependencies")
    for component in manifest["components"]:
        for path in component["packaged_in"]:
            relative_path(path)
    for path in reviewed:
        relative_path(path)
    bindings = [binding["dependency"] for binding in profile["bindings"]]
    if len(bindings) != len(set(bindings)) or set(bindings) != set(dependencies):
        raise InventoryError("incomplete_profile_bindings")
    by_id = {dependency["id"]: dependency for dependency in manifest["dependencies"]}
    for binding in profile["bindings"]:
        dependency = by_id[binding["dependency"]]
        state = binding["state"]
        if not binding["reason"].strip():
            raise InventoryError("missing_profile_reason")
        if state == "omitted" and dependency["requirement"] == "required":
            raise InventoryError("required_dependency_omitted")
        if state == "local":
            if binding.get("service") != dependency["local_service"]:
                raise InventoryError("unknown_local_service")
            if dependency["local_replacement"]["status"] == "unsupported":
                raise InventoryError("unsupported_local_replacement")
        elif "service" in binding:
            raise InventoryError("unexpected_profile_service")
        if state == "preloaded" and "runtime" in dependency["phases"]:
            raise InventoryError("runtime_dependency_cannot_be_preloaded")
        if state == "bundled" and dependency["connections"]:
            raise InventoryError("network_dependency_cannot_be_bundled")


def cell(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace(
        "|", "&#124;"
    ).replace("\r", " ").replace("\n", " ")


def render_matrix(manifest: dict[str, Any], profile: dict[str, Any]) -> str:
    lines = [
        "# Runtime dependency inventory", "",
        "Generated from `runtime-dependencies.json`; do not edit this matrix by hand.", "",
        f"Inventory source revision: `{manifest['source_revision']}`.", "",
        "This is a static inventory, not deployment accreditation, an egress policy,",
        "a runnable deployment profile or proof that hidden network calls are absent.", "",
        "The checker reads source declarations without importing the API or reading `.env`.",
        "Topology changes require explicit inventory review; their digests are not refreshed",
        "by `--write`. File references identify evidence to inspect, "
        "not tests run by this checker.",
        "See [scope and verification](runtime-dependencies-guide.md) for the exact boundaries.", "",
        "## Packaged components", "",
        "| Component | Owner | Packaging source |", "| --- | --- | --- |",
    ]
    for component in sorted(manifest["components"], key=lambda item: item["id"]):
        lines.append("| " + " | ".join((cell(component["id"]), cell(component["owner"]),
                     ", ".join(f"`{cell(path)}`" for path in sorted(component["packaged_in"]))
                     )) + " |")
    lines.extend(("", "## Dependencies", ""))
    for dependency in sorted(manifest["dependencies"], key=lambda item: item["id"]):
        lines.extend((
            f"### {dependency['id']}", "", cell(dependency["purpose"]), "",
            f"Owner: **{cell(dependency['owner'])}**. Components: "
            + ", ".join(sorted(dependency["components"])) + ".", "",
            f"Phase: {', '.join(sorted(dependency['phases']))}. "
            f"Requirement: **{dependency['requirement']}**. {cell(dependency['condition'])}", "",
            "Configuration references: " + (", ".join(f"`{cell(key)}`"
                for key in sorted(dependency["settings"]))
                or "none; platform or packaged dependency")
            + ".", "",
            "Local option (" + dependency["local_replacement"]["status"] + "): "
            + cell(dependency["local_replacement"]["detail"]), "",
            "Failure behavior: " + cell(dependency["failure_behavior"]), "",
        ))
        for connection in sorted(dependency["connections"], key=lambda item: (
            item["direction"], item["protocol"], sorted(item["ports"]), item["detail"]
        )):
            ports = (
                ", ".join(str(port) for port in sorted(connection["ports"]))
                or "deployment-selected"
            )
            lines.append(
                f"- {connection['direction']}, {cell(connection['protocol'])}, ports {ports}: "
                         + cell(connection["detail"]))
        if dependency["connections"]:
            lines.append("")
        lines.append("Evidence references: " + "; ".join(
            f"{item['kind']} `{cell(item['path'])}`" for item in sorted(
                dependency["evidence"], key=lambda item: (item["path"], item["kind"])
            )
        ) + ".")
        lines.append("")
    lines.extend(("## Local-only planning profile", "", cell(profile["description"]), "",
                  "| Dependency | State | Logical service | Reason |", "| --- | --- | --- | --- |"))
    for binding in sorted(profile["bindings"], key=lambda item: item["dependency"]):
        lines.append("| " + " | ".join(cell(binding.get(key, "—"))
                     for key in ("dependency", "state", "service", "reason")) + " |")
    lines.extend(("", "## Topology review baseline", "",
                  "Git blob digests bind the review baseline to packaging, not live traffic.",
                  "",
                  "| Source | Git blob digest |", "| --- | --- |"))
    for entry in sorted(manifest["baseline_topology"], key=lambda item: item["path"]):
        lines.append(f"| `{cell(entry['path'])}` | `{entry['git_blob']}` |")
    return "\n".join(line.rstrip() for line in lines) + "\n"


def check_repository(root: Path, *, write: bool = False) -> dict[str, int]:
    root = root.resolve()
    schema = read_json(root, SCHEMA)
    manifest = read_json(root, MANIFEST)
    profile = read_json(root, PROFILE)
    validate_schema(schema, manifest, "inventory")
    validate_schema(schema, profile, "profile")
    validate_inventory(manifest, profile)
    for path in REQUIRED_FILES:
        read_bytes(root, path)
    observed = discover_settings(root)
    classified = {key for dependency in manifest["dependencies"] for key in dependency["settings"]}
    if observed - classified:
        raise InventoryError("unclassified_endpoint_setting")
    if classified - observed:
        raise InventoryError("stale_endpoint_classification")
    discovered = topology_paths(root)
    reviewed = {entry["path"]: entry["git_blob"] for entry in manifest["baseline_topology"]}
    if discovered != set(reviewed):
        raise InventoryError("topology_file_set_requires_review")
    for path, digest in reviewed.items():
        if git_blob_digest(read_bytes(root, path)) != digest:
            raise InventoryError("topology_content_requires_review")
    references = {item["path"] for dependency in manifest["dependencies"]
                  for item in dependency["evidence"]}
    references.update(
        path for component in manifest["components"] for path in component["packaged_in"]
    )
    for path in sorted(references):
        read_bytes(root, path)
    rendered = render_matrix(manifest, profile)
    target = safe_path(root, MATRIX)
    if write:
        target.write_text(rendered, encoding="utf-8", newline="\n")
    elif read_text(root, MATRIX) != rendered:
        raise InventoryError("generated_matrix_stale")
    return {
        "components": len(manifest["components"]),
        "dependencies": len(manifest["dependencies"]),
        "configuration_references": len(classified),
        "topology_files": len(reviewed),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument(
        "--write", action="store_true", help="Regenerate the matrix after validation"
    )
    args = parser.parse_args(argv)
    try:
        counts = check_repository(args.root, write=args.write)
    except (InventoryError, OSError) as error:
        code = str(error) if isinstance(error, InventoryError) else "file_write_failed"
        print(f"Dependency inventory FAIL: {code}", file=sys.stderr)
        return 1
    print("Dependency inventory OK (static only): " + ", ".join(
        f"{count} {name}" for name, count in counts.items()
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
