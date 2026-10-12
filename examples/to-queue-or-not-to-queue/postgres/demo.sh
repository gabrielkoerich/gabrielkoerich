#!/usr/bin/env bash
# Five workers share the jobs table from claim.sql, with the lease cut to 2 seconds so it expires during the run
set -euo pipefail
cd "$(dirname "$0")"

docker run -d --rm --name pgq-demo -e POSTGRES_PASSWORD=x postgres:17-alpine >/dev/null
trap 'docker stop pgq-demo >/dev/null' EXIT
until docker exec pgq-demo pg_isready -U postgres -q; do sleep 0.5; done
sleep 1

psql() { docker exec -i pgq-demo psql -U postgres -qtA "$@"; }
claim=$(sed -n '/^UPDATE jobs/,/RETURNING/p' claim.sql | sed "s/30 seconds/2 seconds/")
psql < claim.sql >/dev/null
psql -c "INSERT INTO jobs (payload) VALUES ('one'), ('two'), ('three')"

show() {
  local who=$1 row
  row=$(psql -c "$claim" | head -1)
  if [ -n "$row" ]; then
    echo "worker $who: claimed ${row%%|*} attempt ${row##*|}"
  else
    echo "worker $who: nothing"
  fi
}

# Worker A claims job 1 and keeps its transaction open for 3 seconds, longer than the lease
printf 'BEGIN;\n%s\nSELECT pg_sleep(3);\nCOMMIT;\n' "$claim" | psql >/dev/null &
sleep 0.5
echo "worker A holds job 1 in an open transaction"
show B
show C
show D
wait
echo "job 1's lease expires"
show E
