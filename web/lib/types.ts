// API contract types (mirrors backend/app/modules/*). Keep in sync with the FastAPI schemas.

export type Locale = "en" | "ti" | "am";
export type TriState = "yes" | "no" | "unknown";
export type AdvisoryLevel = "info" | "caution" | "avoid_nonessential" | "travel_not_advised";

export interface ApiErrorBody {
  error: { code: string; message: string; details?: unknown };
}

export interface MediaItem {
  id: string;
  width: number;
  height: number;
  urls: Record<string, string>;
  alt_text_i18n?: Record<string, string>;
  caption_i18n?: Record<string, string>;
  license?: string | null;
  credit?: string | null;
  attribution_url?: string | null;
  is_illustrative?: boolean;
  is_reconstruction?: boolean;
  is_ai_generated?: boolean;
  is_hero?: boolean;
}

export interface Source {
  title: string;
  author?: string | null;
  publisher?: string | null;
  year?: string | null;
  url?: string | null;
  note?: string | null;
}

export interface Advisory {
  id: string;
  level: AdvisoryLevel;
  title: string;
  body: string;
  issuing_authority: string;
  source_url?: string | null;
  effective_from: string;
  effective_until?: string | null;
  region_wide: boolean;
  destination_ids?: string[];
  is_synthetic?: boolean;
  status?: string;
}

export interface EventItem {
  id?: string;
  slug: string;
  title: string;
  description: string;
  kind: string;
  starts_on: string | null;
  ends_on: string | null;
  ethiopian_date: string | null;
  date_note: string;
  verified_at: string | null;
  sources?: Source[];
  is_synthetic?: boolean;
}

export interface Destination {
  id: string;
  slug: string;
  name: string;
  eyebrow: string;
  summary: string;
  body?: string | null;
  etiquette?: string;
  accessibility_notes?: string;
  category: { slug: string; name: string } | null;
  interests: string[];
  area: string;
  coordinates: { lat: number; lng: number; precision: "exact" | "approximate" } | null;
  precise_coordinates?: { lat: number; lng: number } | null;
  visit_duration_minutes: number | null;
  accessibility: { step_free?: TriState; terrain?: string; facilities?: string; notes?: string };
  permit_required: TriState;
  permit_authority?: string | null;
  contact?: Record<string, string>;
  timeline?: { period?: string; label?: string; label_i18n?: Record<string, string>; source_ref?: string }[];
  sources: Source[];
  heritage_designations?: { name?: string; body?: string; year?: string; url?: string }[];
  verified_at: string | null;
  review_due?: string | null;
  is_stale: boolean;
  translation_status: "draft" | "machine" | "reviewed" | null;
  locale: string | null;
  requested_locale: string;
  available_locales: string[];
  advisory_level: AdvisoryLevel | null;
  advisories?: Advisory[];
  events?: EventItem[];
  media: MediaItem[];
  is_synthetic: boolean;
}

export interface Category {
  id: string;
  slug: string;
  name: string;
  description: string;
  icon?: string | null;
  sort_order: number;
}

export interface Me {
  id: string;
  email: string;
  display_name: string;
  locale: string;
  email_verified: boolean;
  is_staff: boolean;
  mfa_enabled: boolean;
  mfa_verified: boolean;
  permissions: string[];
  pending_permissions: string[];
  roles: string[];
  csrf_token: string | null;
}

export interface PublicConfig {
  feature_flags: Record<string, boolean>;
  locales: string[];
}

export interface Citation {
  n: number;
  chunk_id: string;
  document_title: string;
  author?: string | null;
  publisher?: string | null;
  published_on?: string | null;
  url?: string | null;
  excerpt: string;
  verified_at?: string | null;
  language?: string | null;
}

export interface TieAnswer {
  conversation_id: string;
  message_id: string;
  answer: string;
  confidence: "grounded" | "partial" | "insufficient_evidence" | "refused";
  citations: Citation[];
  warnings: string[];
  follow_up_questions: string[];
  mode_used: string;
  /** null when no language model produced the answer (retrieval-only / fallback). */
  provider: { name: string; local: boolean; model?: string | null } | null;
  latency_ms: number;
}

export interface PlanStop {
  slug: string;
  name: string;
  area: string;
  coordinates: Destination["coordinates"];
  visit_duration_minutes: number | null;
  permit_required: TriState;
  advisory_level: AdvisoryLevel | null;
  reasons: string[];
  travel_from_previous: {
    distance_km: number | null;
    duration_minutes: number | null;
    verified: boolean;
    basis: string;
  } | null;
}

export interface Plan {
  mode: "operational" | "virtual";
  notice: string;
  days: { day: number; stops: PlanStop[]; unknowns: string[] }[];
  excluded: { slug: string; name: string; reason: string }[];
  virtual_alternatives: { slug: string; name: string }[];
  generated_at: string;
}

export interface Memory {
  id: string;
  title: string;
  excerpt: string;
  body?: string;
  destination: { slug: string; name: string } | null;
  author: { handle: string; display_name: string };
  media: MediaItem[];
  published_at: string;
  featured: boolean;
  locale: string;
}

export interface Competition {
  slug: string;
  title: string;
  status: string;
  opens_at: string | null;
  closes_at: string | null;
  categories: { key: string; name: string; description?: string }[];
  prize_description: string | null;
  rules_url?: string | null;
  is_live: boolean;
  description?: string;
}

export interface Provider {
  slug: string;
  name: string;
  type: string;
  area: string;
  summary: string;
  description?: string;
  contact?: Record<string, string>;
  verification: {
    status: "verified" | "pending" | "expired" | "unverified";
    verified_at: string | null;
    licence_authority?: string | null;
  };
}
