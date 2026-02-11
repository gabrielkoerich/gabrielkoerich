#!/usr/bin/env python3
"""
Fetch blog posts from Medium and wtf.gabrielkoerich.com
Generates markdown files for gabrielkoerich.com site
"""

import requests
import feedparser
import re
from datetime import datetime
from pathlib import Path
import html
import sys
import hashlib
import urllib.parse


def slugify(text):
    """Convert text to URL-friendly slug"""
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[-\s]+", "-", text)
    return text.strip("-")


def download_image(url, output_dir, post_slug):
    """Download an image and save it locally"""
    try:
        # Skip tracking pixels and data URLs
        if "medium.com/_/stat" in url or url.startswith("data:"):
            return None

        response = requests.get(url, timeout=30)
        if response.status_code == 200:
            # Generate filename from URL
            parsed = urllib.parse.urlparse(url)
            filename = Path(parsed.path).name
            if not filename or "." not in filename:
                # Generate hash-based filename
                ext = ".jpg"  # default
                if "png" in url.lower():
                    ext = ".png"
                elif "gif" in url.lower():
                    ext = ".gif"
                filename = f"{hashlib.md5(url.encode()).hexdigest()[:8]}{ext}"

            # Add post slug prefix to avoid conflicts
            filename = f"{post_slug}_{filename}"
            filepath = output_dir / filename

            filepath.write_bytes(response.content)
            print(f"    Downloaded image: {filename}")
            return f"/images/posts/{filename}"
    except Exception as e:
        print(f"    Failed to download image {url}: {e}")
    return None


