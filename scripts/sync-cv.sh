#!/bin/bash
# Copy CV from bean repository to gabrielkoerich website
# Usage: ./scripts/sync-cv.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BEAN_REPO="$(cd "$REPO_ROOT/../bean" && pwd)"

echo "Syncing CV from bean repository..."

# Check if bean repo exists
if [ ! -d "$BEAN_REPO" ]; then
    echo "Error: bean repository not found at $BEAN_REPO"
    exit 1
fi

# Check if source CV exists
if [ ! -f "$BEAN_REPO/md/about/cv-combined.md" ]; then
    echo "Error: CV not found at $BEAN_REPO/md/about/cv-combined.md"
    exit 1
fi

# Convert markdown to Zola format with frontmatter
echo "Converting CV to Zola format..."

cat > "$REPO_ROOT/content/cv.md" << 'FRONTMATTER'
+++
title = "CV"
description = "Senior Software Engineer with 17+ years experience in Rust, Solana, PHP, and Laravel"
+++

FRONTMATTER

# Read the CV content and append it
sed 's/^# Gabriel Koerich$/## Summary/' "$BEAN_REPO/md/about/cv-combined.md" >> "$REPO_ROOT/content/cv.md"

echo "✓ CV synced successfully to content/cv.md"
