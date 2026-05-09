"""Seed data for content-stack.

Two public entry points:

- ``seed_eeat_criteria(session, project_id)`` — populates the canonical
  80-item EEAT rubric for a *new* project. Idempotent on
  ``(project_id, code)``. T04, C01, R10 are seeded as ``tier='core'`` per
  D7; the repository layer (M1.B) refuses to deactivate or un-require
  these rows.

- ``seed_schema_emits_templates(session)`` — inserts global
  schema-emit *templates* (``article_id IS NULL``) the project bootstrap
  procedure (#1) clones into per-article rows. Idempotent on ``type``.

Plus the migration-only helper ``seed_schema_emits_templates_via_op``
which uses Alembic's ``op`` so the templates land at DB-init time.

The 80 EEAT rows describe one-line standards across the 8-dimension
rubric (C / O / R / E / Exp / Ept / A / T). The codes (C01..C10,
O01..O10, R01..R10, E01..E10, Exp01..Exp10, Ept01..Ept10, A01..A10,
T01..T10) are stable identifiers so future rubric renumbering doesn't
break references.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, Final

from alembic import op
from sqlalchemy import text
from sqlmodel import Session, select

from content_stack.db.models import EeatCategory, EeatCriterion, EeatTier, SchemaEmit

# Codes that must be seeded as `tier='core'` per D7 (PLAN.md L1605).
_CORE_VETO_CODES: Final[frozenset[str]] = frozenset({"T04", "C01", "R10"})


# ---------------------------------------------------------------------------
# 80-item EEAT rubric. Each tuple is (code, category, name, standard_text).
# `name` is the short label; `standard_text` is the paraphrased one-line
# rule the auditor checks against.
# ---------------------------------------------------------------------------


_EEAT_ITEMS: Final[tuple[tuple[str, EeatCategory, str, str], ...]] = (
    # C — Contextual Clarity
    ("C01", EeatCategory.C, "Intent Alignment", "Title promise matches what the body delivers."),
    (
        "C02",
        EeatCategory.C,
        "Direct Answer",
        "Core answer appears within the first 150 words.",
    ),
    (
        "C03",
        EeatCategory.C,
        "Query Coverage",
        "At least three query variants (synonyms, long-tail) are addressed.",
    ),
    (
        "C04",
        EeatCategory.C,
        "Definition First",
        "Key terms are defined the first time they appear.",
    ),
    (
        "C05",
        EeatCategory.C,
        "Topic Scope",
        "Article explicitly states what it covers and what it excludes.",
    ),
    (
        "C06",
        EeatCategory.C,
        "Audience Targeting",
        "Article identifies its intended reader explicitly.",
    ),
    (
        "C07",
        EeatCategory.C,
        "Semantic Coherence",
        "Paragraphs flow logically without unmotivated topic jumps.",
    ),
    (
        "C08",
        EeatCategory.C,
        "Use Case Mapping",
        "Decision framework distinguishes when to choose option A versus B.",
    ),
    (
        "C09",
        EeatCategory.C,
        "FAQ Coverage",
        "Structured FAQ section covers common follow-up questions.",
    ),
    (
        "C10",
        EeatCategory.C,
        "Semantic Closure",
        "Conclusion answers the opening question and points at next steps.",
    ),
    # O — Organization
    ("O01", EeatCategory.O, "Heading Hierarchy", "H1 → H2 → H3 nesting with no level skipping."),
    (
        "O02",
        EeatCategory.O,
        "Summary Box",
        "TL;DR or key-takeaways block is present near the top.",
    ),
    (
        "O03",
        EeatCategory.O,
        "Data Tables",
        "Comparisons and specifications are presented in tables, not prose.",
    ),
    (
        "O04",
        EeatCategory.O,
        "List Formatting",
        "Parallel items use bullet or numbered lists consistently.",
    ),
    (
        "O05",
        EeatCategory.O,
        "Schema Markup",
        "Appropriate JSON-LD (Article / FAQ / HowTo / etc.) is emitted.",
    ),
    (
        "O06",
        EeatCategory.O,
        "Section Chunking",
        "Each section covers one topic with paragraphs of 3-5 sentences.",
    ),
    (
        "O07",
        EeatCategory.O,
        "Visual Hierarchy",
        "Key concepts are bolded or otherwise visually highlighted.",
    ),
    (
        "O08",
        EeatCategory.O,
        "Anchor Navigation",
        "Table of contents with jump links is provided.",
    ),
    (
        "O09",
        EeatCategory.O,
        "Information Density",
        "No filler; consistent terminology used throughout.",
    ),
    (
        "O10",
        EeatCategory.O,
        "Multimedia Structure",
        "Images and videos carry information and have captions.",
    ),
    # R — Referenceability
    (
        "R01",
        EeatCategory.R,
        "Data Precision",
        "At least five precise numbers with units are included.",
    ),
    (
        "R02",
        EeatCategory.R,
        "Citation Density",
        "At least one external citation per 500 words of body copy.",
    ),
    (
        "R03",
        EeatCategory.R,
        "Source Hierarchy",
        "Primary sources are listed first; at least three Tier 1-2 sources cited.",
    ),
    (
        "R04",
        EeatCategory.R,
        "Evidence-Claim Mapping",
        "Every claim is followed immediately by supporting evidence.",
    ),
    (
        "R05",
        EeatCategory.R,
        "Methodology Transparency",
        "Sample size, steps, and criteria are documented.",
    ),
    (
        "R06",
        EeatCategory.R,
        "Timestamp & Versioning",
        "Last-updated date is within one year; version changes are noted.",
    ),
    (
        "R07",
        EeatCategory.R,
        "Entity Precision",
        "Full names are used for people, organisations, and products.",
    ),
    (
        "R08",
        EeatCategory.R,
        "Internal Link Graph",
        "Descriptive anchor texts form coherent topic clusters.",
    ),
    (
        "R09",
        EeatCategory.R,
        "HTML Semantics",
        "Article uses semantic tags (article, figure, time, cite).",
    ),
    (
        "R10",
        EeatCategory.R,
        "Content Consistency",
        "Data on the page is internally self-consistent and contains no broken links.",
    ),
    # E — Exclusivity
    (
        "E01",
        EeatCategory.E,
        "Original Data",
        "First-party surveys, experiments, or statistics are presented.",
    ),
    (
        "E02",
        EeatCategory.E,
        "Novel Framework",
        "A named, citable framework or model is introduced.",
    ),
    (
        "E03",
        EeatCategory.E,
        "Primary Research",
        "Original experiments or surveys are documented with process.",
    ),
    (
        "E04",
        EeatCategory.E,
        "Contrarian View",
        "Article challenges consensus with explicit evidence.",
    ),
    (
        "E05",
        EeatCategory.E,
        "Proprietary Visuals",
        "At least two original infographics, charts, or diagrams are included.",
    ),
    (
        "E06",
        EeatCategory.E,
        "Gap Filling",
        "Article covers questions competing pages do not address.",
    ),
    (
        "E07",
        EeatCategory.E,
        "Practical Tools",
        "Downloadable templates, checklists, or calculators are offered.",
    ),
    (
        "E08",
        EeatCategory.E,
        "Depth Advantage",
        "Article goes deeper than competing content on the same topic.",
    ),
    (
        "E09",
        EeatCategory.E,
        "Synthesis Value",
        "Article combines knowledge from multiple domains into new insight.",
    ),
    (
        "E10",
        EeatCategory.E,
        "Forward Insights",
        "Data-backed predictions or trend analysis is included.",
    ),
    # Exp — Experience
    (
        "Exp01",
        EeatCategory.EXP,
        "First-Person Narrative",
        "Body uses first-person testing or observation language.",
    ),
    (
        "Exp02",
        EeatCategory.EXP,
        "Sensory Details",
        "At least ten sensory or observational descriptors are present.",
    ),
    (
        "Exp03",
        EeatCategory.EXP,
        "Process Documentation",
        "Step-by-step process with a timeline is documented.",
    ),
    (
        "Exp04",
        EeatCategory.EXP,
        "Tangible Proof",
        "At least two original photos or screenshots with timestamps are shown.",
    ),
    (
        "Exp05",
        EeatCategory.EXP,
        "Usage Duration",
        "Article states how long the author has used the subject.",
    ),
    (
        "Exp06",
        EeatCategory.EXP,
        "Problems Encountered",
        "At least two real problems plus their solutions are shared.",
    ),
    (
        "Exp07",
        EeatCategory.EXP,
        "Before/After Comparison",
        "Article shows measurable change, improvement, or difference.",
    ),
    (
        "Exp08",
        EeatCategory.EXP,
        "Quantified Metrics",
        "Measurable experience data (time, cost, success rate) is reported.",
    ),
    (
        "Exp09",
        EeatCategory.EXP,
        "Repeated Testing",
        "Multiple tests or long-term tracking back the conclusion.",
    ),
    (
        "Exp10",
        EeatCategory.EXP,
        "Limitations Acknowledged",
        "Article states which scenarios it did not test.",
    ),
    # Ept — Expertise
    (
        "Ept01",
        EeatCategory.EPT,
        "Author Identity",
        "Byline includes avatar plus a bio of more than thirty words.",
    ),
    (
        "Ept02",
        EeatCategory.EPT,
        "Credentials Display",
        "Relevant degrees, certifications, or years of experience are shown.",
    ),
    (
        "Ept03",
        EeatCategory.EPT,
        "Professional Vocabulary",
        "Industry terminology is used accurately throughout.",
    ),
    (
        "Ept04",
        EeatCategory.EPT,
        "Technical Depth",
        "Parameters, thresholds, and examples are concrete and actionable.",
    ),
    (
        "Ept05",
        EeatCategory.EPT,
        "Methodology Rigor",
        "Analytical method is described in reproducible detail.",
    ),
    (
        "Ept06",
        EeatCategory.EPT,
        "Edge Case Awareness",
        "At least two exceptions or non-applicable scenarios are discussed.",
    ),
    (
        "Ept07",
        EeatCategory.EPT,
        "Historical Context",
        "Article shows knowledge of the field's evolution over time.",
    ),
    (
        "Ept08",
        EeatCategory.EPT,
        "Reasoning Transparency",
        "Choices between options are justified with explicit tradeoffs.",
    ),
    (
        "Ept09",
        EeatCategory.EPT,
        "Cross-domain Integration",
        "Knowledge from adjacent fields is connected and applied.",
    ),
    (
        "Ept10",
        EeatCategory.EPT,
        "Editorial Process",
        '"Reviewed by" or "Fact-checked by" labels are present.',
    ),
    # A — Authority
    (
        "A01",
        EeatCategory.A,
        "Backlink Profile",
        "Authoritative sites (.edu, .gov, recognised leaders) cite this content.",
    ),
    (
        "A02",
        EeatCategory.A,
        "Media Mentions",
        '"Featured in" media logos are displayed where applicable.',
    ),
    (
        "A03",
        EeatCategory.A,
        "Industry Awards",
        "Relevant industry awards or recognitions are listed.",
    ),
    (
        "A04",
        EeatCategory.A,
        "Publishing Record",
        "Conference talks, publications, or patents are referenced.",
    ),
    (
        "A05",
        EeatCategory.A,
        "Brand Recognition",
        "Brand has measurable search volume or branded queries.",
    ),
    (
        "A06",
        EeatCategory.A,
        "Social Proof",
        "Authentic user testimonials with verifiable details are present.",
    ),
    (
        "A07",
        EeatCategory.A,
        "Knowledge Graph Presence",
        "Subject has a Wikipedia entry or Google Knowledge Panel.",
    ),
    (
        "A08",
        EeatCategory.A,
        "Entity Consistency",
        "Brand and author information is consistent across the web.",
    ),
    (
        "A09",
        EeatCategory.A,
        "Partnership Signals",
        "Documented partnerships with authoritative organisations are visible.",
    ),
    (
        "A10",
        EeatCategory.A,
        "Community Standing",
        "Author or brand is active and influential in professional communities.",
    ),
    # T — Trust
    (
        "T01",
        EeatCategory.T,
        "Legal Compliance",
        "Privacy Policy and Terms of Service are present and reachable.",
    ),
    (
        "T02",
        EeatCategory.T,
        "Contact Transparency",
        "A physical address or at least two contact methods are listed.",
    ),
    (
        "T03",
        EeatCategory.T,
        "Security Standards",
        "Site is HTTPS-only with no browser security warnings.",
    ),
    (
        "T04",
        EeatCategory.T,
        "Disclosure Statements",
        "Affiliate links are disclosed at the point of use.",
    ),
    (
        "T05",
        EeatCategory.T,
        "Editorial Policy",
        "Content standards and review process are published.",
    ),
    (
        "T06",
        EeatCategory.T,
        "Correction & Update Policy",
        "A corrections page or article-level changelog is published.",
    ),
    (
        "T07",
        EeatCategory.T,
        "Ad Experience",
        "Ads occupy under 30% of viewport and avoid intrusive popups.",
    ),
    (
        "T08",
        EeatCategory.T,
        "Risk Disclaimers",
        "YMYL topics carry the appropriate disclaimers.",
    ),
    (
        "T09",
        EeatCategory.T,
        "Review Authenticity",
        "Reviews show authenticity signals (verified purchase, photos, dates).",
    ),
    (
        "T10",
        EeatCategory.T,
        "Customer Support",
        "Return policy, complaint channels, and response SLAs are clear.",
    ),
)


# Default schema-emit templates seeded at DB init (PLAN.md L500-L502).
# Six per-task brief; PLAN.md L501-L502 lists 8 (adds HowTo, BreadcrumbList);
# we stop at six per the M1.A acceptance criteria, leaving HowTo +
# BreadcrumbList for the M3 publish skill once we know they remain in scope
# (HowTo rich results were retired Sep 2023 — keeping the wider list out
# of the seed avoids a guaranteed DEPRECATED sweep).
_SCHEMA_EMIT_TEMPLATES: Final[tuple[tuple[str, dict[str, Any]], ...]] = (
    (
        "Article",
        {
            "@context": "https://schema.org",
            "@type": "Article",
            "headline": "{{ title }}",
            "author": {"@type": "Person", "name": "{{ author_name }}"},
            "datePublished": "{{ published_at_iso }}",
            "dateModified": "{{ last_refreshed_at_iso }}",
        },
    ),
    (
        "BlogPosting",
        {
            "@context": "https://schema.org",
            "@type": "BlogPosting",
            "headline": "{{ title }}",
            "author": {"@type": "Person", "name": "{{ author_name }}"},
            "datePublished": "{{ published_at_iso }}",
        },
    ),
    (
        "FAQPage",
        {
            "@context": "https://schema.org",
            "@type": "FAQPage",
            "mainEntity": [
                {
                    "@type": "Question",
                    "name": "{{ question }}",
                    "acceptedAnswer": {"@type": "Answer", "text": "{{ answer }}"},
                }
            ],
        },
    ),
    (
        "Product",
        {
            "@context": "https://schema.org",
            "@type": "Product",
            "name": "{{ title }}",
            "description": "{{ description }}",
            "offers": {"@type": "Offer", "url": "{{ canonical_url }}"},
        },
    ),
    (
        "Organization",
        {
            "@context": "https://schema.org",
            "@type": "Organization",
            "name": "{{ org_name }}",
            "url": "{{ site_url }}",
            "logo": "{{ logo_url }}",
        },
    ),
    (
        "Review",
        {
            "@context": "https://schema.org",
            "@type": "Review",
            "itemReviewed": {"@type": "Thing", "name": "{{ subject }}"},
            "author": {"@type": "Person", "name": "{{ author_name }}"},
            "reviewRating": {"@type": "Rating", "ratingValue": "{{ rating }}"},
        },
    ),
)


def _utcnow() -> datetime:
    return datetime.now(tz=UTC).replace(tzinfo=None)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def seed_eeat_criteria(session: Session, project_id: int) -> int:
    """Seed the canonical 80 EEAT criteria for ``project_id``.

    Idempotent: rows already present (matched on ``(project_id, code)``)
    are left untouched. T04, C01, R10 are always inserted as
    ``tier='core', required=true, active=true``; the M1.B repository
    layer enforces the invariant that those rows cannot be deactivated.

    Returns the number of rows inserted on this call.
    """
    existing_codes = set(
        session.exec(select(EeatCriterion.code).where(EeatCriterion.project_id == project_id)).all()
    )
    now = _utcnow()
    inserted = 0
    for code, category, name, standard in _EEAT_ITEMS:
        if code in existing_codes:
            continue
        is_core = code in _CORE_VETO_CODES
        row = EeatCriterion(
            project_id=project_id,
            code=code,
            category=category,
            description=name,
            text=standard,
            weight=10,
            required=is_core,
            active=True,
            tier=EeatTier.CORE if is_core else EeatTier.RECOMMENDED,
            version=1,
            created_at=now,
        )
        session.add(row)
        inserted += 1
    session.commit()
    return inserted


def seed_schema_emits_templates(session: Session) -> int:
    """Seed the 6 default schema-emit templates as global rows.

    ``article_id IS NULL`` flags these as templates that the per-project
    bootstrap procedure clones into per-article rows. Idempotent on
    ``type``: re-running leaves existing rows alone.
    """
    existing_types = set(
        session.exec(
            select(SchemaEmit.type).where(SchemaEmit.article_id.is_(None))  # type: ignore[union-attr]
        ).all()
    )
    inserted = 0
    for idx, (schema_type, template) in enumerate(_SCHEMA_EMIT_TEMPLATES):
        if schema_type in existing_types:
            continue
        row = SchemaEmit(
            article_id=None,
            type=schema_type,
            schema_json=template,
            position=idx,
            is_primary=False,
            version_published=None,
            validated_at=None,
        )
        session.add(row)
        inserted += 1
    session.commit()
    return inserted


# ---------------------------------------------------------------------------
# Migration-only helper — uses Alembic's `op` because at migration time
# we don't have a SQLModel session bound to the upgrade's connection
# without extra plumbing.
# ---------------------------------------------------------------------------


def seed_schema_emits_templates_via_op() -> None:
    """Insert the 6 schema templates from inside an Alembic upgrade.

    Uses ``INSERT OR IGNORE`` so re-running the migration after a
    partial failure (or against a DB seeded by a parallel path) does
    not fail with a unique-constraint violation.
    """
    bind = op.get_bind()
    for idx, (schema_type, template) in enumerate(_SCHEMA_EMIT_TEMPLATES):
        bind.execute(
            text(
                "INSERT OR IGNORE INTO schema_emits "
                "(article_id, type, schema_json, position, is_primary, "
                "version_published, validated_at) "
                "VALUES (NULL, :type, :schema_json, :position, 0, NULL, NULL)"
            ),
            {
                "type": schema_type,
                "schema_json": _json_dumps(template),
                "position": idx,
            },
        )


def _json_dumps(value: dict[str, Any]) -> str:
    """Compact JSON serialisation used by the migration template inserts."""
    import json

    return json.dumps(value, separators=(",", ":"))


__all__ = [
    "seed_eeat_criteria",
    "seed_schema_emits_templates",
    "seed_schema_emits_templates_via_op",
]