def clean_html(html_content, post_slug, images_dir):
    """Convert HTML to markdown with proper code block and image handling"""

    # Remove script and style tags
    html_content = re.sub(
        r"<script[^>]*>.*?</script>", "", html_content, flags=re.DOTALL
    )
    html_content = re.sub(r"<style[^>]*>.*?</style>", "", html_content, flags=re.DOTALL)

    # Track images to download
    images_to_download = []

    def extract_image(match):
        full_tag = match.group(0)
        src_match = re.search(r'src="([^"]+)"', full_tag)
        alt_match = re.search(r'alt="([^"]*)"', full_tag)

        if src_match:
            src = src_match.group(1)
            alt = alt_match.group(1) if alt_match else ""

            # Queue for download
            images_to_download.append((src, alt))

            # Return placeholder that will be replaced after download
            return f"___IMAGE_{len(images_to_download) - 1}___"

        return ""

    # Extract images first
    html_content = re.sub(r"<img[^>]*>", extract_image, html_content, flags=re.DOTALL)

    # Step 1: Extract code blocks
    code_blocks = []
    CODE_BLOCK_DELIMITER = "\n___CODE_BLOCK_{idx}___\n"

    def extract_code_block(match):
        full_html = match.group(0)

        # Try to extract from <code> inside first
        code_match = re.search(r"<code[^>]*>(.*?)</code>", full_html, re.DOTALL)
        if code_match:
            code = code_match.group(1)
        else:
            # Try <pre> content
            pre_match = re.search(r"<pre[^>]*>(.*?)</pre>", full_html, re.DOTALL)
            if pre_match:
                code = pre_match.group(1)
            else:
                code = full_html

        # Clean the code
        code = html.unescape(code)
        code = re.sub(r"<br\s*/?>", "\n", code)
        code = re.sub(r"&nbsp;", " ", code)
        code = re.sub(r"</?[^>]+>", "", code)

        idx = len(code_blocks)
        code_blocks.append(code.strip())
        return CODE_BLOCK_DELIMITER.format(idx=idx)

    # Extract code blocks
    # Pattern 1: <figure><pre><code>...</code></pre></figure>
    html_content = re.sub(
        r"<figure[^>]*>\s*<pre[^>]*>\s*<code[^>]*>.*?</code>\s*</pre>\s*</figure>",
        extract_code_block,
        html_content,
        flags=re.DOTALL,
    )

    # Pattern 2: <pre><code>...</code></pre>
    html_content = re.sub(
        r"<pre[^>]*>\s*<code[^>]*>.*?</code>\s*</pre>",
        extract_code_block,
        html_content,
        flags=re.DOTALL,
    )

    # Pattern 3: <pre>...</pre>
    html_content = re.sub(
        r"<pre[^>]*>(.*?)</pre>", extract_code_block, html_content, flags=re.DOTALL
    )

    # Convert headings
    html_content = re.sub(
        r"<h1[^>]*>(.*?)</h1>", r"# \1\n\n", html_content, flags=re.DOTALL
    )
    html_content = re.sub(
        r"<h2[^>]*>(.*?)</h2>", r"## \1\n\n", html_content, flags=re.DOTALL
    )
    html_content = re.sub(
        r"<h3[^>]*>(.*?)</h3>", r"### \1\n\n", html_content, flags=re.DOTALL
    )
    html_content = re.sub(
        r"<h4[^>]*>(.*?)</h4>", r"#### \1\n\n", html_content, flags=re.DOTALL
    )
    html_content = re.sub(
        r"<h5[^>]*>(.*?)</h5>", r"##### \1\n\n", html_content, flags=re.DOTALL
    )
    html_content = re.sub(
        r"<h6[^>]*>(.*?)</h6>", r"###### \1\n\n", html_content, flags=re.DOTALL
    )

    # Convert paragraphs
    def convert_paragraph(match):
        content = match.group(1)
        content = re.sub(r"<br\s*/?>", "\n", content)
        content = html.unescape(content)
        content = re.sub(r"<[^>]+>", "", content)
        return content.strip() + "\n\n"

    html_content = re.sub(
        r"<p[^>]*>(.*?)</p>", convert_paragraph, html_content, flags=re.DOTALL
    )

    # Convert formatting
    html_content = re.sub(
        r"<strong[^>]*>(.*?)</strong>", r"**\1**", html_content, flags=re.DOTALL
    )
    html_content = re.sub(
        r"<b[^>]*>(.*?)</b>", r"**\1**", html_content, flags=re.DOTALL
    )
    html_content = re.sub(
        r"<em[^>]*>(.*?)</em>", r"*\1*", html_content, flags=re.DOTALL
    )
    html_content = re.sub(r"<i[^>]*>(.*?)</i>", r"*\1*", html_content, flags=re.DOTALL)

    # Handle inline code (not in code blocks)
    html_content = re.sub(
        r"<code[^>]*>(.*?)</code>",
        lambda m: f"`{html.unescape(m.group(1))}`",
        html_content,
    )

    # Convert links
    def replace_link(match):
        href = match.group(1)
        text = match.group(2)
        text = re.sub(r"<[^>]+>", "", text)
        text = html.unescape(text)
        return f"[{text}]({href})"

    html_content = re.sub(
        r'<a[^>]*href="([^"]*)"[^>]*>(.*?)</a>',
        replace_link,
        html_content,
        flags=re.DOTALL,
    )

    # Convert lists
    def convert_li(match):
        content = match.group(1)
        content = re.sub(r"<[^>]+>", "", content)
        content = html.unescape(content)
        return f"- {content.strip()}\n"

    html_content = re.sub(
        r"<li[^>]*>(.*?)</li>", convert_li, html_content, flags=re.DOTALL
    )
    html_content = re.sub(
        r"<ul[^>]*>(.*?)</ul>", r"\1\n", html_content, flags=re.DOTALL
    )

    def convert_ol(match):
        content = match.group(1)
        items = re.findall(r"<li[^>]*>(.*?)</li>", content, re.DOTALL)
        result = ""
        for i, item in enumerate(items, 1):
            item = re.sub(r"<[^>]+>", "", item)
            item = html.unescape(item)
            result += f"{i}. {item.strip()}\n"
        return result + "\n"

    html_content = re.sub(
        r"<ol[^>]*>(.*?)</ol>", convert_ol, html_content, flags=re.DOTALL
    )

    # Blockquotes
    def convert_blockquote(match):
        content = match.group(1)
        content = re.sub(
            r"<blockquote[^>]*>(.*?)</blockquote>", r"\1", content, flags=re.DOTALL
        )
        content = re.sub(r"<[^>]+>", "", content)
        content = html.unescape(content)
        lines = content.strip().split("\n")
        quoted = "\n".join(f"> {line}" for line in lines if line.strip())
        return quoted + "\n\n"

    html_content = re.sub(
        r"<blockquote[^>]*>(.*?)</blockquote>",
        convert_blockquote,
        html_content,
        flags=re.DOTALL,
    )

    # Horizontal rules
    html_content = re.sub(r"<hr[^>]*/?>", "---\n\n", html_content)

    # Line breaks
    html_content = re.sub(r"<br\s*/?>", "\n", html_content)

    # Remove remaining HTML tags
    html_content = re.sub(r"<[^>]+>", "", html_content)

    # Clean up HTML entities
    html_content = html.unescape(html_content)

    # Fix excessive newlines
    html_content = re.sub(r"\n{4,}", "\n\n\n", html_content)

    # Restore code blocks
    for idx, code in enumerate(code_blocks):
        placeholder = CODE_BLOCK_DELIMITER.format(idx=idx)

        # Detect language
        lang = ""
        if code.strip().startswith("<?php"):
            lang = "php"
        elif "import " in code[:200] or "def " in code[:200]:
            lang = "python"
        elif "function " in code[:200] or "const " in code[:200]:
            lang = "javascript"
        elif "<?php" in code[:100]:
            lang = "php"

        code_block_md = f"\n```{lang}\n{code}\n```\n"
        html_content = html_content.replace(placeholder, code_block_md)

    # Download images and replace placeholders
    images_dir.mkdir(parents=True, exist_ok=True)
    for idx, (src, alt) in enumerate(images_to_download):
        placeholder = f"___IMAGE_{idx}___"
        local_path = download_image(src, images_dir, post_slug)
        if local_path:
            html_content = html_content.replace(
                placeholder, f"\n![{alt}]({local_path})\n"
            )
        else:
            html_content = html_content.replace(placeholder, "")

    return html_content.strip()


