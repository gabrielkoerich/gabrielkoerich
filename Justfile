# Default recipe - show available commands
default:
    @just --list

# Fetch GitHub profile and repository data (dynamically fetches pinned repos)
fetch-github:
    python3 scripts/fetch-github.py

# Fetch GitHub data with token (for higher API limits)
fetch-github-auth TOKEN:
    python3 scripts/fetch-github.py {{ TOKEN }}

# Fetch blog posts from Medium and wtf.gabrielkoerich.com
fetch-posts:
    uv run python scripts/fetch-blog-posts.py --output content/posts/external

# Fetch only Medium posts
fetch-posts-medium:
    uv run python scripts/fetch-blog-posts.py --medium-only --output content/posts/external

# Translate external posts to English using Google Translate (translate-shell).
# Overwrites posts in place (English-only).
# OpenAI is available as optional fallback via --provider openai.
translate-posts-en:
    uv run python scripts/translate-blog-posts.py \
      --input-dir content/posts/external \
      --source-lang pt \
      --target-lang en \
      --provider command \
      --translator-cmd "trans -b -s {source_lang} -t {target_lang}"

# Build the site locally (with GitHub data and blog posts)
build: fetch-github fetch-posts-medium
    zola build

# Build without fetching GitHub data (faster)
build-fast:
    zola build

# Direct Zola build (no fetch steps)
zola-build:
    zola build

# Serve the site locally for development
serve:
    zola serve

# Direct Zola watch/serve
zola-serve:
    zola serve

# Serve on specific port
serve-port PORT="1111":
    zola serve --port {{ PORT }}

# Clean build artifacts
clean:
    rm -rf public

# Build for production (GitHub Pages)
build-prod:
    zola build --base-url https://gabrielkoerich.com

# Deploy to GitHub Pages (requires gh CLI)
deploy:
    just build-prod
    git add .
    git commit -m "Update site"
    git push origin main

# Create a new blog post
new-post TITLE:
    #!/usr/bin/env bash
    DATE=$(date +%Y-%m-%d)
    SLUG=$(echo "{{ TITLE }}" | tr '[:upper:]' '[:lower:]' | tr ' ' '-')
    mkdir -p content/posts
    cat > "content/posts/${DATE}-${SLUG}.md" << EOF
    +++
    title = "{{ TITLE }}"
    date = ${DATE}
    [taxonomies]
    tags = []
    +++

    EOF
    echo "Created content/posts/${DATE}-${SLUG}.md"

# Check for broken links
check-links:
    zola check

# Update Zola to latest version
update-zola:
    brew upgrade zola

# Preview production build locally
preview:
    just build-prod
    cd public && python3 -m http.server 8000

md-to-pdf file:
    pandoc {{ file }}.md -o {{ file }}.pdf

# Build CV PDF from content/cv.md
build-cv:
    { echo "# Gabriel Koerich | Software Engineer"; tail -n +5 content/cv.md | sed '/^## Notable Projects/,$d' | sed 's/ <a [^>]*class="no-print"[^>]*>[^<]*<\/a>//g'; } > /tmp/cv-temp.md
    pandoc /tmp/cv-temp.md -o static/gabrielkoerich-cv.pdf \
      --from markdown+hard_line_breaks \
      --pdf-engine=xelatex \
      -V geometry:top=1.25in \
      -V geometry:bottom=0.75in
