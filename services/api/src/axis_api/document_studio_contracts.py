"""Document Studio contract: versioned documents, sections, blocks, templates.

Contract slice of [#829](https://github.com/Limes-Labs/limes-axis/issues/829)
(parent #828). This module is pure vocabulary: no storage, no editor runtime,
no rendering, no governed embed resolution (owned by #830). It defines the
durable shape of documents and reusable templates plus the rules producers
must satisfy:

* Versioned envelopes (``axis.document-studio.document`` /
  ``axis.document-studio.template``) with strict round-trips. Unknown fields
  and incompatible major versions are rejected; there is no fallback.
* Published document/template revisions are immutable: editing a published
  artifact is a refused operation; it produces a draft or a new revision.
* Template provenance carries the exact template revision digest, so
  instantiated documents stay verifiable even after the template is deleted
  or revised; deleting a template never invalidates existing documents.
* Template parameters are typed and bounded; string-ish values cannot express
  URLs, raw queries, script/style payloads or template delimiters.
* Template regions reference real block IDs (construction-time integrity);
  instantiation cannot override ``fixed`` region content.
* Accessibility semantics (heading levels, reading order, alt text, table
  structure) are first-class contract data preserved by serialization.

The digest helper is shared so producers cannot sign non-canonical bytes.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping
from typing import Literal

from axis_sdk.connector_authoring.contracts import ContractModel, Digest
from pydantic import Field, ValidationError, model_validator

DOCUMENT_FORMAT = "axis.document-studio.document"
TEMPLATE_FORMAT = "axis.document-studio.template"
CONTRACT_MAJOR = 1
CONTRACT_MINOR = 0

#: Supported schema versions for reading; major bumps change semantics.
SUPPORTED_MAJOR_VERSIONS = (CONTRACT_MAJOR,)

_MAX_SECTIONS = 64
_MAX_BLOCKS_PER_SECTION = 256
_MAX_TEXT = 20_000
_MAX_ALT = 600
_MAX_TITLE = 200
_MAX_TABLE_ROWS = 1_000
_MAX_TABLE_COLUMNS = 16
_MAX_TABLE_CELL = 500
_MAX_PARAMETERS = 32
_MAX_METADATA_ENTRIES = 16

_IDENTIFIER = r"^[a-z][a-z0-9-]{2,47}$"
_RESOURCE_ID = r"^[a-z][a-z0-9._/-]{2,199}$"
_VERSION_REVISION = r"^\d+$"
_TIMESTAMP = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$"
_DATE = r"^\d{4}-\d{2}-\d{2}$"
_TOKEN = r"^[a-z0-9][a-z0-9-]{0,31}$"
_PARAMETER_NAME = r"^[a-z][a-z0-9_]{0,31}$"

BlockKind = Literal[
    "heading", "text", "media", "divider", "callout", "metadata", "table",
    "toc", "page_break", "embed_placeholder",
]
ParameterKind = Literal["string", "number", "boolean", "date", "governed_ref"]
RegionKind = Literal["fixed", "editable", "required"]
DocumentState = Literal["draft", "published"]
TemplateState = Literal["draft", "published", "deleted"]

# Authored contract text is structured plain text, never markup: reject
# script/iframe payloads, script URLs, template delimiters and prototype
# pollution shapes wherever prose or values enter the contract.
_UNSAFE = re.compile(
    r"(?is)(<\s*script|<\s*iframe|javascript:|data:text/html|onerror\s*=|"
    r"onload\s*=|\{\{|\}\}|\$\{|__proto__)"
)

_NUMBER = re.compile(r"^-?\d+(\.\d+)?$")
_BOOLEAN = re.compile(r"^(true|false)$")


class DocumentStudioError(ValueError):
    """Fixed contract codes; raw validation details are never rendered."""

    INCOMPATIBLE_VERSION = "incompatible_document_contract_version"
    INVALID_DOCUMENT = "invalid_document_contract"
    INVALID_TEMPLATE = "invalid_template_contract"
    INVALID_PARAMETER = "invalid_template_parameter"
    UNSAFE_CONTENT = "unsafe_document_content"
    MISSING_PROVENANCE = "missing_template_provenance"
    INCOMPATIBLE_INSTANTIATION = "incompatible_template_instantiation"
    IMMUTABLE_REVISION = "published_revision_is_immutable"
    NOT_PUBLISHED = "template_not_published"
    DELETED_TEMPLATE = "template_deleted"
    TEMPLATE_DIGEST_MISMATCH = "template_digest_mismatch"

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def canonical_document_digest(value: object) -> Digest:
    """Deterministic digest over canonical JSON; producers must reuse this."""

    data = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _parse_major(value: object, invalid_code: str) -> int:
    if not isinstance(value, dict):
        raise DocumentStudioError(invalid_code)
    major = value.get("schema_version", {}).get("major") if isinstance(
        value.get("schema_version"), dict
    ) else None
    if not isinstance(major, int) or isinstance(major, bool):
        raise DocumentStudioError(invalid_code)
    return major


def _ensure_safe(text: str, code: str) -> str:
    if _UNSAFE.search(text):
        raise DocumentStudioError(code)
    return text


class ManifestVersion(ContractModel):
    major: int = Field(ge=1, strict=True)
    minor: int = Field(ge=0, strict=True)

    @model_validator(mode="after")
    def bounded_version(self) -> ManifestVersion:
        if self.major != CONTRACT_MAJOR or self.minor != CONTRACT_MINOR:
            raise ValueError(f"Unsupported document contract version {self.major}.{self.minor}")
        return self


class ThemeTokens(ContractModel):
    """Bounded design-token reference; arbitrary CSS/JS is unrepresentable."""

    accent: str | None = Field(default=None, pattern=_TOKEN)
    surface: str | None = Field(default=None, pattern=_TOKEN)
    ink: str | None = Field(default=None, pattern=_TOKEN)
    font_scale: float | None = Field(default=None, gt=0, le=2)


class PageLayout(ContractModel):
    orientation: Literal["portrait", "landscape"] = "portrait"
    page_size: Literal["a4", "letter"] = "a4"
    margin_mm: int = Field(default=20, ge=0, le=50, strict=True)
    columns: int = Field(default=1, ge=1, le=4, strict=True)
    header: str | None = Field(default=None, min_length=1, max_length=_MAX_ALT)
    footer: str | None = Field(default=None, min_length=1, max_length=_MAX_ALT)

    @model_validator(mode="after")
    def safe_repeats(self) -> PageLayout:
        if self.header is not None:
            _ensure_safe(self.header, DocumentStudioError.UNSAFE_CONTENT)
        if self.footer is not None:
            _ensure_safe(self.footer, DocumentStudioError.UNSAFE_CONTENT)
        return self


class EmbedSlot(ContractModel):
    """Typed governed embed placeholder; resolution is owned by #830."""

    slot_id: str = Field(pattern=_IDENTIFIER)
    embed_kind: str = Field(pattern=_TOKEN)
    binding_ref: str | None = Field(default=None, pattern=_RESOURCE_ID)
    caption: str | None = Field(default=None, min_length=1, max_length=_MAX_ALT)

    @model_validator(mode="after")
    def safe_caption(self) -> EmbedSlot:
        if self.caption is not None:
            _ensure_safe(self.caption, DocumentStudioError.UNSAFE_CONTENT)
        if self.binding_ref is not None and ".." in self.binding_ref:
            raise DocumentStudioError(DocumentStudioError.INVALID_DOCUMENT)
        return self


