#!/usr/bin/env bash
set -euo pipefail

echo "🔍 Running Anonymity Checks..."

PATTERNS=(
    "github\\.com/[a-zA-Z0-9_-]+"
    "linkedin\\.com/in/"
    "candidate@[a-z]"
)

VIOLATIONS=0
for pattern in "${PATTERNS[@]}"; do
    if grep -riE "$pattern" \
        --include="*.py" --include="*.ts" --include="*.tsx" \
        --include="*.md" --include="*.yml" --include="*.yaml" \
        --exclude-dir=node_modules --exclude-dir=.git --exclude-dir=.venv \
        . 2>/dev/null; then
        echo "❌ VIOLATION DETECTED: Pattern '$pattern' found!"
        VIOLATIONS=1
    fi
done

if [ $VIOLATIONS -eq 1 ]; then
    echo "🚨 Anonymity check failed. Please remove personal identifiers."
    exit 1
else
    echo "✅ Anonymity check passed! No personal information detected."
    exit 0
fi
