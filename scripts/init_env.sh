#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")/.."

echo "▶ load .env"
if [[ -f ./.env ]]; then
  set -a; . ./.env; set +a
else
  echo "❌ .env not found in $(pwd)"; exit 1
fi

: "${PROJECT_ID:=upbeat-legacy-390709}"
: "${REGION:=europe-west3}"
: "${RESULTS_BUCKET:=${PROJECT_ID}-results}"
: "${PROJECT_NUMBER:=$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)' 2>/dev/null || echo "")}"

echo "PROJECT_ID=$PROJECT_ID"
echo "REGION=$REGION"
echo "RESULTS_BUCKET=$RESULTS_BUCKET"

echo "▶ ensure gcloud auth"
ACTIVE_ACCT="$(gcloud auth list --filter=status:ACTIVE --format='value(account)' 2>/dev/null || true)"
if [[ -z "$ACTIVE_ACCT" ]]; then
  gcloud auth login
fi

CFG="doc-analyzer"
if ! gcloud config configurations list --format='value(name)' | grep -qx "$CFG"; then
  gcloud config configurations create "$CFG" --quiet
fi
gcloud config configurations activate "$CFG" --quiet
gcloud config set project "$PROJECT_ID" --quiet
gcloud config set run/region "$REGION" --quiet

echo "✅ environment ready."