class DocumentBlock(ContractModel):
    """One content block with a stable ID and typed, bounded payload."""

    block_id: str = Field(pattern=_IDENTIFIER)
    kind: BlockKind
    text: str | None = Field(default=None, min_length=1, max_length=_MAX_TEXT)
    heading_level: int | None = Field(default=None, ge=1, le=6, strict=True)
    alt_text: str | None = Field(default=None, min_length=1, max_length=_MAX_ALT)
    media_ref: str | None = Field(default=None, pattern=_RESOURCE_ID)
    table_columns: int | None = Field(default=None, ge=1, le=_MAX_TABLE_COLUMNS, strict=True)
    table_rows: tuple[tuple[str, ...], ...] = Field(default=(), max_length=_MAX_TABLE_ROWS)
    embed: EmbedSlot | None = None
    metadata: dict[str, str] = Field(default_factory=dict)

    @model_validator(mode="after")
    def coherent_block(self) -> DocumentBlock:
        if self.text is not None:
            _ensure_safe(self.text, DocumentStudioError.UNSAFE_CONTENT)
        if self.alt_text is not None:
            _ensure_safe(self.alt_text, DocumentStudioError.UNSAFE_CONTENT)
        if self.media_ref is not None and ".." in self.media_ref:
            raise DocumentStudioError(DocumentStudioError.INVALID_DOCUMENT)
        for key, value in self.metadata.items():
            if not re.match(_TOKEN, key) or len(value) > _MAX_ALT:
                raise DocumentStudioError(DocumentStudioError.INVALID_DOCUMENT)
            _ensure_safe(value, DocumentStudioError.UNSAFE_CONTENT)
        if self.kind == "heading":
            if self.heading_level is None or self.text is None:
                raise ValueError("Heading blocks require a level and text")
        elif self.kind in {"text", "callout", "metadata"}:
            if self.text is None:
                raise ValueError(f"{self.kind} blocks require text")
        elif self.kind == "media":
            if self.media_ref is None or self.alt_text is None:
                raise ValueError("Media blocks require a bounded reference and alt text")
        elif self.kind == "table":
            if self.table_columns is None or not self.table_rows:
                raise ValueError("Table blocks require columns and at least one row")
            if any(len(row) != self.table_columns for row in self.table_rows):
                raise ValueError("Every table row must match the declared column count")
            if any(len(cell) > _MAX_TABLE_CELL for row in self.table_rows for cell in row):
                raise DocumentStudioError(DocumentStudioError.INVALID_DOCUMENT)
            for row in self.table_rows:
                for cell in row:
                    _ensure_safe(cell, DocumentStudioError.UNSAFE_CONTENT)
        elif self.kind == "embed_placeholder":
            if self.embed is None:
                raise ValueError("Embed placeholder blocks require a typed slot")
        else:
            if any(
                value is not None
                for value in (
                    self.text, self.heading_level, self.alt_text, self.media_ref, self.embed
                )
            ) or self.table_rows:
                raise ValueError(f"{self.kind} blocks carry no payload")
        return self


