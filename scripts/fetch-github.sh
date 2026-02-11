#!/bin/bash
# Fetch GitHub profile, pinned repos, and contributed repos
# Usage: ./fetch-github.sh [GITHUB_TOKEN]

set -e

USERNAME="gabrielkoerich"
OUTPUT_DIR="data"
TOKEN="${1:-${GITHUB_TOKEN:-}}"

mkdir -p "$OUTPUT_DIR"

echo "Fetching GitHub profile for $USERNAME..."

# Build curl headers (GitHub token if available)
AUTH_HEADER=""
if [ -n "$TOKEN" ]; then
    AUTH_HEADER="-H Authorization: token $TOKEN"
    echo "Using authenticated requests"
else
    echo "Using public API (unauthenticated)"
fi

# Fetch user profile
curl -s $AUTH_HEADER "https://api.github.com/users/$USERNAME" > "$OUTPUT_DIR/github-profile.json"

# Fetch all user repositories
echo "Fetching repositories..."
curl -s $AUTH_HEADER "https://api.github.com/users/$USERNAME/repos?sort=updated&per_page=100" > "$OUTPUT_DIR/github-repos.json"

# Pinned repos - these are manually curated on GitHub profile
# Based on user's profile as of 2026
echo "Fetching pinned repositories..."

# Define pinned repos (fetched from profile)
PINNED_REPOS=(
    "gabrielkoerich/dotfiles"
    "gabrielkoerich/lulo-cpi-example"
    "gabrielkoerich/skills"
    "gabrielkoerich/orchestrator"
    "laravel/framework"
    "Kamino-Finance/klend"
)

# Build pinned repos JSON array
echo '[' > "$OUTPUT_DIR/github-pinned.json"
FIRST=true

for repo_path in "${PINNED_REPOS[@]}"; do
    OWNER=$(echo "$repo_path" | cut -d'/' -f1)
    REPO=$(echo "$repo_path" | cut -d'/' -f2)
    
    echo "  Fetching $OWNER/$REPO..."
    
    # Fetch repo details
    REPO_DATA=$(curl -s $AUTH_HEADER "https://api.github.com/repos/$OWNER/$REPO")
    
    # Check if repo exists
    if echo "$REPO_DATA" | grep -q '"name"' && ! echo "$REPO_DATA" | grep -q '"message".*"Not Found"'; then
        if [ "$FIRST" = true ]; then
            FIRST=false
        else
            echo ',' >> "$OUTPUT_DIR/github-pinned.json"
        fi
        
        # Use Python for reliable JSON parsing
        python3 << PYEOF >> "$OUTPUT_DIR/github-pinned.json"
import json
import sys

try:
    data = '''$REPO_DATA'''
    repo = json.loads(data)
    
    result = {
        "name": repo.get("name", "$REPO"),
        "description": repo.get("description") or "",
        "html_url": repo.get("html_url", "https://github.com/$repo_path"),
        "language": {"name": repo.get("language") or ""},
        "stargazers": {"totalCount": repo.get("stargazers_count", 0)},
        "owner": {"login": repo.get("owner", {}).get("login", "$OWNER")}
    }
    
    json.dump(result, sys.stdout)
except:
    # Fallback if parsing fails
    result = {
        "name": "$REPO",
        "description": "",
        "html_url": "https://github.com/$repo_path",
        "language": {"name": ""},
        "stargazers": {"totalCount": 0},
        "owner": {"login": "$OWNER"}
    }
    json.dump(result, sys.stdout)
PYEOF
    else
        echo "    (Warning: Could not fetch $repo_path)"
    fi
done

echo ']' >> "$OUTPUT_DIR/github-pinned.json"

# Fetch recent events to find contributed repos
echo "Fetching contribution events..."
curl -s $AUTH_HEADER "https://api.github.com/users/$USERNAME/events/public?per_page=100" > "$OUTPUT_DIR/github-events.json"

echo ""
echo "GitHub data fetched successfully!"
echo ""
echo "Files created:"
echo "  - $OUTPUT_DIR/github-profile.json"
echo "  - $OUTPUT_DIR/github-repos.json"
echo "  - $OUTPUT_DIR/github-pinned.json"
echo "  - $OUTPUT_DIR/github-events.json"
