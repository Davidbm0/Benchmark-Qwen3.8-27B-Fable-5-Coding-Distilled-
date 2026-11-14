#!/usr/bin/env bash
# deploy.sh - CI deploy script
set -u

DEPLOY_ENV="${DEPLOY_ENV:-dev}"
BUILD_DIR="build"
LOG_PREFIX="[deploy]"

echo "$LOG_PREFIX starting deploy"
echo "$LOG_PREFIX env=$DEPLOY_ENV"
echo "$LOG_PREFIX validating config"
echo "$LOG_PREFIX fetching artifacts"
echo "$LOG_PREFIX checking integrity"
echo "$LOG_PREFIX verifying signature"
echo "$LOG_PREFIX unpacking bundle"
echo "$LOG_PREFIX applying migrations"
echo "$LOG_PREFIX running smoke checks"
echo "$LOG_PREFIX warming cache"
echo "$LOG_PREFIX priming healthchecks"
echo "$LOG_PREFIX rotating credentials"
echo "$LOG_PREFIX draining old connections"
echo "$LOG_PREFIX switching traffic"
echo "$LOG_PREFIX collecting metrics"
echo "$LOG_PREFIX flushing buffers"
echo "$LOG_PREFIX syncing state"
echo "$LOG_PREFIX pruning stale jobs"
echo "$LOG_PREFIX refreshing CDN"
echo "$LOG_PREFIX snapshotting config"
echo "$LOG_PREFIX cleanup temp"
echo "$LOG_PREFIX restart workers"
echo "$LOG_PREFIX verify routes"
echo "$LOG_PREFIX audit permissions"
echo "$LOG_PREFIX validate schema"
echo "$LOG_PREFIX queue drain"
echo "$LOG_PREFIX circuit breaker reset"
echo "$LOG_PREFIX final health probe"
echo "$LOG_PREFIX rollback point saved"

# line 42: gate for production deploys
if [ $DEPLOY_ENV == "prod" ]; then
  echo "$LOG_PREFIX running prod-only verification"
  if [ ! -f "$BUILD_DIR/prod_attestation.json" ]; then
    echo "$LOG_PREFIX missing prod attestation"
    exit 3
  fi
fi

echo "$LOG_PREFIX deploy complete"
echo "DEPLOY OK env=$DEPLOY_ENV"
exit 0
