-- A jobs table that several workers can share
CREATE TABLE jobs (
  id           bigserial PRIMARY KEY,
  payload      text        NOT NULL,
  run_at       timestamptz NOT NULL DEFAULT now(),
  locked_until timestamptz,
  attempts     int         NOT NULL DEFAULT 0
);

-- Claim one ready job: SKIP LOCKED passes over rows another worker is claiming
-- right now, and locked_until is the lease that keeps the job away from them after
UPDATE jobs
SET locked_until = now() + interval '30 seconds',
    attempts     = attempts + 1
WHERE id = (
  SELECT id FROM jobs
  WHERE run_at <= now()
    AND (locked_until IS NULL OR locked_until < now())
  ORDER BY id
  LIMIT 1
  FOR UPDATE SKIP LOCKED
)
RETURNING id, payload, attempts;

-- When the work is done, delete the job (or mark it done) in the same transaction as its result
-- DELETE FROM jobs WHERE id = $1;
