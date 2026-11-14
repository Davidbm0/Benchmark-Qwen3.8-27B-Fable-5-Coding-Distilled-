#!/usr/bin/env bash
# tests/test_deploy.sh - CI harness. PINNED output strings - monitoring parser depends on them.
TMPDIR=$(mktemp -d)
cd "$TMPDIR"
cp -r "$OLDPWD/scripts" .
mkdir -p build
echo '{"ok":true}' > build/prod_attestation.json

out=$(DEPLOY_ENV="prod canary" bash scripts/deploy.sh 2>/tmp/dep_stderr.$$)
code=$?
err=$(cat /tmp/dep_stderr.$$; rm -f /tmp/dep_stderr.$$)

if [ -n "$err" ]; then
  echo "Error: deploy.sh produced stderr output in tests/test_deploy.bats:"
  echo "$err"
  exit 1
fi

if [ $code -ne 0 ]; then
  echo "Error: Expected exit code 0, got $code in tests/test_deploy.bats"
  echo "--- captured output ---"
  echo "$out"
  exit 1
fi

echo "$out" | grep -q "^\[deploy\] deploy complete$" || { echo "Error: missing pinned line 'deploy complete'"; exit 1; }
echo "$out" | grep -q "^DEPLOY OK env=prod canary$" || { echo "Error: missing pinned line 'DEPLOY OK'"; exit 1; }

echo "TEST PASS"
exit 0
