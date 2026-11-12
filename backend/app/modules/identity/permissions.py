"""Permission catalogue and default (system) roles.

Roles are data. Administrators with ``roles.manage`` can create custom roles and change
role-permission assignments at runtime. System roles are created if missing and are never
silently overwritten, so local customisation survives upgrades.
"""
from __future__ import annotations

PERMISSIONS: dict[str, str] = {
    # content
    "destinations.read_draft": "View unpublished destinations and revisions",
    "destinations.edit": "Create and edit destination drafts",
    "destinations.publish": "Publish, schedule, archive and roll back destinations",
    "categories.manage": "Create and edit destination categories",
    "advisories.manage": "Create and publish official travel advisories",
    "events.manage": "Manage festivals and events",
    "media.manage": "Review and manage media assets and rights",
    "geo.manage": "Manage coordinates, sensitivity and verified route segments",
    "heritage.read_restricted": "See restricted heritage details (precise coordinates of protected sites)",
    # knowledge & AI
    "knowledge.upload": "Upload documents to the Knowledge Vault",
    "knowledge.review": "Review document metadata and extraction",
    "knowledge.publish": "Approve and publish documents for retrieval",
    "knowledge.read_internal": "Retrieve internal-classified knowledge",
    "knowledge.read_restricted": "Retrieve restricted/sacred-classified knowledge",
    "ai.admin": "Manage AI modes, model registry and evaluations",
    "bureau.assistant": "Use the internal Bureau AI assistant",
    # translation
    "translations.edit": "Draft translations",
    "translations.approve": "Approve translations as professionally reviewed",
    # community
    "community.moderate": "Moderate visitor content, reports and appeals",
    # awards
    "awards.manage": "Create and administer competitions",
    "awards.authorize": "Record Bureau authorization / legal approval for competitions",
    "awards.judge": "Score assigned competition entries",
    "awards.approve_winners": "Approve proposed winners (second approver)",
    "awards.finance": "Manage sponsors and prize fulfilment",
    # providers
    "providers.verify": "Verify tourism providers and licences",
    # operations
    "analytics.view": "View analytics dashboards",
    "tourism_stats.record": "Record measured tourism statistics with their source",
    "reports.export": "Export reports",
    "editorial.assign": "Assign editorial tasks",
    "users.manage": "Manage staff accounts and role assignments",
    "roles.manage": "Create roles and change their permissions",
    "audit.view": "View the audit log and verify its integrity",
    "settings.manage": "Change feature flags and platform settings",
}

ROLES: dict[str, tuple[str, list[str]]] = {
    "executive": ("Executive leadership", ["analytics.view", "reports.export", "destinations.read_draft", "bureau.assistant", "audit.view"]),
    "tourism_officer": ("Tourism officer", ["destinations.read_draft", "destinations.edit", "advisories.manage", "events.manage", "analytics.view", "bureau.assistant", "editorial.assign", "tourism_stats.record"]),
    "heritage_specialist": ("Cultural heritage specialist", ["destinations.read_draft", "destinations.edit", "destinations.publish", "knowledge.upload", "knowledge.review", "knowledge.publish", "knowledge.read_internal", "knowledge.read_restricted", "heritage.read_restricted", "media.manage", "bureau.assistant"]),
    "content_editor": ("Content editor", ["destinations.read_draft", "destinations.edit", "destinations.publish", "categories.manage", "events.manage", "media.manage", "knowledge.upload", "editorial.assign", "bureau.assistant"]),
    "translator": ("Translator", ["destinations.read_draft", "translations.edit"]),
    "translation_reviewer": ("Translation reviewer", ["destinations.read_draft", "translations.edit", "translations.approve"]),
    "geo_officer": ("Geographic data officer", ["destinations.read_draft", "geo.manage", "heritage.read_restricted"]),
    "provider_verifier": ("Provider verification staff", ["providers.verify"]),
    "moderator": ("Community moderator", ["community.moderate", "media.manage"]),
    "competition_admin": ("Competition administrator", ["awards.manage"]),
    "competition_approver": ("Competition approver (Bureau)", ["awards.authorize", "awards.approve_winners"]),
    "judge": ("Competition judge", ["awards.judge"]),
    "finance_officer": ("Finance and sponsorship officer", ["awards.finance", "reports.export"]),
    "knowledge_curator": ("Knowledge curator", ["knowledge.upload", "knowledge.review", "knowledge.publish", "knowledge.read_internal"]),
    "ai_admin": ("AI administrator", ["ai.admin", "knowledge.read_internal", "analytics.view"]),
    "system_admin": ("System administrator", ["users.manage", "roles.manage", "settings.manage", "audit.view", "ai.admin"]),
    "auditor": ("Auditor", ["audit.view", "analytics.view", "destinations.read_draft"]),
}
