#!/usr/bin/env python3
"""
Translate Zola blog posts using a local command (default: translate-shell/Google Translate)
or OpenAI API as optional fallback.

Default behavior:
- Reads unsuffixed markdown files from content/posts/external
- Translates title + body from pt -> en
- Keeps Portuguese as <slug>.pt.md
- Writes English as default file <slug>.md
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
from pathlib import Path
import tomllib
import requests


FRONT_MATTER_DELIM = "+++"
TITLE_RE = re.compile(r'(?m)^title\s*=\s*"((?:[^"\\]|\\.)*)"\s*$')


def split_front_matter(text: str) -> tuple[str, str]:
    if not text.startswith(FRONT_MATTER_DELIM):
        raise ValueError("Missing TOML front matter delimiters (+++)")

    parts = text.split(FRONT_MATTER_DELIM, 2)
    if len(parts) < 3:
        raise ValueError("Invalid front matter format")

    front_matter = parts[1].strip("\n")
    body = parts[2].lstrip("\n")
    return front_matter, body


def escape_toml_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def read_title(front_matter: str) -> str:
    match = TITLE_RE.search(front_matter)
    if not match:
        raise ValueError("title field not found in front matter")
    parsed = tomllib.loads(match.group(0))
    return str(parsed["title"])


def replace_title(front_matter: str, new_title: str) -> str:
    escaped = escape_toml_string(new_title)
    return TITLE_RE.sub(lambda _match: f'title = "{escaped}"', front_matter, count=1)


def run_command_translator(command_template: str, source_lang: str, target_lang: str, text: str) -> str:
    command = command_template.format(source_lang=source_lang, target_lang=target_lang)
    args = shlex.split(command)

    proc = subprocess.run(
        args,
        input=text,
        text=True,
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"translator command failed ({proc.returncode}): {proc.stderr.strip() or proc.stdout.strip()}"
        )

    output = proc.stdout.strip()
    if not output:
        raise RuntimeError("translator command returned empty output")
    return output


def parse_openai_text(payload: dict) -> str:
    output_text = payload.get("output_text")
    if isinstance(output_text, str) and output_text.strip():
        return output_text.strip()

    output = payload.get("output", [])
    for item in output:
        for content in item.get("content", []):
            text = content.get("text")
            if isinstance(text, str) and text.strip():
                return text.strip()
    raise RuntimeError("OpenAI response did not include output text")


def run_openai_translator(
    *,
    source_lang: str,
    target_lang: str,
    text: str,
    model: str,
    api_key: str,
) -> str:
    instructions = (
        f"Translate the user text from {source_lang} to {target_lang}. "
        "Preserve meaning, tone, and markdown formatting exactly. "
        "Return only the translated text."
    )

    response = requests.post(
        "https://api.openai.com/v1/responses",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        data=json.dumps(
            {
                "model": model,
                "input": [
                    {"role": "system", "content": [{"type": "input_text", "text": instructions}]},
                    {"role": "user", "content": [{"type": "input_text", "text": text}]},
                ],
            }
        ),
        timeout=120,
    )

    if response.status_code >= 300:
        raise RuntimeError(f"OpenAI API error {response.status_code}: {response.text[:500]}")

    payload = response.json()
    return parse_openai_text(payload)


def candidate_files(input_dir: Path) -> list[Path]:
    files: list[Path] = []
    for path in sorted(input_dir.glob("*.md")):
        if path.name.startswith("_index"):
            continue
        if re.search(r"\.[a-z]{2}\.md$", path.name):
            continue
        files.append(path)
    return files


def target_paths(path: Path, source_lang: str, target_lang: str, make_target_default: bool) -> tuple[Path, Path]:
    stem = path.stem
    parent = path.parent

    if make_target_default:
        source_path = parent / f"{stem}.{source_lang}.md"
        target_path = path
    else:
        source_path = path
        target_path = parent / f"{stem}.{target_lang}.md"

    return source_path, target_path


def process_file(
    path: Path,
    source_lang: str,
    target_lang: str,
    translate_fn,
    make_target_default: bool,
    overwrite: bool,
    dry_run: bool,
) -> None:
    raw = path.read_text(encoding="utf-8")
    front_matter, body = split_front_matter(raw)

    source_title = read_title(front_matter)
    translated_title = translate_fn(source_lang, target_lang, source_title)
    translated_body = translate_fn(source_lang, target_lang, body)

    translated_front_matter = replace_title(front_matter, translated_title)
    translated_raw = f"{FRONT_MATTER_DELIM}\n{translated_front_matter}\n{FRONT_MATTER_DELIM}\n\n{translated_body.rstrip()}\n"

    source_path, target_path = target_paths(path, source_lang, target_lang, make_target_default)

    if target_path.exists() and not overwrite and target_path.resolve() != path.resolve():
        raise FileExistsError(f"target file exists: {target_path}")

    print(f"Translating: {path}")
    print(f"  source title: {source_title}")
    print(f"  target title: {translated_title}")
    print(f"  write target: {target_path}")

    if dry_run:
        return

    if make_target_default and path.resolve() == target_path.resolve():
        if source_path.exists() and target_path.exists() and not overwrite:
            print(f"  skip: already migrated ({source_path.name} exists)")
            return
        if source_path.exists() and not overwrite:
            raise FileExistsError(f"source language file already exists: {source_path}")
        path.rename(source_path)
        target_path.write_text(translated_raw, encoding="utf-8")
    else:
        target_path.write_text(translated_raw, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Translate Zola blog posts")
    parser.add_argument("--input-dir", default="content/posts/external", help="Directory containing post markdown files")
    parser.add_argument("--source-lang", default="pt", help="Source language code")
    parser.add_argument("--target-lang", default="en", help="Target language code")
    parser.add_argument(
        "--provider",
        choices=["openai", "command"],
        default="command",
        help="Translation provider",
    )
    parser.add_argument(
        "--translator-cmd",
        default="trans -b -s {source_lang} -t {target_lang}",
        help="Command template. Reads text from stdin and writes translated text to stdout",
    )
    parser.add_argument("--openai-model", default="gpt-4.1-mini", help="OpenAI model for translation")
    parser.add_argument(
        "--make-target-default",
        action="store_true",
        help="Move unsuffixed source file to .<source-lang>.md and write translation to unsuffixed .md",
    )
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing output files")
    parser.add_argument("--dry-run", action="store_true", help="Preview operations without writing files")
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    if not input_dir.exists():
        print(f"Input directory not found: {input_dir}", file=sys.stderr)
        return 1

    files = candidate_files(input_dir)
    if not files:
        print(f"No candidate files in {input_dir}")
        return 0

    if args.provider == "openai":
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key:
            print("OPENAI_API_KEY is required when --provider openai", file=sys.stderr)
            return 1

        def translate_fn(src: str, dst: str, text: str) -> str:
            return run_openai_translator(
                source_lang=src,
                target_lang=dst,
                text=text,
                model=args.openai_model,
                api_key=api_key,
            )
    else:
        def translate_fn(src: str, dst: str, text: str) -> str:
            return run_command_translator(args.translator_cmd, src, dst, text)

    for path in files:
        try:
            process_file(
                path=path,
                source_lang=args.source_lang,
                target_lang=args.target_lang,
                translate_fn=translate_fn,
                make_target_default=args.make_target_default,
                overwrite=args.overwrite,
                dry_run=args.dry_run,
            )
        except Exception as exc:
            print(f"Error processing {path}: {exc}", file=sys.stderr)
            return 1

    print(f"Done. Processed {len(files)} files.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
