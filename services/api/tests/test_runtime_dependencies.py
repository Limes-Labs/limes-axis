"""Offline dependency inventory checks; synthetic fixtures are not runtime isolation evidence."""

from __future__ import annotations

import ast
import importlib.util
import json
import socket
from copy import deepcopy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = ROOT / "scripts/check_runtime_dependencies.py"
spec = importlib.util.spec_from_file_location("axis_runtime_dependency_inventory", SCRIPT)
assert spec is not None and spec.loader is not None
inventory = importlib.util.module_from_spec(spec)
spec.loader.exec_module(inventory)


@pytest.fixture
def documents():
    return tuple(inventory.read_json(ROOT, name) for name in (
        inventory.SCHEMA, inventory.MANIFEST, inventory.PROFILE
    ))


def put(root: Path, path: str, content: str) -> Path:
    destination = root / path
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(content, encoding="utf-8")
    return destination


def put_json(root: Path, path: str, value) -> None:
    put(root, path, json.dumps(value, indent=2) + "\n")


@pytest.fixture
def repository(tmp_path, documents):
    schema, manifest, profile = deepcopy(documents)
    for directory in (*inventory.PYTHON_ROOTS, *inventory.WEB_ROOTS, inventory.SETTINGS_ROOT):
        (tmp_path / directory).mkdir(parents=True, exist_ok=True)
    paths = set(inventory.REQUIRED_FILES)
    paths.update(entry["path"] for entry in manifest["baseline_topology"])
    paths.update(entry["path"] for dependency in manifest["dependencies"]
                 for entry in dependency["evidence"])
    paths.update(path for component in manifest["components"] for path in component["packaged_in"])
    for path in paths:
        put(tmp_path, path, "# Synthetic inventory fixture; no application behavior.\n")
    settings = sorted(key for dep in manifest["dependencies"] for key in dep["settings"]
                      if not key.startswith(("model:", "NEXT_PUBLIC_"))
                      and key != "AXIS_CSRF_HOST_COOKIE_NAME")
    put(tmp_path, "apps/web/lib/session-csrf.ts",
        inventory.read_text(ROOT, "apps/web/lib/session-csrf.ts"))
    declarations = ["class FixtureSettings:"]
    for index, key in enumerate(settings):
        declarations.append(f'    setting_{index}: str = Field(default=None, alias="{key}")')
    put(tmp_path, inventory.SETTINGS_ROOT + "/fixture.py", "\n".join(declarations) + "\n")
    put(tmp_path, "apps/web/lib/api-status.ts",
        "export const api = process.env.NEXT_PUBLIC_AXIS_API_BASE_URL;\n")
    put(tmp_path, "services/api/src/axis_api/s3_source_profile.py", '''class S3SourceProfile:
    endpoint: str = Field(min_length=1)
    private_endpoint_ref: str = Field(min_length=1)
    credential_secret_ref: str = Field(pattern=r"^env://[A-Z]+$")
''')
    for entry in manifest["baseline_topology"]:
        entry["git_blob"] = inventory.git_blob_digest((tmp_path / entry["path"]).read_bytes())
    for name, value in ((inventory.SCHEMA, schema), (inventory.MANIFEST, manifest),
                        (inventory.PROFILE, profile)):
        put_json(tmp_path, name, value)
    put(tmp_path, inventory.MATRIX, inventory.render_matrix(manifest, profile))
    return tmp_path


def test_repository_inventory():
    """Integration gate: requires the complete checkout, not the synthetic fixture."""
    inventory.check_repository(ROOT)


def test_synthetic_complete_inventory_passes(repository):
    counts = inventory.check_repository(repository)
    assert counts == {"components": 10, "dependencies": 21, "configuration_references": 29,
                      "topology_files": 17}


def test_csrf_host_cookie_constant_has_console_origin_owner(documents):
    _, manifest, _ = documents
    owners = [dependency for dependency in manifest["dependencies"]
              if "AXIS_CSRF_HOST_COOKIE_NAME" in dependency["settings"]]
    assert len(owners) == 1
    assert owners[0]["id"] == "console-origin"
    assert {"path": "apps/web/lib/session-csrf.ts", "kind": "source"} in owners[0]["evidence"]
    assert "not an environment setting or remote host" in owners[0]["purpose"]