class DocumentSection(ContractModel):
    section_id: str = Field(pattern=_IDENTIFIER)
    title: str = Field(min_length=1, max_length=_MAX_TITLE)
    blocks: tuple[DocumentBlock, ...] = Field(min_length=1, max_length=_MAX_BLOCKS_PER_SECTION)

    @model_validator(mode="after")
    def safe_title(self) -> DocumentSection:
        _ensure_safe(self.title, DocumentStudioError.UNSAFE_CONTENT)
        return self


class TemplateProvenance(ContractModel):
    """Exact template revision a document was instantiated from."""

    template_id: str = Field(pattern=_IDENTIFIER)
    template_revision: str = Field(pattern=_VERSION_REVISION)
    template_digest: Digest = Field(repr=False)


class DocumentRevision(ContractModel):
    """One document at one revision; published revisions are immutable."""

    format: Literal["axis.document-studio.document"] = DOCUMENT_FORMAT
    schema_version: ManifestVersion
    document_id: str = Field(pattern=_IDENTIFIER)
    revision: str = Field(pattern=_VERSION_REVISION)
    title: str = Field(min_length=1, max_length=_MAX_TITLE)
    description: str | None = Field(default=None, max_length=_MAX_TITLE)
    locale: str = Field(pattern=r"^[a-z]{2}(-[A-Z]{2})?$")
    state: DocumentState
    page: PageLayout
    theme: ThemeTokens
    sections: tuple[DocumentSection, ...] = Field(min_length=1, max_length=_MAX_SECTIONS)
    template_provenance: TemplateProvenance | None = None
    parameter_values: dict[str, str] = Field(default_factory=dict)
    issued_at: str | None = Field(default=None, pattern=_TIMESTAMP, min_length=20, max_length=40)

    @model_validator(mode="after")
    def coherent_document(self) -> DocumentRevision:
        _ensure_safe(self.title, DocumentStudioError.UNSAFE_CONTENT)
        if self.description is not None:
            _ensure_safe(self.description, DocumentStudioError.UNSAFE_CONTENT)
        section_ids = [section.section_id for section in self.sections]
        if len(set(section_ids)) != len(section_ids):
            raise ValueError("Section IDs must be unique within a document")
        block_ids = [
            block.block_id for section in self.sections for block in section.blocks
        ]
        if len(set(block_ids)) != len(block_ids):
            raise ValueError("Block IDs must be unique across the whole document")
        if self.state == "published":
            if self.issued_at is None:
                raise ValueError("A published revision must carry its issuance timestamp")
        else:
            if self.issued_at is not None:
                raise ValueError("Only published revisions carry an issuance timestamp")
            if self.template_provenance is None and self.parameter_values:
                raise ValueError("Standalone documents have no template parameters")
        return self

    def digest(self) -> Digest:
        return canonical_document_digest(self.model_dump(mode="json"))


