-- =============================================================================
-- Migration 00014: RGPD Right to Erasure / Account Deletion Lifecycle (30 Days Soft Delete)
-- =============================================================================

ALTER TABLE public.users ADD COLUMN IF NOT EXISTS status VARCHAR(30) DEFAULT 'active';
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS deletion_requested_at TIMESTAMPTZ;
ALTER TABLE public.users ADD COLUMN IF NOT EXISTS scheduled_purge_at TIMESTAMPTZ;

-- Index on scheduled_purge_at for efficient cleanup cron tasks
CREATE INDEX IF NOT EXISTS idx_users_scheduled_purge ON public.users(scheduled_purge_at) WHERE scheduled_purge_at IS NOT NULL;