def test_unclassified_csrf_host_cookie_constant_requires_review(repository):
    manifest = inventory.read_json(repository, inventory.MANIFEST)
    owner = next(dep for dep in manifest["dependencies"] if dep["id"] == "console-origin")
    owner["settings"].remove("AXIS_CSRF_HOST_COOKIE_NAME")
    put_json(repository, inventory.MANIFEST, manifest)
    with pytest.raises(inventory.InventoryError, match="unclassified_endpoint_setting"):
        inventory.check_repository(repository)


def test_removed_csrf_host_cookie_constant_is_stale(repository):
    put(repository, "apps/web/lib/session-csrf.ts", "export {};\n")
    with pytest.raises(inventory.InventoryError, match="stale_endpoint_classification"):
        inventory.check_repository(repository)


def test_manifest_and_profile_conform_to_bundled_schema(documents):
    schema, manifest, profile = documents
    inventory.validate_schema(schema, manifest, "inventory")
    inventory.validate_schema(schema, profile, "profile")
    inventory.validate_inventory(manifest, profile)


@pytest.mark.parametrize("version", [0, 2, True, "1", None])
def test_schema_rejects_invalid_version(documents, version):
    schema, manifest, _ = deepcopy(documents)
    manifest["schema_version"] = version
    with pytest.raises(inventory.InventoryError, match="schema_validation_failed"):
        inventory.validate_schema(schema, manifest, "inventory")


@pytest.mark.parametrize("content,code", [
    ('{"a":1,"a":2}', "duplicate_json_key"),
    ('{"a":NaN}', "nonfinite_json_number"),
    ('{"a":Infinity}', "nonfinite_json_number"),
    ('{"a":1e999}', "nonfinite_json_number"),
    ('{"a":-Infinity}', "nonfinite_json_number"),
    ('{BROKEN_SENTINEL', "invalid_json"),
])
def test_bad_json_is_rejected_without_values(tmp_path, content, code):
    put(tmp_path, "input.json", content)
    with pytest.raises(inventory.InventoryError, match=code) as caught:
        inventory.read_json(tmp_path, "input.json")
    assert "SENTINEL" not in str(caught.value)


def test_json_depth_limit(tmp_path):
    put(tmp_path, "input.json", "[" * 70 + "0" + "]" * 70)
    with pytest.raises(inventory.InventoryError, match="json_depth_limit"):
        inventory.read_json(tmp_path, "input.json")


def test_json_size_limit(tmp_path):
    put(tmp_path, "input.json", " " * (inventory.MAX_BYTES + 1))
    with pytest.raises(inventory.InventoryError, match="file_size_limit"):
        inventory.read_json(tmp_path, "input.json")


def test_invalid_utf8(tmp_path):
    (tmp_path / "input.json").write_bytes(b"\xff")
    with pytest.raises(inventory.InventoryError, match="invalid_utf8"):
        inventory.read_json(tmp_path, "input.json")


@pytest.mark.parametrize("path", ["/etc/passwd", "../outside", "docs/../outside", "docs//x",
                                  "docs/./x", "docs\\x", "https://example.invalid/x", ""])
def test_path_escape_and_ambiguous_paths_rejected(tmp_path, path):
    with pytest.raises(inventory.InventoryError, match="invalid_repository_path"):
        inventory.safe_path(tmp_path, path)


def test_symlink_file_rejected(tmp_path):
    put(tmp_path, "target", "sentinel")
    (tmp_path / "link").symlink_to(tmp_path / "target")
    with pytest.raises(inventory.InventoryError, match="symlink_not_allowed"):
        inventory.read_bytes(tmp_path, "link")


def test_symlink_directory_rejected(tmp_path):
    put(tmp_path, "target/file", "sentinel")
    (tmp_path / "link").symlink_to(tmp_path / "target", target_is_directory=True)
    with pytest.raises(inventory.InventoryError, match="symlink_not_allowed"):
        inventory.read_bytes(tmp_path, "link/file")


def test_remote_schema_reference_cannot_trigger_network(documents, monkeypatch):
    schema, manifest, _ = deepcopy(documents)
    calls = []

    def forbidden(*args, **kwargs):
        calls.append((args, kwargs))
        raise AssertionError("network must not be used")

    monkeypatch.setattr(socket, "create_connection", forbidden)
    schema["$defs"]["inventory"]["properties"]["schema_version"] = {
        "$ref": "https://schema.invalid/private-sentinel"
    }
    with pytest.raises(inventory.InventoryError, match="nonlocal_schema_reference"):
        inventory.validate_schema(schema, manifest, "inventory")
    assert not calls