class TemplateParameter(ContractModel):
    """A typed template input; values cannot smuggle queries or scripts."""

    name: str = Field(pattern=_PARAMETER_NAME)
    kind: ParameterKind
    required: bool
    description: str = Field(min_length=1, max_length=_MAX_ALT)
    default: str | None = Field(default=None, max_length=_MAX_ALT)

    @model_validator(mode="after")
    def typed_default(self) -> TemplateParameter:
        _ensure_safe(self.description, DocumentStudioError.UNSAFE_CONTENT)
        if self.default is None:
            return self
        _ensure_safe(self.default, DocumentStudioError.UNSAFE_CONTENT)
        if self.kind == "number" and not _NUMBER.match(self.default):
            raise DocumentStudioError(DocumentStudioError.INVALID_PARAMETER)
        if self.kind == "boolean" and not _BOOLEAN.match(self.default):
            raise DocumentStudioError(DocumentStudioError.INVALID_PARAMETER)
        if self.kind == "date" and not re.match(_DATE, self.default):
            raise DocumentStudioError(DocumentStudioError.INVALID_PARAMETER)
        if self.kind == "governed_ref" and not re.match(_RESOURCE_ID, self.default):
            raise DocumentStudioError(DocumentStudioError.INVALID_PARAMETER)
        if self.kind == "string" and not self.default:
            raise DocumentStudioError(DocumentStudioError.INVALID_PARAMETER)
        return self


class TemplateRegion(ContractModel):
    """Named block group with an instantiation policy."""

    region_id: str = Field(pattern=_IDENTIFIER)
    kind: RegionKind
    block_ids: tuple[str, ...] = Field(min_length=1, max_length=_MAX_BLOCKS_PER_SECTION)


_TEMPLATE_LIFECYCLE_FIELDS = frozenset({"state", "issued_at", "deleted_at"})


