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
  actions?: GuideAction[];
}

export type GuideAction =
  | { type: "open_planner"; label: string; params: { days?: number; interests?: string[]; start_slug?: string } }
  | { type: "open_destination"; label: string; slug: string };

export interface ConversationSummary {
  id: string;
  title: string;
  persona: string;
  updated_at: string;
  message_count: number;
}

export interface Suggestion {
  text: string;
  category: string;
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
  alternatives?: { slug: string; name: string; reason: string }[];
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
  checklist?: ChecklistItem[];
  summary?: { stop_count: number; days: number; known_minutes: number; verified_legs: number; unverified_legs: number };
  edited?: boolean;
}

export interface ChecklistItem {
  kind: "permit" | "advisory" | "accessibility" | "verification" | "duration" | "travel";
  text: string;
  slugs: string[];
}

/* ------------------------------------------------------------------ Journals (Substack-like) */

export interface PersonRef {
  handle: string;
  display_name: string;
}

export interface JournalSummary {
  id: string;
  title: string;
  subtitle: string;
  excerpt: string;
  cover: MediaItem | null;
  author: PersonRef;
  publication: { handle: string; name: string };
  destination: { slug: string; name: string } | null;
  tags: string[];
  published_at: string | null;
  reading_minutes: number;
  like_count: number;
  comment_count: number;
  liked: boolean;
}

export type BlockType = "paragraph" | "heading" | "quote" | "image" | "divider";

export interface JournalBlock {
  type: BlockType;
  text?: string;
  media?: MediaItem | null;
  caption?: string;
}

export interface JournalPost extends JournalSummary {
  blocks: JournalBlock[];
  status?: string;
  is_author?: boolean;
}

export interface JournalComment {
  id: string;
  parent_id: string | null;
  body: string;
  author: PersonRef;
  created_at: string;
  can_delete: boolean;
}

export interface Publication {
  handle: string;
  name: string;
  tagline: string;
  about: string;
  cover: MediaItem | null;
  author: { display_name: string };
  subscriber_count: number;
  is_subscribed: boolean;
  email_digest: boolean;
  posts: JournalSummary[];
}

export interface NotificationItem {
  id: string;
  kind: string;
  title: string;
  body: string;
  link: string | null;
  created_at: string;
  read: boolean;
}

/* ------------------------------------------------------------------ Spaces (Discord-like) */

export interface Channel {
  slug: string;
  name: string;
  topic: string;
  kind: "text" | "announcements";
  slow_mode_seconds: number;
  can_post: boolean;
}

export interface Space {
  slug: string;
  name: string;
  description: string;
  icon: string | null;
  member_count: number;
  is_member: boolean;
  my_role: "member" | "moderator" | null;
  channels: Channel[];
}

export interface Reaction {
  emoji: string;
  count: number;
  mine: boolean;
}

export interface SpaceMessage {
  id: number;
  author: PersonRef & { role?: string | null };
  body: string;
  reply_to: { id: number; excerpt: string; author: PersonRef | string } | null;
  reactions: Reaction[];
  created_at: string;
  edited_at: string | null;
  status: "visible" | "held" | "removed";
  can_edit: boolean;
  can_delete: boolean;
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
