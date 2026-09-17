"""Contract tests for the #829 Document Studio document/template contracts."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from axis_api.document_studio_contracts import (
    DocumentBlock,
    DocumentRevision,
    DocumentSection,
    DocumentStudioError,
    DocumentTemplate,
    EmbedSlot,
    ManifestVersion,
    PageLayout,
    TemplateParameter,
    TemplateProvenance,
    TemplateRegion,
    ThemeTokens,
    canonical_document_digest,
    delete_template,
    document_accessibility_outline,
    edit_document,
    instantiate_template,
    parse_document_contract,
    parse_template_contract,
    publish_document,
    publish_template,
    revise_document,
    revise_template,
    verify_template_lineage,
)

_NOW_PUBLISH = "2026-09-10T08:00:00Z"
_NOW_INSTANTIATE = "2026-09-11T08:00:00Z"


def _template_sections() -> tuple[DocumentSection, ...]:
    return (
        DocumentSection(
            section_id="sec-summary",
            title="Executive summary",
            blocks=(
                DocumentBlock(
                    block_id="blk-title", kind="heading", heading_level=1, text="Executive briefing"
                ),
                DocumentBlock(block_id="blk-summary", kind="text", text="Summary body"),
                DocumentBlock(
                    block_id="blk-chart",
                    kind="embed_placeholder",
                    embed=EmbedSlot(slot_id="slot-trend", embed_kind="line-chart"),
                ),
                DocumentBlock(
                    block_id="blk-photo",
                    kind="media",
                    media_ref="media/plant-floor.jpg",
                    alt_text="Plant floor",
                ),
                DocumentBlock(block_id="blk-divider", kind="divider"),
            ),
        ),
        DocumentSection(
            section_id="sec-detail",
            title="Operational detail",
            blocks=(
                DocumentBlock(block_id="blk-findings", kind="text", text="Findings body"),
                DocumentBlock(
                    block_id="blk-metrics",
                    kind="table",
                    table_columns=2,
                    table_rows=(("metric", "value"), ("oee", "0.91")),
                ),
                DocumentBlock(block_id="blk-break", kind="page_break"),
                DocumentBlock(
                    block_id="blk-note", kind="callout", text="Reviewed by operations"
                ),
            ),
        ),
    )


def _template() -> DocumentTemplate:
    return DocumentTemplate(
        schema_version=ManifestVersion(major=1, minor=0),
        template_id="tpl-briefing",
        revision="1",
        title="Executive briefing template",
        description="Reusable monthly briefing skeleton",
        parameters=(
            TemplateParameter(
                name="period",
                kind="string",
                required=True,
                description="Reporting period label",
            ),
            TemplateParameter(
                name="risk_threshold",
                kind="number",
                required=False,
                description="Risk threshold shown in the summary",
                default="0.8",
            ),
            TemplateParameter(
                name="data_source",
                kind="governed_ref",
                required=False,
                description="Governed reference backing the summary chart",
                default="refs/quality/monthly",
            ),
        ),
        regions=(
            TemplateRegion(region_id="reg-head", kind="fixed", block_ids=("blk-title",)),
            TemplateRegion(region_id="reg-summary", kind="required", block_ids=("blk-summary",)),
            TemplateRegion(
                region_id="reg-detail", kind="editable", block_ids=("blk-findings", "blk-note")
            ),
        ),
        page=PageLayout(orientation="portrait", page_size="a4", margin_mm=18, columns=1),
        theme=ThemeTokens(accent="signal-blue", ink="ink-default"),
        sections=_template_sections(),
        state="draft",
    )


def _published_template(revision: str = "1") -> DocumentTemplate:
    return publish_template(_template(), now=_NOW_PUBLISH)


def _instantiate(template: DocumentTemplate, **overrides: object) -> DocumentRevision:
    values: dict[str, object] = {
        "document_id": "doc-september",
        "title": "September executive briefing",
        "locale": "en",
        "parameter_values": {"period": "September 2026"},
        "content": {
            "blk-summary": "Throughput recovered after the packaging line changeover.",
            "blk-findings": "Two findings closed, one carried forward.",
        },
    }
    values.update(overrides)
    return instantiate_template(template, **values)  # type: ignore[arg-type]


# --- schema definition and template publication ------------------------------


def test_published_template_freezes_revision_digest() -> None:
    template = _published_template()
    assert template.state == "published"
    assert template.issued_at == _NOW_PUBLISH
    assert template.digest() == canonical_document_digest(template.model_dump(mode="json"))


def test_template_digest_changes_when_content_changes() -> None:
    published = _published_template()
    revised = DocumentTemplate.model_validate(
        {**published.model_dump(mode="json"), "revision": "2", "state": "draft", "issued_at": None}
    )
    revised = publish_template(revised, now="2026-09-12T08:00:00Z")
    assert revised.digest() != published.digest()


def test_major_version_bump_is_rejected() -> None:
    with pytest.raises(ValidationError, match="Unsupported document contract version"):
        ManifestVersion(major=2, minor=0)


# --- instantiation and provenance --------------------------------------------


def test_instantiation_twice_with_different_bindings_stays_verifiable() -> None:
    template = _published_template()
    first = _instantiate(
        template, document_id="doc-september", parameter_values={"period": "September 2026"}
    )
    second = _instantiate(
        template, document_id="doc-october", parameter_values={"period": "October 2026"}
    )
    assert first.template_provenance is not None
    assert second.template_provenance is not None
    assert first.template_provenance.template_digest == template.content_digest()
    assert first.parameter_values["period"] != second.parameter_values["period"]
    assert verify_template_lineage(first, template) and verify_template_lineage(second, template)


def test_published_document_binds_to_original_template_revision() -> None:
    template_v1 = _published_template("1")
    document = publish_document(_instantiate(template_v1), now="2026-09-13T08:00:00Z")
    revised_v2 = DocumentTemplate.model_validate(
        {
            **template_v1.model_dump(mode="json"),
            "revision": "2",
            "state": "draft",
            "issued_at": None,
        }
    )
    revised_v2 = publish_template(revised_v2, now="2026-09-14T08:00:00Z")
    assert not verify_template_lineage(document, revised_v2)
    assert verify_template_lineage(document, template_v1)


def test_deleted_template_keeps_historical_lineage() -> None:
    template = _published_template()
    document = publish_document(_instantiate(template), now="2026-09-13T08:00:00Z")
    deleted = delete_template(template, now="2026-09-15T08:00:00Z")
    assert deleted.state == "deleted" and deleted.deleted_at is not None
    assert verify_template_lineage(document, deleted)
    with pytest.raises(DocumentStudioError) as blocked:
        _instantiate(deleted)
    assert blocked.value.code == DocumentStudioError.DELETED_TEMPLATE


def test_draft_template_cannot_be_instantiated() -> None:
    with pytest.raises(DocumentStudioError) as blocked:
        _instantiate(_template())
    assert blocked.value.code == DocumentStudioError.NOT_PUBLISHED


# --- parameter and region discipline -----------------------------------------


def test_missing_required_parameter_blocks_instantiation() -> None:
    template = _published_template()
    with pytest.raises(DocumentStudioError) as blocked:
        _instantiate(template, parameter_values={})
    assert blocked.value.code == DocumentStudioError.INCOMPATIBLE_INSTANTIATION


def test_unknown_parameter_is_rejected() -> None:
    template = _published_template()
    with pytest.raises(DocumentStudioError) as blocked:
        _instantiate(template, parameter_values={"period": "Q3", "unknown": "x"})
    assert blocked.value.code == DocumentStudioError.INCOMPATIBLE_INSTANTIATION


def test_parameter_type_violations_are_rejected() -> None:
    template = _published_template()
    with pytest.raises(DocumentStudioError) as blocked:
        _instantiate(template, parameter_values={"period": "Q3", "risk_threshold": "high"})
    assert blocked.value.code == DocumentStudioError.INVALID_PARAMETER


def test_parameter_cannot_carry_script_payload() -> None:
    template = _published_template()
    with pytest.raises(DocumentStudioError) as blocked:
        _instantiate(template, parameter_values={"period": "{{request.session}}"})
    assert blocked.value.code == DocumentStudioError.INVALID_PARAMETER


def test_fixed_region_content_cannot_be_overridden() -> None:
    template = _published_template()
    with pytest.raises(DocumentStudioError) as blocked:
        _instantiate(template, content={"blk-title": "Injected title"})
    assert blocked.value.code == DocumentStudioError.INCOMPATIBLE_INSTANTIATION


def test_required_region_must_be_fulfilled() -> None:
    template = _published_template()
    with pytest.raises(DocumentStudioError) as blocked:
        _instantiate(template, content={})
    assert blocked.value.code == DocumentStudioError.INCOMPATIBLE_INSTANTIATION


def test_editable_region_content_replaces_text() -> None:
    template = _published_template()
    document = _instantiate(template, content={"blk-summary": "Replaced summary"})
    summary = next(
        block
        for section in document.sections
        for block in section.blocks
        if block.block_id == "blk-summary"
    )
    assert summary.text == "Replaced summary"


def test_governed_ref_rejects_traversal() -> None:
    template = _published_template()
    with pytest.raises(DocumentStudioError) as blocked:
        _instantiate(
            template,
            parameter_values={"period": "Q3", "data_source": "refs/../secret"},
        )
    assert blocked.value.code == DocumentStudioError.INVALID_PARAMETER


def test_embed_binding_ref_rejects_traversal() -> None:
    with pytest.raises(ValidationError):
        DocumentBlock(
            block_id="blk-slot",
            kind="embed_placeholder",
            embed=EmbedSlot(slot_id="slot-x", embed_kind="table", binding_ref="a/../b"),
        )


def test_revise_template_starts_draft_and_keeps_documents_bound() -> None:
    template_v1 = _published_template("1")
    document = publish_document(_instantiate(template_v1), now="2026-09-13T08:00:00Z")
    draft_v2 = revise_template(template_v1)
    assert draft_v2.revision == "2"
    assert draft_v2.state == "draft" and draft_v2.issued_at is None
    assert verify_template_lineage(document, template_v1)
    published_v2 = publish_template(draft_v2, now="2026-09-14T08:00:00Z")
    assert not verify_template_lineage(document, published_v2)
    assert verify_template_lineage(document, template_v1)


def test_template_regions_must_reference_real_blocks() -> None:
    with pytest.raises(ValidationError, match="regions must reference existing block IDs"):
        DocumentTemplate.model_validate(
            {
                **_template().model_dump(mode="json"),
                "regions": (
                    TemplateRegion(
                        region_id="reg-ghost", kind="editable", block_ids=("blk-ghost",)
                    ),
                ),
            }
        )


# --- lifecycle immutability ---------------------------------------------------


def test_published_document_cannot_be_edited() -> None:
    document = publish_document(_instantiate(_published_template()), now="2026-09-13T08:00:00Z")
    with pytest.raises(DocumentStudioError) as blocked:
        edit_document(document, {"title": "Rewritten"})
    assert blocked.value.code == DocumentStudioError.IMMUTABLE_REVISION


def test_editing_creates_new_revision_without_rewriting_bytes() -> None:
    document = publish_document(_instantiate(_published_template()), now="2026-09-13T08:00:00Z")
    draft = revise_document(document)
    assert draft.revision == "2" and draft.state == "draft" and draft.issued_at is None
    assert document.state == "published" and document.issued_at == "2026-09-13T08:00:00Z"
    assert draft.digest() != document.digest()


def test_edit_document_cannot_bypass_lifecycle() -> None:
    draft = _instantiate(_published_template())
    with pytest.raises(DocumentStudioError) as blocked:
        edit_document(draft, {"state": "published", "issued_at": _NOW_INSTANTIATE})
    assert blocked.value.code == DocumentStudioError.IMMUTABLE_REVISION


def test_publish_document_stamps_issuance_and_digest() -> None:
    draft = _instantiate(_published_template())
    published = publish_document(draft, now="2026-09-13T08:00:00Z")
    assert published.state == "published" and published.issued_at == "2026-09-13T08:00:00Z"
    assert published.digest() != draft.digest()
    with pytest.raises(DocumentStudioError):
        publish_document(published, now="2026-09-14T08:00:00Z")


def test_document_without_template_cannot_carry_parameter_values() -> None:
    standalone = DocumentRevision(
        schema_version=ManifestVersion(major=1, minor=0),
        document_id="doc-memo",
        revision="1",
        title="Standalone memo",
        locale="en",
        state="draft",
        page=PageLayout(),
        theme=ThemeTokens(),
        sections=_template_sections()[:1],
    )
    with pytest.raises(ValidationError, match="no template parameters"):
        DocumentRevision.model_validate(
            {**standalone.model_dump(mode="json"), "parameter_values": {"period": "Q3"}}
        )


# --- content safety -----------------------------------------------------------


@pytest.mark.parametrize(
    "payload",
    [
        "<script>alert(1)</script>",
        "ok {{evil}}",
        "a ${lookup} b",
        "javascript:alert(1)",
        "<iframe src=//x>",
    ],
)
def test_authored_text_rejects_injection_payloads(payload: str) -> None:
    with pytest.raises(ValidationError):
        DocumentBlock(block_id="blk-unsafe", kind="text", text=payload)


def test_unsafe_content_code_surfaces_on_direct_calls() -> None:
    template = _published_template()
    with pytest.raises(DocumentStudioError) as blocked:
        _instantiate(
            template,
            content={
                "blk-summary": "<script>boom</script>",
                "blk-findings": "<script>boom</script>",
                "blk-note": "Reviewed by operations",
            },
        )
    assert blocked.value.code == DocumentStudioError.UNSAFE_CONTENT


def test_media_alt_and_table_cells_are_guarded() -> None:
    with pytest.raises(ValidationError):
        DocumentBlock(
            block_id="blk-photo",
            kind="media",
            media_ref="media/x.jpg",
            alt_text="<img src=x onerror=alert(1)>",
        )
    with pytest.raises(ValidationError):
        DocumentBlock(
            block_id="blk-table",
            kind="table",
            table_columns=1,
            table_rows=(("clean",), ("<script>bad</script>",)),
        )


def test_media_reference_rejects_traversal() -> None:
    with pytest.raises(ValidationError):
        DocumentBlock(
            block_id="blk-photo", kind="media", media_ref="../secrets/x.jpg", alt_text="alt"
        )


def test_theme_tokens_bounded_values_only() -> None:
    with pytest.raises(ValidationError):
        ThemeTokens(accent="blue; background:url(javascript:x)")


# --- accessibility outline ----------------------------------------------------


def test_accessibility_outline_preserves_reading_order_and_metadata() -> None:
    document = _instantiate(_published_template())
    outline = document_accessibility_outline(document)
    ids = [entry["block_id"] for entry in outline]
    assert ids == [
        "blk-title", "blk-summary", "blk-chart", "blk-photo", "blk-divider",
        "blk-findings", "blk-metrics", "blk-break", "blk-note",
    ]
    heading = next(entry for entry in outline if entry["block_id"] == "blk-title")
    assert heading["heading_level"] == 1
    photo = next(entry for entry in outline if entry["block_id"] == "blk-photo")
    assert photo["alt_text"] == "Plant floor"
    table = next(entry for entry in outline if entry["block_id"] == "blk-metrics")
    assert table["table_shape"] == (2, 2)
    embed = next(entry for entry in outline if entry["block_id"] == "blk-chart")
    assert embed["embed_kind"] == "line-chart"


# --- round-trip, digests and untrusted parsing --------------------------------


def test_document_round_trip_is_byte_stable_and_deterministic() -> None:
    document = publish_document(_instantiate(_published_template()), now="2026-09-13T08:00:00Z")
    raw = json.loads(document.model_dump_json())
    parsed = parse_document_contract(raw)
    assert parsed == document
    assert parsed.digest() == document.digest()


def test_digest_is_order_insensitive_and_tamper_evident() -> None:
    document = _instantiate(_published_template())
    raw = json.loads(document.model_dump_json())
    reordered = dict(reversed(list(raw.items())))
    assert canonical_document_digest(raw) == canonical_document_digest(reordered)
    assert canonical_document_digest(raw) == document.digest()
    tampered = dict(raw)
    tampered["title"] = "Tampered"
    assert canonical_document_digest(tampered) != document.digest()


def test_parse_rejects_future_major_with_dedicated_code() -> None:
    raw = json.loads(_instantiate(_published_template()).model_dump_json())
    raw["schema_version"] = {"major": 2, "minor": 0}
    with pytest.raises(DocumentStudioError) as document_error:
        parse_document_contract(raw)
    assert document_error.value.code == DocumentStudioError.INCOMPATIBLE_VERSION
    template_raw = json.loads(_published_template().model_dump_json())
    template_raw["schema_version"] = {"major": 2, "minor": 0}
    with pytest.raises(DocumentStudioError) as template_error:
        parse_template_contract(template_raw)
    assert template_error.value.code == DocumentStudioError.INCOMPATIBLE_VERSION


def test_parse_reports_malformed_payload_with_safe_code() -> None:
    with pytest.raises(DocumentStudioError) as document_error:
        parse_document_contract("not-a-document")
    assert document_error.value.code == DocumentStudioError.INVALID_DOCUMENT
    with pytest.raises(DocumentStudioError) as template_error:
        parse_template_contract({"format": "axis.document-studio.template"})
    assert template_error.value.code == DocumentStudioError.INVALID_TEMPLATE


def test_provenance_digest_is_tamper_evident() -> None:
    template = _published_template()
    document = _instantiate(template)
    raw = json.loads(document.model_dump_json())
    raw["template_provenance"]["template_digest"] = "0" * 64
    forged = DocumentRevision.model_validate(raw)
    assert not verify_template_lineage(forged, template)
    assert isinstance(forged.template_provenance, TemplateProvenance)