class DocumentTemplate(ContractModel):
    """One reusable template at one revision; published revisions are immutable."""

    format: Literal["axis.document-studio.template"] = TEMPLATE_FORMAT
    schema_version: ManifestVersion
    template_id: str = Field(pattern=_IDENTIFIER)
    revision: str = Field(pattern=_VERSION_REVISION)
    title: str = Field(min_length=1, max_length=_MAX_TITLE)
    description: str | None = Field(default=None, max_length=_MAX_TITLE)
    parameters: tuple[TemplateParameter, ...] = Field(max_length=_MAX_PARAMETERS)
    regions: tuple[TemplateRegion, ...] = Field(max_length=_MAX_BLOCKS_PER_SECTION)
    page: PageLayout
    theme: ThemeTokens
    sections: tuple[DocumentSection, ...] = Field(min_length=1, max_length=_MAX_SECTIONS)
    state: TemplateState
    issued_at: str | None = Field(default=None, pattern=_TIMESTAMP, min_length=20, max_length=40)
    deleted_at: str | None = Field(default=None, pattern=_TIMESTAMP, min_length=20, max_length=40)

    @model_validator(mode="after")
    def coherent_template(self) -> DocumentTemplate:
        _ensure_safe(self.title, DocumentStudioError.UNSAFE_CONTENT)
        if self.description is not None:
            _ensure_safe(self.description, DocumentStudioError.UNSAFE_CONTENT)
        block_ids = {
            block.block_id for section in self.sections for block in section.blocks
        }
        for region in self.regions:
            if not set(region.block_ids) <= block_ids:
                raise ValueError("Template regions must reference existing block IDs")
        region_ids = [region.region_id for region in self.regions]
        if len(set(region_ids)) != len(region_ids):
            raise ValueError("Region IDs must be unique within a template")
        parameter_names = [parameter.name for parameter in self.parameters]
        if len(set(parameter_names)) != len(parameter_names):
            raise ValueError("Parameter names must be unique within a template")
        if self.state == "published":
            if self.issued_at is None or self.deleted_at is not None:
                raise ValueError("A published template carries only its issuance timestamp")
        elif self.state == "deleted":
            if self.issued_at is None or self.deleted_at is None:
                raise ValueError("A deleted template keeps its publish and deletion timestamps")
        elif self.issued_at is not None or self.deleted_at is not None:
            raise ValueError("Draft templates carry no lifecycle timestamps")
        return self

    def digest(self) -> Digest:
        return canonical_document_digest(self.model_dump(mode="json"))

    def content_digest(self) -> Digest:
        """Digest of revision content without lifecycle fields.

        Publication and deletion only change lifecycle fields, so lineage
        recorded against this digest survives both — deleting a template
        never invalidates documents instantiated from the revision.
        """

        payload = {
            key: value
            for key, value in self.model_dump(mode="json").items()
            if key not in _TEMPLATE_LIFECYCLE_FIELDS
        }
        return canonical_document_digest(payload)


def _validated_parameter(
    parameter: TemplateParameter, value: str
) -> str:
    _ensure_safe(value, DocumentStudioError.INVALID_PARAMETER)
    if parameter.kind == "number" and not _NUMBER.match(value):
        raise DocumentStudioError(DocumentStudioError.INVALID_PARAMETER)
    if parameter.kind == "boolean" and not _BOOLEAN.match(value):
        raise DocumentStudioError(DocumentStudioError.INVALID_PARAMETER)
    if parameter.kind == "date" and not re.match(_DATE, value):
        raise DocumentStudioError(DocumentStudioError.INVALID_PARAMETER)
    if parameter.kind == "governed_ref" and (
        not re.match(_RESOURCE_ID, value) or ".." in value
    ):
        raise DocumentStudioError(DocumentStudioError.INVALID_PARAMETER)
    if parameter.kind == "string" and not value:
        raise DocumentStudioError(DocumentStudioError.INVALID_PARAMETER)
    return value


def _instantiate_sections(
    template: DocumentTemplate,
    content: Mapping[str, str],
) -> tuple[DocumentSection, ...]:
    payload = [section.model_dump(mode="json") for section in template.sections]
    for section in payload:
        for block in section["blocks"]:
            replacement = content.get(block["block_id"])
            if replacement is not None:
                _ensure_safe(replacement, DocumentStudioError.UNSAFE_CONTENT)
                if len(replacement) > _MAX_TEXT:
                    raise DocumentStudioError(DocumentStudioError.INVALID_DOCUMENT)
                block["text"] = replacement
    return tuple(DocumentSection.model_validate(section) for section in payload)