def test_invalid_schema_hides_rejected_schema_content(documents):
    schema, manifest, _ = deepcopy(documents)
    schema["$defs"]["inventory"]["properties"]["schema_version"] = {"type": "SCHEMA_SENTINEL"}
    with pytest.raises(inventory.InventoryError, match="invalid_schema") as caught:
        inventory.validate_schema(schema, manifest, "inventory")
    assert "SCHEMA_SENTINEL" not in str(caught.value)


@pytest.mark.parametrize("key", ["AXIS_NEW_URL", "AXIS_NEW_URI", "AXIS_NEW_DSN", "AXIS_NEW_HOST",
                                "AXIS_NEW_ADDRESS", "AXIS_NEW_ENDPOINT", "AXIS_NEW_ISSUER",
                                "AXIS_NEW_ORIGINS", "AXIS_NEW_HOSTNAME"])
def test_new_endpoint_setting_fails(repository, key):
    put(repository, inventory.SETTINGS_ROOT + "/new.py",
        f'class Added:\n    target: str = Field(default="VALUE_SENTINEL", alias="{key}")\n')
    with pytest.raises(inventory.InventoryError, match="unclassified_endpoint_setting") as caught:
        inventory.check_repository(repository)
    assert "VALUE_SENTINEL" not in str(caught.value)


def test_url_default_without_endpoint_name_requires_review(repository):
    put(repository, inventory.SETTINGS_ROOT + "/new.py",
        'class Added:\n'
        '    target: str = Field(default="https://VALUE_SENTINEL.invalid", alias="AXIS_BACKEND")\n')
    with pytest.raises(inventory.InventoryError, match="unclassified_endpoint_setting"):
        inventory.check_repository(repository)


def test_non_network_setting_does_not_require_inventory_edit(repository):
    put(repository, inventory.SETTINGS_ROOT + "/new.py",
        'class Added:\n    capacity: int = Field(default=100, alias="AXIS_POOL_CAPACITY")\n')
    inventory.check_repository(repository)


def test_new_worker_environment_endpoint_requires_review(repository):
    put(repository, "services/worker/src/axis_worker/new.py",
        'import os\ntarget = os.environ["AXIS_NEW_QUEUE_URL"]\n')
    with pytest.raises(inventory.InventoryError, match="unclassified_endpoint_setting"):
        inventory.check_repository(repository)


def test_bracket_web_environment_endpoint_requires_review(repository):
    put(repository, "apps/web/lib/new.ts",
        'const target = process.env["NEXT_PUBLIC_AXIS_NEW_URL"];\n')
    with pytest.raises(inventory.InventoryError, match="unclassified_endpoint_setting"):
        inventory.check_repository(repository)


def test_nested_s3_endpoint_field_requires_review(repository):
    with (repository / "services/api/src/axis_api/s3_source_profile.py").open("a") as stream:
        stream.write('    fallback_url: str = Field(default=None)\n')
    with pytest.raises(inventory.InventoryError, match="unclassified_endpoint_setting"):
        inventory.check_repository(repository)


def test_annotated_field_alias_is_discovered():
    tree = ast.parse(
        'class Config:\n    target: Annotated[str, Field(alias="AXIS_CALLBACK_URL")]\n'
    )
    assert inventory.declared_endpoints(tree) == {"AXIS_CALLBACK_URL"}


def test_unaliased_endpoint_is_not_ignored():
    tree = ast.parse('class Config:\n    callback_url: str = ""\n')
    assert inventory.declared_endpoints(tree) == {"callback_url"}


@pytest.mark.parametrize("expression", ['get_alias()', 'AliasChoices("AXIS_A_URL", "AXIS_B_URL")'])
def test_dynamic_alias_requires_explicit_review(expression):
    tree = ast.parse(f'class Config:\n    target_url: str = Field(alias={expression})\n')
    with pytest.raises(inventory.InventoryError, match="dynamic_setting_alias_requires_review"):
        inventory.declared_endpoints(tree)


def test_conflicting_alias_and_validation_alias_fail():
    tree = ast.parse(
        'class Config:\n'
        '    target_url: str = Field(alias="AXIS_A_URL", validation_alias="AXIS_B_URL")\n'
    )
    with pytest.raises(inventory.InventoryError, match="multiple_setting_aliases_require_review"):
        inventory.declared_endpoints(tree)


