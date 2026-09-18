"""Assurance pack assembly: deterministic package from a frozen #883 manifest.

Slice of [#884](https://github.com/Limes-Labs/limes-axis/issues/884) (parent
#733, depends on #883). One domain service: it assembles the bounded,
human-readable package for an approved `PackManifest` — a canonical JSON
manifest, a sanitized local Markdown index, and permitted bounded
attachments. It owns no registry and performs no I/O of its own:

* **Release authorization is resolved first.** Every included artifact is
  read only through the caller-supplied `ArtifactSource`, which applies the
  current release authorization, outbound disclosure policy and object
  storage itself. A revoked audience permission, changed artifact revision
  or unavailable evidence aborts generation with a fixed code — a
  privileged cached package is never reused. #729 stays the evidence
  owner; freshness preflight stays with the #883 helpers.
* **Reference-only citations stay byte-free.** A ``reference_only`` entry
  is emitted as a bounded metadata citation — never as a copy of
  restricted bytes, a URL or a bearer link. The scope wording for #871/#879
  citations is the contract's own (`reference_scope_note`).
* **The package is deterministic and bounded.** Fixed member order, fixed
  timestamps, pinned archive metadata; entry count, attachment bytes and
  total package size are capped. Any breach aborts the build — no partial
  or issued artifact exists on failure.
* **The final output is scanned before release.** The manifest JSON, index
  text, member filenames and each packaged attachment's bytes go through
  the caller-supplied `PackScanner`; a planted secret blocks the package.
  A scanner that cannot judge a format must abort the build — silently
  passing unsupported formats is a policy failure, not a success.
* **Claims are preserved verbatim.** Support states, responsibilities,
  limitations and certificate scope ship exactly as approved; the builder
  never upgrades them into compliant/certified wording and adds no remote
  fonts, images or scripts (the index is local Markdown, no URLs).

The returned `AssembledPack` carries package bytes plus safe digests,
counts and reason codes only — ordinary audit emission stays with the
caller and must never include secret or evidence content. Signing,
issuance and download delivery stay with #885; PDF/DOCX rendering with
#834.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import zipfile
from dataclasses import dataclass
from typing import Protocol

from axis_api.assurance_pack_contracts import (
    AnswerSelection,
    PackManifest,
    reference_scope_note,
)

PACK_PACKAGE_FORMAT = "axis.assurance-pack.package"
PACKAGE_FORMAT_MAJOR = 1
PACKAGE_FORMAT_MINOR = 0

#: Deterministic packaging timestamp (DOS epoch); no wall clock enters the
#: archive, so identical inputs produce identical bytes and digests.
_PACKAGE_DATE_TIME = (1980, 1, 1, 0, 0, 0)

# Hard caps (issue AC: bounded size, entry count, processing inputs).
MAX_ATTACHMENTS = 32
MAX_ATTACHMENT_BYTES = 2 * 1024 * 1024
MAX_PACKAGE_BYTES = 16 * 1024 * 1024
MAX_MEMBERS = 128

#: Formats the builder requests from the scanner; anything else is an
#: explicit abort (`UNSUPPORTED_SCAN_FORMAT`), never a silent pass.
SCAN_FORMATS = ("json", "text", "filename")

# Defense in depth for rendered text; #883 already construction-refuses
# these in manifest free text, and the builder re-checks what it renders.
_UNSAFE = re.compile(r"(?i)(<\s*script|javascript:|\{\{|\}\}|\$\{|__proto__)")


class PackagingError(ValueError):
    """Fixed safe codes; details never include secret or evidence content."""

    INVALID_MANIFEST = "invalid_assurance_pack_manifest"
    RELEASE_NOT_CURRENT = "pack_release_not_current"
    ARTIFACT_UNAVAILABLE = "pack_artifact_unavailable"
    REVISION_MISMATCH = "pack_artifact_revision_mismatch"
    DIGEST_MISMATCH = "pack_artifact_digest_mismatch"
    UNSUPPORTED_SCAN_FORMAT = "pack_scan_format_unsupported"
    SECRET_DETECTED = "pack_secret_detected"
    BOUNDS_EXCEEDED = "pack_bounds_exceeded"
    UNSAFE_TEXT = "unsafe_pack_text"

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class ArtifactSource(Protocol):
    """Caller-owned release authorization and object reads (outbound policy)."""

    def resolve(self, entry: AnswerSelection, manifest: PackManifest) -> bytes:
        """Return the released artifact bytes for one included-artifact entry.

        Implementations apply the current release authorization (revoked
        audience -> :class:`PackagingError` ``RELEASE_NOT_CURRENT``), the
        outbound disclosure boundary, and the object-store read itself
        (unavailable evidence -> ``ARTIFACT_UNAVAILABLE``). A released
        artifact that no longer matches the approved revision fails with
        ``REVISION_MISMATCH``. The builder re-verifies the approved digest
        over the returned bytes; support-state freshness stays with the
        #883 preflight helpers.
        """


class PackScanner(Protocol):
    """Caller-owned final-output sensitive-data inspection."""

    def scan(self, data: bytes, fmt: str) -> bool:
        """Return True when ``data`` passes the scan for format ``fmt``.

        Formats are the entries of `SCAN_FORMATS`. Raise
        :class:`PackagingError` ``UNSUPPORTED_SCAN_FORMAT`` when the format
        cannot be judged — the builder propagates the abort instead of
        releasing an unscanned package.
        """


@dataclass(frozen=True)
class ReferenceOnlyCitation:
    """Bounded metadata-only citation for a reference-only entry."""

    entry_id: str
    title: str
    evidence_refs: tuple[str, ...]
    scope_note: str


@dataclass(frozen=True)
class AssembledPack:
    """The assembled package plus its safe verification evidence."""

    package_format: str
    format_version: dict[str, int]
    manifest: PackManifest
    manifest_digest: str
    package_sha256: str
    package_bytes: bytes
    members: tuple[str, ...]
    included_attachments: tuple[str, ...]
    reference_only_citations: tuple[ReferenceOnlyCitation, ...]


def _ensure_safe(text: str) -> None:
    if _UNSAFE.search(text):
        raise PackagingError(PackagingError.UNSAFE_TEXT)


def _attachment_name(entry_id: str) -> str:
    return f"attachments/{entry_id}.bin"


def _entry_block(entry: AnswerSelection) -> list[str]:
    lines = [
        f"## {entry.entry_id}",
        "",
        f"support: {entry.support}",
        f"responsibility: {entry.responsibility}",
        f"disclosure: {entry.disclosure}",
    ]
    if entry.limitation is not None:
        lines.append(f"limitation: {entry.limitation}")
    if entry.mode == "reference_only":
        lines.append("availability: reference only — cited, not included")
    return lines


def build_index_text(manifest: PackManifest) -> str:
    """Sanitized local Markdown index; no markup beyond headings/lists."""

    _ensure_safe(manifest.title)
    lines = [
        f"# {manifest.title}",
        "",
        f"pack: {manifest.pack_id}",
        (
            f"release: {manifest.release_snapshot.release} "
            f"profile: {manifest.release_snapshot.profile}"
        ),
        "",
        "## Entries",
        "",
    ]
    for entry in manifest.entries:
        lines.extend(_entry_block(entry))
        lines.append("")
    lines.append("## Included attachments")
    lines.append("")
    for entry in manifest.entries:
        if entry.mode == "included_artifact":
            lines.append(f"- {_attachment_name(entry.entry_id)}")
    lines.append("")
    lines.append(reference_scope_note())
    return "\n".join(lines)


def _manifest_json(manifest: PackManifest) -> bytes:
    return json.dumps(
        manifest.model_dump(mode="json"),
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _build_zip(members: list[tuple[str, bytes]]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name, content in members:
            info = zipfile.ZipInfo(name)
            info.date_time = _PACKAGE_DATE_TIME
            info.compress_type = zipfile.ZIP_DEFLATED
            info.create_system = 3  # pinned; otherwise platform-dependent
            info.external_attr = 0o600 << 16
            archive.writestr(info, content)
    return buffer.getvalue()


def build_assurance_pack(
    manifest: PackManifest,
    artifacts: ArtifactSource,
    scanner: PackScanner,
) -> AssembledPack:
    """Assemble the bounded package for one approved manifest.

    Deterministic given the same manifest, artifact bytes and scan policy.
    Raises fixed-code :class:`PackagingError` on any authorization,
    integrity, scan or bound failure; the caller is left with no package
    to release. Run the #883 freshness preflight (`check_support_freshness`)
    before calling — this builder verifies revision/digest integrity but
    re-derives no support states.
    """

    if not isinstance(manifest, PackManifest) or not manifest.entries:
        raise PackagingError(PackagingError.INVALID_MANIFEST)

    manifest_json = _manifest_json(manifest)
    index_text = build_index_text(manifest)

    members: list[tuple[str, bytes]] = [
        ("manifest.json", manifest_json),
        ("index.md", index_text.encode("utf-8")),
    ]
    attachments: list[str] = []
    citations: list[ReferenceOnlyCitation] = []
    included = [entry for entry in manifest.entries if entry.mode == "included_artifact"]
    if len(included) > MAX_ATTACHMENTS:
        raise PackagingError(PackagingError.BOUNDS_EXCEEDED)

    for entry in manifest.entries:
        if entry.mode == "reference_only":
            _ensure_safe(entry.question_ref)
            citations.append(
                ReferenceOnlyCitation(
                    entry_id=entry.entry_id,
                    title=entry.question_ref,
                    evidence_refs=entry.evidence_refs,
                    scope_note=reference_scope_note(),
                )
            )
            continue

        content = artifacts.resolve(entry, manifest)
        if len(content) > MAX_ATTACHMENT_BYTES:
            raise PackagingError(PackagingError.BOUNDS_EXCEEDED)
        # The approved digest is over the raw artifact bytes; a producer
        # cannot ship content that differs from the approved revision.
        if hashlib.sha256(content).hexdigest() != entry.artifact_digest:
            raise PackagingError(PackagingError.DIGEST_MISMATCH)
        name = _attachment_name(entry.entry_id)
        _ensure_safe(name)
        members.append((name, content))
        attachments.append(name)

    # Final-output scan: manifest, index, every filename, every attachment.
    if not scanner.scan(manifest_json, "json"):
        raise PackagingError(PackagingError.SECRET_DETECTED)
    if not scanner.scan(index_text.encode("utf-8"), "text"):
        raise PackagingError(PackagingError.SECRET_DETECTED)
    for name, content in members[2:]:
        if not scanner.scan(name.encode("utf-8"), "filename"):
            raise PackagingError(PackagingError.SECRET_DETECTED)
        if not scanner.scan(content, "text"):
            raise PackagingError(PackagingError.SECRET_DETECTED)

    if len(members) > MAX_MEMBERS:
        raise PackagingError(PackagingError.BOUNDS_EXCEEDED)
    package_bytes = _build_zip(members)
    if len(package_bytes) > MAX_PACKAGE_BYTES:
        raise PackagingError(PackagingError.BOUNDS_EXCEEDED)

    return AssembledPack(
        package_format=PACK_PACKAGE_FORMAT,
        format_version={"major": PACKAGE_FORMAT_MAJOR, "minor": PACKAGE_FORMAT_MINOR},
        manifest=manifest,
        manifest_digest=manifest.digest(),
        package_sha256=hashlib.sha256(package_bytes).hexdigest(),
        package_bytes=package_bytes,
        members=tuple(name for name, _ in members),
        included_attachments=tuple(attachments),
        reference_only_citations=tuple(citations),
    )
