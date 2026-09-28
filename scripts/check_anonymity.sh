#!/usr/bin/env bash
set -euo pipefail

echo "Running Anonymity Checks..."

# Personal identifiers that MUST NOT appear anywhere
PATTERNS=(
    "João"
    "joao"
    "Felipe"
    "felipe"
    "Souza"
    "souza"
    "JohnScheuer"
    "johnscheuer"
    "johnfelipe13"
    "99705"
    "4864"
    "JohnScheuer7"
    "linkedin.com/in/joao"
    "linkedin.com/in/Joao"
)

VIOLATIONS=0
for pattern in "${PATTERNS[@]}"; do
    if grep -ri "$pattern" \
        --include="*.py" --include="*.ts" --include="*.tsx" \
        --include="*.json" --include="*.toml" --include="*.yml" \
        --include="*.yaml" --include="*.md" --include="*.sh" \
        --include="Dockerfile" --include=".env*" \
        --exclude-dir=node_modules --exclude-dir=.git \
        --exclude-dir=.venv --exclude-dir=__pycache__ \
        --exclude="check_anonymity.sh" \
        . 2>/dev/null; then
        echo "VIOLATION: Found '$pattern' in repository!"
        VIOLATIONS=1
    fi
done

if [ $VIOLATIONS -eq 1 ]; then
    echo "ANONYMITY CHECK FAILED. Remove all personal identifiers."
    exit 1
else
    echo "Anonymity check passed."
    exit 0
fi