def test_source_is_parsed_not_executed(repository):
    put(repository, inventory.SETTINGS_ROOT + "/not_executed.py",
        'raise RuntimeError("SOURCE_EXECUTION_SENTINEL")\n')
    put(repository, ".env", "AXIS_NEW_URL=ENV_FILE_SENTINEL\n")
    inventory.check_repository(repository)


def test_source_syntax_failure_does_not_expose_excerpt(repository):
    put(repository, inventory.SETTINGS_ROOT + "/broken.py", "SOURCE_SECRET_SENTINEL (\n")
    with pytest.raises(inventory.InventoryError, match="python_source_parse_failed") as caught:
        inventory.check_repository(repository)
    assert "SOURCE_SECRET_SENTINEL" not in str(caught.value)


def test_test_only_environment_keys_are_not_runtime_entries(repository):
    put(repository, "apps/web/lib/example.test.ts", 'const x = "NEXT_PUBLIC_AXIS_FIXTURE_URL";\n')
    put(repository, "apps/web/lib/__tests__/helpers.ts",
        'const x = "NEXT_PUBLIC_AXIS_FIXTURE_URL";\n')
    inventory.check_repository(repository)


def test_removed_setting_is_rejected(repository):
    path = repository / "apps/web/lib/api-status.ts"
    path.write_text("// The endpoint reference was removed.\n")
    with pytest.raises(inventory.InventoryError, match="stale_endpoint_classification"):
        inventory.check_repository(repository)


@pytest.mark.parametrize("path", inventory.REQUIRED_FILES)
def test_missing_required_file_is_not_a_pass(repository, path):
    (repository / path).unlink()
    with pytest.raises(inventory.InventoryError, match="required_file_missing"):
        inventory.check_repository(repository)


def test_missing_source_root_is_not_a_pass(repository):
    (repository / "apps/web/providers").rmdir()
    with pytest.raises(inventory.InventoryError, match="required_source_root_missing"):
        inventory.check_repository(repository)


def test_empty_settings_inventory_is_not_a_pass(repository):
    for path in (repository / inventory.SETTINGS_ROOT).rglob("*.py"):
        path.unlink()
    with pytest.raises(inventory.InventoryError, match="empty_settings_inventory"):
        inventory.check_repository(repository)


def test_new_packaged_component_requires_topology_review(repository):
    put(repository, "infra/helm/limes-axis/templates/new-deployment.yaml", "kind: Deployment\n")
    with pytest.raises(inventory.InventoryError, match="topology_file_set_requires_review"):
        inventory.check_repository(repository)


def test_additional_compose_profile_requires_review(repository):
    put(repository, "infra/docker/docker-compose-extra.yaml", "services: {}\n")
    with pytest.raises(inventory.InventoryError, match="topology_file_set_requires_review"):
        inventory.check_repository(repository)


def test_new_chart_requires_review(repository):
    put(repository, "infra/helm/extra/Chart.yaml", "apiVersion: v2\n")
    with pytest.raises(inventory.InventoryError, match="topology_file_set_requires_review"):
        inventory.check_repository(repository)


def test_removed_topology_file_requires_review(repository):
    (repository / "infra/helm/limes-axis/templates/hpa.yaml").unlink()
    with pytest.raises(inventory.InventoryError, match="topology_file_set_requires_review"):
        inventory.check_repository(repository)


def test_changed_topology_requires_review_and_write_cannot_refresh_it(repository):
    manifest_before = (repository / inventory.MANIFEST).read_bytes()
    matrix_before = (repository / inventory.MATRIX).read_bytes()
    with (repository / "infra/docker/docker-compose.yml").open("a") as stream:
        stream.write("# A packaging change that needs review.\n")
    with pytest.raises(inventory.InventoryError, match="topology_content_requires_review"):
        inventory.check_repository(repository, write=True)
    assert (repository / inventory.MANIFEST).read_bytes() == manifest_before
    assert (repository / inventory.MATRIX).read_bytes() == matrix_before


def test_git_blob_hash_matches_git_empty_blob():
    assert inventory.git_blob_digest(b"") == "e69de29bb2d1d6434b8b29ae775ad8c2e48c5391"


def test_missing_evidence_file_fails(repository):
    (repository / "services/api/tests/test_object_storage.py").unlink()
    with pytest.raises(inventory.InventoryError, match="required_file_missing"):
        inventory.check_repository(repository)


def test_duplicate_component_fails(documents):
    _, manifest, profile = deepcopy(documents)
    manifest["components"].append(manifest["components"][0])
    with pytest.raises(inventory.InventoryError, match="duplicate_inventory_id"):
        inventory.validate_inventory(manifest, profile)