def instantiate_template(
    template: DocumentTemplate,
    *,
    document_id: str,
    title: str,
    locale: str,
    parameter_values: Mapping[str, str] | None = None,
    content: Mapping[str, str] | None = None,
) -> DocumentRevision:
    """Instantiate a published template into a fresh document draft."""

    if template.state == "deleted":
        raise DocumentStudioError(DocumentStudioError.DELETED_TEMPLATE)
    if template.state != "published":
        raise DocumentStudioError(DocumentStudioError.NOT_PUBLISHED)
    _ensure_safe(title, DocumentStudioError.UNSAFE_CONTENT)

    parameters = {parameter.name: parameter for parameter in template.parameters}
    values: dict[str, str] = {}
    for name, value in (parameter_values or {}).items():
        parameter = parameters.get(name)
        if parameter is None:
            raise DocumentStudioError(DocumentStudioError.INCOMPATIBLE_INSTANTIATION)
        values[name] = _validated_parameter(parameter, value)
    missing = [
        parameter.name
        for parameter in template.parameters
        if parameter.required and parameter.name not in values
    ]
    if missing:
        raise DocumentStudioError(DocumentStudioError.INCOMPATIBLE_INSTANTIATION)

    region_of_block: dict[str, TemplateRegion] = {}
    for region in template.regions:
        for block_id in region.block_ids:
            region_of_block[block_id] = region
    provided = dict(content or {})
    for block_id in provided:
        region = region_of_block.get(block_id)
        if region is None or region.kind == "fixed":
            raise DocumentStudioError(DocumentStudioError.INCOMPATIBLE_INSTANTIATION)
    for region in template.regions:
        if region.kind == "required" and not any(
            block_id in provided for block_id in region.block_ids
        ):
            raise DocumentStudioError(DocumentStudioError.INCOMPATIBLE_INSTANTIATION)

    return DocumentRevision(
        schema_version=ManifestVersion(major=CONTRACT_MAJOR, minor=CONTRACT_MINOR),
        document_id=document_id,
        revision="1",
        title=title,
        locale=locale,
        state="draft",
        page=template.page,
        theme=template.theme,
        sections=_instantiate_sections(template, provided),
        template_provenance=TemplateProvenance(
            template_id=template.template_id,
            template_revision=template.revision,
            template_digest=template.content_digest(),
        ),
        parameter_values=values,
    )


def publish_document(draft: DocumentRevision, *, now: str) -> DocumentRevision:
    """Publish a draft; template-derived drafts must carry provenance."""

    if draft.state != "draft":
        raise DocumentStudioError(DocumentStudioError.IMMUTABLE_REVISION)
    if draft.template_provenance is None and draft.parameter_values:
        raise DocumentStudioError(DocumentStudioError.MISSING_PROVENANCE)
    return DocumentRevision.model_validate(
        {**draft.model_dump(mode="json"), "state": "published", "issued_at": now}
    )


def revise_document(published: DocumentRevision) -> DocumentRevision:
    """Start a new draft revision from any revision; never rewrites bytes."""

    return DocumentRevision.model_validate(
        {
            **published.model_dump(mode="json"),
            "revision": str(int(published.revision) + 1),
            "state": "draft",
            "issued_at": None,
        }
    )


def revise_template(published: DocumentTemplate) -> DocumentTemplate:
    """Start a new template draft revision; issued documents stay bound to N."""

    return DocumentTemplate.model_validate(
        {
            **published.model_dump(mode="json"),
            "revision": str(int(published.revision) + 1),
            "state": "draft",
            "issued_at": None,
            "deleted_at": None,
        }
    )


