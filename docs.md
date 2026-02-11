# gabrielkoerich.com

Personal website of Gabriel Koerich - Senior Software Engineer | Rust • Solana • PHP • Laravel

**Live:** https://gabrielkoerich.com

## Development

Built with [Zola](https://www.getzola.org/) - a fast static site generator written in Rust.

```bash
# Serve locally
just serve

# Create new post
just new-post "My Post Title"

# Deploy (auto on push to main)
just deploy
```

## Structure

```
.
├── config.toml          # Site configuration
├── content/             # Markdown content
│   ├── _index.md        # Homepage
│   ├── cv.md            # CV page
│   └── posts/           # Blog posts
├── templates/           # HTML templates
├── sass/               # Stylesheets (dark theme)
└── static/             # Static assets
```

## Deployment

Auto-deploys to GitHub Pages on push to `main` branch.
