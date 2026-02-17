# Default recipe - show available commands
default:
    @just --list

# Fetch GitHub profile and repository data (dynamically fetches pinned repos)
[group('github')]
fetch-github:
    python3 scripts/fetch-github.py

# Fetch GitHub data with token (for higher API limits)
[group('github')]
fetch-github-auth TOKEN:
    python3 scripts/fetch-github.py {{ TOKEN }}

# Fetch blog posts from Medium and wtf.gabrielkoerich.com
[group('posts')]
fetch-posts:
    uv run python scripts/fetch-blog-posts.py --output content/posts/external

# Fetch only Medium posts
[group('posts')]
fetch-posts-medium:
    uv run python scripts/fetch-blog-posts.py --medium-only --output content/posts/external

# Translate external posts to English using Google Translate (translate-shell).
# Overwrites posts in place (English-only).

# OpenAI is available as optional fallback via --provider openai.
[group('posts')]
translate-posts-en:
    uv run python scripts/translate-blog-posts.py \
      --input-dir content/posts/external \
      --source-lang pt \
      --target-lang en \
      --provider command \
      --translator-cmd "trans -b -s {source_lang} -t {target_lang}"

# Create a new blog post
[group('posts')]
new-post:
    #!/usr/bin/env bash
    set -euo pipefail

    printf "Post title: "
    IFS= read -r TITLE_INPUT
    if [ -z "$TITLE_INPUT" ]; then
      echo "Title cannot be empty" >&2
      exit 1
    fi

    echo "Post body (finish with Ctrl-D):"
    BODY_INPUT=$(cat)

    DATE=$(date +%Y-%m-%d)
    TITLE_TOML=$(printf '%s' "$TITLE_INPUT" | sed 's/\\/\\\\/g; s/"/\\"/g')
    SLUG=$(printf '%s' "$TITLE_INPUT" | tr '[:upper:]' '[:lower:]' | sed -E 's/[^a-z0-9]+/-/g; s/^-+|-+$//g')
    if [ -z "$SLUG" ]; then
      echo "Could not generate a valid slug from title" >&2
      exit 1
    fi

    mkdir -p content/posts
    FILE="content/posts/${DATE}-${SLUG}.md"
    if [ -e "$FILE" ]; then
      echo "File already exists: $FILE" >&2
      exit 1
    fi

    cat > "$FILE" << EOF
    +++
    title = "$TITLE_TOML"
    date = ${DATE}
    [taxonomies]
    tags = []
    +++

    ${BODY_INPUT}

    EOF
    echo "Created $FILE"

# Build the site locally (with GitHub data and blog posts)
[group('website')]
build: fetch-github fetch-posts-medium
    zola build && zola check

# Serve the site locally for development
[group('website')]
serve *args:
    zola serve {{ args }}

# Clean build artifacts
[group('website')]
clean:
    rm -rf public

[group('cv')]
md-to-pdf from_md to_pdf:
    pandoc {{ from_md }} -o {{ to_pdf }} \
      --from markdown+hard_line_breaks \
      --pdf-engine=xelatex \
      -V geometry:top=1.25in \
      -V geometry:bottom=0.75in

_build-pdf-cv:
    { echo "# Gabriel Koerich | Software Engineer"; tail -n +5 content/cv.md | sed '/^## Notable Projects/,$d' | sed 's/ <a [^>]*class="no-print"[^>]*>[^<]*<\/a>//g'; } > /tmp/cv-temp.md
    just md-to-pdf /tmp/cv-temp.md static/gabrielkoerich-cv.pdf

_build-pdf-summarized-cv:
    { echo "# Gabriel Koerich | Software Engineer"; tail -n +5 content/cv-summary.md | sed 's/ <a [^>]*class="no-print"[^>]*>[^<]*<\/a>//g'; } > /tmp/cv-temp.md
    just md-to-pdf /tmp/cv-temp.md static/gabrielkoerich-cv-summary.pdf

# Build CV PDF from content/cv.md
[group('cv')]
build-cv: _build-pdf-cv _build-pdf-summarized-cv
