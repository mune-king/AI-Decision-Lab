-- VDT VAS: run via Supabase SQL Editor after review.
-- Pseudonymous responses only; no student number or name.
CREATE TABLE IF NOT EXISTS public.vdt_vas_responses (
 id uuid PRIMARY KEY,
 research_id text NOT NULL CHECK (research_id ~ '^[A-Za-z0-9_-]{1,32}$'),
 phase text NOT NULL CHECK (phase IN ('before','after')),
 eye smallint NOT NULL CHECK (eye BETWEEN 0 AND 100),
 neck smallint NOT NULL CHECK (neck BETWEEN 0 AND 100),
 back smallint NOT NULL CHECK (back BETWEEN 0 AND 100),
 fatigue smallint NOT NULL CHECK (fatigue BETWEEN 0 AND 100),
 focus smallint NOT NULL CHECK (focus BETWEEN 0 AND 100),
 created_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE public.vdt_vas_responses ENABLE ROW LEVEL SECURITY;
REVOKE ALL ON TABLE public.vdt_vas_responses FROM anon, authenticated;
GRANT INSERT ON TABLE public.vdt_vas_responses TO anon;
CREATE POLICY "vas_anon_insert_only" ON public.vdt_vas_responses
  FOR INSERT TO anon WITH CHECK (true);
-- No SELECT/UPDATE/DELETE for anonymous users.
-- Administrator reads with controlled server-side credentials only.