def fetch_medium_posts(username="gabrielkoerich"):
    """Fetch posts from Medium RSS feed"""
    print(f"Fetching Medium posts for @{username}...")

    urls = [
        f"https://medium.com/feed/@{username}",
        f"https://{username}.medium.com/feed",
    ]

    posts = []
    for url in urls:
        try:
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                feed = feedparser.parse(response.content)

                for entry in feed.entries:
                    published = entry.get("published_parsed")
                    if (
                        published
                        and isinstance(published, (tuple, list))
                        and len(published) >= 6
                    ):
                        try:
                            date = datetime(*published[:6])
                        except:
                            date = datetime.now()
                    else:
                        date = datetime.now()

                    # Get content
                    if entry.get("content"):
                        content = entry["content"][0].get("value", "")
                    else:
                        content = entry.get("summary", "")

                    post = {
                        "title": entry.get("title", "Untitled"),
                        "date": date,
                        "content": content,
                        "url": entry.get("link", ""),
                        "source": "medium",
                    }
                    posts.append(post)

                print(f"  ✓ Found {len(feed.entries)} posts from {url}")
                break
        except Exception as e:
            print(f"  ✗ Failed to fetch from {url}: {e}")
            continue

    return posts


def fetch_wtf_posts():
    """Fetch posts from wtf.gabrielkoerich.com"""
    print("Fetching posts from wtf.gabrielkoerich.com...")

    try:
        urls = [
            "https://wtf.gabrielkoerich.com/rss",
            "https://wtf.gabrielkoerich.com/feed.xml",
            "https://wtf.gabrielkoerich.com/feed",
            "https://wtf.gabrielkoerich.com/index.xml",
        ]

        posts = []
        for url in urls:
            try:
                response = requests.get(url, timeout=30)
                if response.status_code == 200:
                    feed = feedparser.parse(response.content)

                    for entry in feed.entries:
                        published = entry.get("published_parsed")
                        if (
                            published
                            and isinstance(published, (tuple, list))
                            and len(published) >= 6
                        ):
                            try:
                                date = datetime(*published[:6])
                            except:
                                date = datetime.now()
                        else:
                            date = datetime.now()

                        if entry.get("content"):
                            content = entry["content"][0].get("value", "")
                        else:
                            content = entry.get("summary", "")

                        post = {
                            "title": entry.get("title", "Untitled"),
                            "date": date,
                            "content": content,
                            "url": entry.get("link", ""),
                            "source": "wtf",
                        }
                        posts.append(post)

                    print(f"  ✓ Found {len(feed.entries)} posts from {url}")
                    return posts
            except:
                continue

        print("  Note: Could not fetch from wtf.gabrielkoerich.com")

    except Exception as e:
        print(f"  ✗ Failed to fetch: {e}")

    return []


def generate_markdown(posts, output_dir, images_dir):
    """Generate markdown files from posts"""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    images_path = Path(images_dir)
    images_path.mkdir(parents=True, exist_ok=True)

    print(f"\nGenerating markdown files in {output_dir}...")

    for post in posts:
        date_str = post["date"].strftime("%Y-%m-%d")
        slug = slugify(post["title"])
        filename = f"{date_str}-{slug}.md"
        filepath = output_path / filename

        # Clean HTML with image downloading
        content = clean_html(post["content"], slug, images_path)

        # Escape quotes in title for TOML
        safe_title = post["title"].replace('"', '\\"')

        markdown = f"""+++
title = "{safe_title}"
date = {post["date"].strftime("%Y-%m-%d")}
[taxonomies]
tags = ["{post["source"]}"]
[extra]
source = "{post["source"]}"
original_url = "{post["url"]}"
+++

{content}

*Originally published on [{post["source"].upper()}]({post["url"]})*
"""

        filepath.write_text(markdown, encoding="utf-8")
        print(f"  ✓ {filename}")

    print(f"\nGenerated {len(posts)} markdown files")


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Fetch blog posts and generate markdown"
    )
    parser.add_argument(
        "--output",
        "-o",
        default="./content/posts/external",
        help="Output directory for markdown files",
    )
    parser.add_argument(
        "--images",
        "-i",
        default="./static/images/posts",
        help="Output directory for images",
    )
    parser.add_argument(
        "--medium-only", action="store_true", help="Only fetch Medium posts"
    )
    parser.add_argument("--wtf-only", action="store_true", help="Only fetch wtf posts")

    args = parser.parse_args()

    all_posts = []

    if not args.wtf_only:
        medium_posts = fetch_medium_posts()
        all_posts.extend(medium_posts)

    if not args.medium_only:
        wtf_posts = fetch_wtf_posts()
        all_posts.extend(wtf_posts)

    if all_posts:
        all_posts.sort(key=lambda x: x["date"], reverse=True)
        generate_markdown(all_posts, args.output, args.images)
    else:
        print("\nNo posts found!")
        sys.exit(1)


if __name__ == "__main__":
    main()
