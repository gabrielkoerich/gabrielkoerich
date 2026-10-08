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

# The version CI deploys with. Newer zola dropped the `concat` filter the templates use, so
# a local build on whatever Homebrew installed fails while the deploy is fine. Keep in step
# with .github/workflows/build-and-deploy.yml.
zola_version := "0.18.0"

# A pinned zola under .tools, fetched once. `just zola-which` says what is being used.
[group('website')]
_zola:
    #!/usr/bin/env bash
    set -euo pipefail
    bin=".tools/zola-{{ zola_version }}"
    [ -x "$bin" ] && exit 0
    mkdir -p .tools
    case "$(uname -s)-$(uname -m)" in
        Darwin-*)  asset="zola-v{{ zola_version }}-x86_64-apple-darwin.tar.gz" ;;
        Linux-*)   asset="zola-v{{ zola_version }}-x86_64-unknown-linux-gnu.tar.gz" ;;
        *) echo "no pinned zola for this platform, falling back to PATH"; exit 0 ;;
    esac
    echo "fetching zola {{ zola_version }}"
    curl -sSfL "https://github.com/getzola/zola/releases/download/v{{ zola_version }}/$asset" \
        | tar -xzf - -C .tools zola
    mv .tools/zola "$bin"
    chmod +x "$bin"

# Which zola a build will use, and whether it matches CI
[group('website')]
zola-which: _zola
    #!/usr/bin/env bash
    bin=".tools/zola-{{ zola_version }}"
    if [ -x "$bin" ]; then echo "pinned: $($bin --version)"; else echo "PATH: $(zola --version)"; fi

# Build the site locally (with GitHub data and blog posts)
[group('website')]
build: fetch-github _zola
    #!/usr/bin/env bash
    set -euo pipefail
    bin=".tools/zola-{{ zola_version }}"
    [ -x "$bin" ] || bin="zola"
    "$bin" build && "$bin" check

# Serve the site locally for development, unpublished posts included
[group('website')]
serve *args: _zola
    #!/usr/bin/env bash
    bin=".tools/zola-{{ zola_version }}"
    [ -x "$bin" ] || bin="zola"
    "$bin" serve {{ args }}

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
