#!/usr/bin/env bash
# Build the local NXERP image from the CURRENT working tree: base image + every modified or untracked
# file under helpdesk/ and desk/ (gitignored files excluded), frontend rebuilt. Git is only read.
# Usage: docker/nxerp/build-local-image.sh [image-tag]
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
BASE="${BASE_IMAGE:-ghcr.io/sriainfotech/frappe-help-desk:nxerp-8bb287a}"
TAG="${1:-frappe-help-desk-local:nxerp-tasks}"
CTX="$(mktemp -d)"
mkdir -p "$CTX/overlay"

cd "$REPO"
git ls-files -z -m -o --exclude-standard -- helpdesk desk | while IFS= read -r -d '' f; do
  [ -f "$f" ] || continue
  case "$f" in */node_modules/*|*__pycache__*|*.pyc) continue ;; esac
  mkdir -p "$CTX/overlay/$(dirname "$f")"
  cp "$f" "$CTX/overlay/$f"
done
cp "$HERE/Dockerfile.local" "$CTX/Dockerfile"

echo "overlay files:"; (cd "$CTX/overlay" && find . -type f | sed 's#^\./##' | sort)
echo "base: $BASE  ->  tag: $TAG  (context: $CTX)"
docker build --no-cache --build-arg BASE_IMAGE="$BASE" -t "$TAG" "$CTX"