def test_duplicate_dependency_fails(documents):
    _, manifest, profile = deepcopy(documents)
    manifest["dependencies"].append(manifest["dependencies"][0])
    with pytest.raises(inventory.InventoryError, match="duplicate_inventory_id"):
        inventory.validate_inventory(manifest, profile)


def test_missing_packaged_component_fails(documents):
    _, manifest, profile = deepcopy(documents)
    manifest["components"] = [
        component for component in manifest["components"] if component["id"] != "valkey"
    ]
    with pytest.raises(inventory.InventoryError, match="required_component_unclassified"):
        inventory.validate_inventory(manifest, profile)


def test_duplicate_setting_owner_fails(documents):
    _, manifest, profile = deepcopy(documents)
    manifest["dependencies"][1]["settings"].append(manifest["dependencies"][0]["settings"][0])
    with pytest.raises(inventory.InventoryError, match="duplicate_setting_owner"):
        inventory.validate_inventory(manifest, profile)


def test_unknown_component_reference_fails(documents):
    _, manifest, profile = deepcopy(documents)
    manifest["dependencies"][0]["components"].append("unclassified")
    with pytest.raises(inventory.InventoryError, match="unknown_component_reference"):
        inventory.validate_inventory(manifest, profile)


def test_conditional_dependency_requires_reason(documents):
    _, manifest, profile = deepcopy(documents)
    dep = next(dep for dep in manifest["dependencies"] if dep["requirement"] == "conditional")
    dep["condition"] = " "
    with pytest.raises(inventory.InventoryError, match="missing_dependency_condition"):
        inventory.validate_inventory(manifest, profile)


def test_duplicate_topology_entry_fails(documents):
    _, manifest, profile = deepcopy(documents)
    manifest["baseline_topology"].append(manifest["baseline_topology"][0])
    with pytest.raises(inventory.InventoryError, match="duplicate_topology_path"):
        inventory.validate_inventory(manifest, profile)


@pytest.mark.parametrize("change", ["missing", "duplicate", "unknown"])
def test_profile_must_cover_every_dependency_once(documents, change):
    _, manifest, profile = deepcopy(documents)
    if change == "missing":
        profile["bindings"].pop()
    elif change == "duplicate":
        profile["bindings"].append(profile["bindings"][0])
    else:
        profile["bindings"][0]["dependency"] = "unknown"
    with pytest.raises(inventory.InventoryError, match="incomplete_profile_bindings"):
        inventory.validate_inventory(manifest, profile)


def test_profile_cannot_omit_required_dependency(documents):
    _, manifest, profile = deepcopy(documents)
    profile["bindings"][0] = {"dependency": "control-api", "state": "omitted", "reason": "Absent"}
    with pytest.raises(inventory.InventoryError, match="required_dependency_omitted"):
        inventory.validate_inventory(manifest, profile)


def test_profile_omission_requires_substantive_reason(documents):
    _, manifest, profile = deepcopy(documents)
    omitted = next(binding for binding in profile["bindings"] if binding["state"] == "omitted")
    omitted["reason"] = " "
    with pytest.raises(inventory.InventoryError, match="missing_profile_reason"):
        inventory.validate_inventory(manifest, profile)


def test_profile_local_service_must_match_manifest(documents):
    _, manifest, profile = deepcopy(documents)
    profile["bindings"][0]["service"] = "unexpected-host"
    with pytest.raises(inventory.InventoryError, match="unknown_local_service"):
        inventory.validate_inventory(manifest, profile)


def test_profile_cannot_claim_unsupported_local_option(documents):
    _, manifest, profile = deepcopy(documents)
    manifest["dependencies"][0]["local_replacement"]["status"] = "unsupported"
    with pytest.raises(inventory.InventoryError, match="unsupported_local_replacement"):
        inventory.validate_inventory(manifest, profile)


def test_omitted_profile_entry_cannot_carry_endpoint(documents):
    _, manifest, profile = deepcopy(documents)
    omitted = next(binding for binding in profile["bindings"] if binding["state"] == "omitted")
    omitted["service"] = "host"
    with pytest.raises(inventory.InventoryError, match="unexpected_profile_service"):
        inventory.validate_inventory(manifest, profile)