_LIFECYCLE_FIELDS = frozenset({"state", "revision", "issued_at"})


def edit_document(draft: DocumentRevision, changes: Mapping[str, object]) -> DocumentRevision:
    """Apply validated edits to a draft; lifecycle fields go through publish."""

    if draft.state != "draft":
        raise DocumentStudioError(DocumentStudioError.IMMUTABLE_REVISION)
    if _LIFECYCLE_FIELDS.intersection(changes):
        raise DocumentStudioError(DocumentStudioError.IMMUTABLE_REVISION)
    payload = draft.model_dump(mode="json")
    payload.update(changes)
    return DocumentRevision.model_validate(payload)


def publish_template(template: DocumentTemplate, *, now: str) -> DocumentTemplate:
    """Publish a template draft; the revision digest freezes at this point."""

    if template.state != "draft":
        raise DocumentStudioError(DocumentStudioError.IMMUTABLE_REVISION)
    return DocumentTemplate.model_validate(
        {**template.model_dump(mode="json"), "state": "published", "issued_at": now}
    )


def delete_template(template: DocumentTemplate, *, now: str) -> DocumentTemplate:
    """Mark a published template deleted; historical documents keep lineage."""

    if template.state != "published":
        raise DocumentStudioError(DocumentStudioError.IMMUTABLE_REVISION)
    return DocumentTemplate.model_validate(
        {
            **template.model_dump(mode="json"),
            "state": "deleted",
            "deleted_at": now,
        }
    )


def verify_template_lineage(document: DocumentRevision, template: DocumentTemplate) -> bool:
    """True when the document was instantiated from exactly this revision.

    Works for deleted templates on purpose: deletion must never invalidate
    documents instantiated from the immutable revision.
    """

    provenance = document.template_provenance
    if provenance is None:
        return False
    return (
        provenance.template_id == template.template_id
        and provenance.template_revision == template.revision
        and provenance.template_digest == template.content_digest()
    )


def document_accessibility_outline(
    document: DocumentRevision,
) -> tuple[dict[str, object], ...]:
    """Ordered reading outline: headings, alt text and table shapes."""

    outline: list[dict[str, object]] = []
    for section in document.sections:
        for block in section.blocks:
            entry: dict[str, object] = {
                "section_id": section.section_id,
                "block_id": block.block_id,
                "kind": block.kind,
            }
            if block.heading_level is not None:
                entry["heading_level"] = block.heading_level
            if block.alt_text is not None:
                entry["alt_text"] = block.alt_text
            if block.kind == "table" and block.table_columns is not None:
                entry["table_shape"] = (len(block.table_rows), block.table_columns)
            if block.embed is not None:
                entry["embed_kind"] = block.embed.embed_kind
            outline.append(entry)
    return tuple(outline)


def parse_document_contract(value: object) -> DocumentRevision:
    """Parse an untrusted document payload with fixed safe error codes."""

    if isinstance(value, dict):
        major = _parse_major(value, DocumentStudioError.INVALID_DOCUMENT)
        if major not in SUPPORTED_MAJOR_VERSIONS:
            raise DocumentStudioError(DocumentStudioError.INCOMPATIBLE_VERSION)
    try:
        return DocumentRevision.model_validate(value)
    except ValidationError:
        raise DocumentStudioError(DocumentStudioError.INVALID_DOCUMENT) from None


def parse_template_contract(value: object) -> DocumentTemplate:
    """Parse an untrusted template payload with fixed safe error codes."""

    if isinstance(value, dict):
        major = _parse_major(value, DocumentStudioError.INVALID_TEMPLATE)
        if major not in SUPPORTED_MAJOR_VERSIONS:
            raise DocumentStudioError(DocumentStudioError.INCOMPATIBLE_VERSION)
    try:
        return DocumentTemplate.model_validate(value)
    except ValidationError:
        raise DocumentStudioError(DocumentStudioError.INVALID_TEMPLATE) from None
