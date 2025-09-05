#!/usr/bin/env bash
set -euo pipefail

echo "▶ step 0: go to repo"
cd "$(dirname "$0")/.."

echo "▶ step 1: load .env"
if [[ -f ./.env ]]; then
  set -a; . ./.env; set +a
else
  echo "❌ .env not found in $(pwd). Create it first."; exit 1
fi

: "${PROJECT_ID:=upbeat-legacy-390709}"
: "${REGION:=europe-west3}"
: "${RESULTS_BUCKET:=${PROJECT_ID}-results}"
: "${PROJECT_NUMBER:=$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)' 2>/dev/null || echo "")}"

echo "  PROJECT_ID=$PROJECT_ID"
echo "  REGION=$REGION"
echo "  RESULTS_BUCKET=$RESULTS_BUCKET"

echo "▶ step 2: ensure gcloud auth"
ACTIVE_ACCT="$(gcloud auth list --filter=status:ACTIVE --format='value(account)' 2>/dev/null || true)"
if [[ -z "$ACTIVE_ACCT" ]]; then
  echo "  No active account → launching 'gcloud auth login'..."
  gcloud auth login
fi
gcloud auth list

echo "▶ step 3: lock configuration"
CFG="doc-analyzer"
if ! gcloud config configurations list --format='value(name)' | grep -qx "$CFG"; then
  gcloud config configurations create "$CFG" --quiet
fi
gcloud config configurations activate "$CFG" --quiet
gcloud config set project "$PROJECT_ID" --quiet
gcloud config set run/region "$REGION" --quiet

echo "▶ step 4: docker auth for Artifact Registry"
gcloud auth configure-docker "${REGION}-docker.pkg.dev" --quiet

echo "▶ step 5: compute IMAGE and SA"
IMAGE="${REGION}-docker.pkg.dev/${PROJECT_ID}/doc-analyzer/app:latest"
if [[ -z "$PROJECT_NUMBER" ]]; then
  PROJECT_NUMBER="$(gcloud projects describe "$PROJECT_ID" --format='value(projectNumber)')"
fi
SA="$(gcloud run services describe doc-analyzer --region="$REGION" --format='value(spec.template.spec.serviceAccountName)' 2>/dev/null || true)"
if [[ -z "$SA" ]]; then
  SA="${PROJECT_NUMBER}-compute@developer.gserviceaccount.com"
fi
echo "  IMAGE=$IMAGE"
echo "  SA=$SA"

echo "▶ step 6: grant storage.objectAdmin on results bucket"
gcloud storage buckets add-iam-policy-binding "gs://${RESULTS_BUCKET}" \
  --member="serviceAccount:${SA}" \
  --role="roles/storage.objectAdmin" \
  --quiet || true

echo "▶ step 7: build & deploy"
gcloud builds submit --tag "$IMAGE" .
gcloud run deploy doc-analyzer \
  --image="$IMAGE" \
  --region="$REGION" \
  --platform=managed \
  --allow-unauthenticated

echo "▶ step 8: health check"
SERVICE_URL="$(gcloud run services describe doc-analyzer --region="$REGION" --format='value(status.url)')"
echo "  SERVICE_URL: $SERVICE_URL"
curl -s -i "$SERVICE_URL/health" || true

echo "✅ done."