def test_runtime_dependency_cannot_be_disguised_as_preloaded(documents):
    _, manifest, profile = deepcopy(documents)
    binding = profile["bindings"][0]
    binding.pop("service")
    binding["state"] = "preloaded"
    with pytest.raises(inventory.InventoryError, match="runtime_dependency_cannot_be_preloaded"):
        inventory.validate_inventory(manifest, profile)


def test_network_service_cannot_be_disguised_as_bundled_asset(documents):
    _, manifest, profile = deepcopy(documents)
    binding = profile["bindings"][0]
    binding.pop("service")
    binding["state"] = "bundled"
    with pytest.raises(inventory.InventoryError, match="network_dependency_cannot_be_bundled"):
        inventory.validate_inventory(manifest, profile)


@pytest.mark.parametrize(
    "unsafe", ["https://customer.invalid", "admin@example.invalid", "10.2.3.4"]
)
def test_profile_does_not_accept_literal_endpoint_or_account(documents, unsafe):
    schema, _, profile = deepcopy(documents)
    profile["bindings"][0]["reason"] = unsafe
    with pytest.raises(inventory.InventoryError, match="schema_validation_failed"):
        inventory.validate_schema(schema, profile, "profile")


@pytest.mark.parametrize("extra", ["secret", "url", "env", "token", "password", "sovereign"])
def test_profile_forbids_ad_hoc_values_and_certification_flags(documents, extra):
    schema, _, profile = deepcopy(documents)
    profile[extra] = "VALUE_SENTINEL"
    with pytest.raises(inventory.InventoryError, match="schema_validation_failed") as caught:
        inventory.validate_schema(schema, profile, "profile")
    assert "VALUE_SENTINEL" not in str(caught.value)


def test_generated_matrix_staleness_is_detected(repository):
    put(repository, inventory.MATRIX, "STALE\n")
    with pytest.raises(inventory.InventoryError, match="generated_matrix_stale"):
        inventory.check_repository(repository)


def test_write_regenerates_only_the_matrix_after_successful_checks(repository):
    original = (repository / inventory.MANIFEST).read_bytes()
    put(repository, inventory.MATRIX, "STALE\n")
    inventory.check_repository(repository, write=True)
    inventory.check_repository(repository)
    assert (repository / inventory.MANIFEST).read_bytes() == original


def test_render_is_deterministic(documents):
    _, manifest, profile = deepcopy(documents)
    first = inventory.render_matrix(manifest, profile)
    manifest["dependencies"].reverse()
    manifest["components"].reverse()
    manifest["baseline_topology"].reverse()
    profile["bindings"].reverse()
    assert inventory.render_matrix(manifest, profile) == first


def test_document_cells_cannot_break_tables():
    assert inventory.cell("a|b\n<script>") == "a&#124;b &lt;script&gt;"


def test_cli_success(repository, capsys):
    assert inventory.main(["--root", str(repository)]) == 0
    assert "static only" in capsys.readouterr().out


def test_cli_reports_failure_without_false_success(repository, capsys):
    put(repository, inventory.MATRIX, "STALE\n")
    assert inventory.main(["--root", str(repository)]) == 1
    captured = capsys.readouterr()
    assert "generated_matrix_stale" in captured.err
    assert "OK" not in captured.out


@pytest.mark.parametrize("expression", [
    'os.getenv("OTHER_SERVICE_URL")',
    'os.environ["OTHER_SERVICE_URL"]',
    'os.environ.get("OTHER_SERVICE_URL")',
    'getenv("OTHER_SERVICE_URL")',
    'read_env("OTHER_SERVICE_URL")',
    'environment["OTHER_SERVICE_URL"]',
])
def test_non_axis_environment_key_is_discovered(expression):
    tree = ast.parse(
        'from os import getenv as read_env, environ as environment\n'
        f'target = {expression}\n'
    )
    assert inventory.environment_endpoints(tree) == {"OTHER_SERVICE_URL"}


def test_url_default_declared_in_flat_facade_is_discovered(repository):
    put(repository, "services/api/src/axis_api/config.py",
        'class Settings:\n'
        '    target: str = Field(default="https://local.invalid", alias="AXIS_BACKEND")\n')
    with pytest.raises(inventory.InventoryError, match="unclassified_endpoint_setting"):
        inventory.check_repository(repository)



def test_generated_document_has_no_trailing_whitespace(documents):
    _, manifest, profile = documents
    rendered = inventory.render_matrix(manifest, profile)
    assert all(line == line.rstrip() for line in rendered.splitlines())
