#!/usr/bin/env bash
set -euo pipefail
SERVICE="${SERVICE:-shyam-ai-fo-scanner}"
REGION="${REGION:-asia-south1}"
echo "Deploying ${SERVICE} to Cloud Run (${REGION})..."
gcloud run deploy "${SERVICE}" \
  --source . \
  --region "${REGION}" \
  --port 8080 \
  --memory 1Gi \
  --cpu 1 \
  --timeout 300 \
  --concurrency 1 \
  --max-instances 1 \
  --no-allow-unauthenticated
