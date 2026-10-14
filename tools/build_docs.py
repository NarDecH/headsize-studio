"""Build the HTML documentation from the Markdown sources in ``docs/``.

Run:  python tools/build_docs.py [--check]

Produces ``docs/readme.html``, ``docs/research.html``, ``docs/changelog.html``
and ``docs/index.html`` — self-contained files (the only external references are
the images next to them), readable on a light or dark browser theme.

``--check`` verifies the generated files and exits non-zero on problems, which is
what CI runs.
"""

from __future__ import annotations

import argparse
import html as html_module
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"

PAGES = (
    ("readme.md", "readme.html", "Overview", "What HeadSize Studio is and how to use it"),
    ("research.md", "research.html", "Research", "Design decisions, maths and measurements"),
    ("changelog.md", "changelog.html", "Changelog", "What changed in every version"),
)

REPO_SLUG = "NarDecH/headsize-studio"


def repo_slug() -> str:
    """Owner/repo from the config baked into headsize/update/repo.py."""
    sys.path.insert(0, str(ROOT))
    try:
        from headsize.update.repo import DEFAULT_OWNER, DEFAULT_REPO

        return f"{DEFAULT_OWNER}/{DEFAULT_REPO}"
    except Exception:
        return REPO_SLUG


CSS = """
:root {
  --bg: #f5f7fc;
  --surface: #ffffff;
  --surface-alt: #f0f3fb;
  --border: #dde3f0;
  --text: #16203a;
  --muted: #5a6784;
  --accent: #4059e8;
  --accent-soft: #e8ecff;
  --code-bg: #eef1f9;
  --shadow: 0 10px 30px rgba(24, 39, 75, .08);
}
@media (prefers-color-scheme: dark) {
  :root {
    --bg: #0d1017;
    --surface: #151a24;
    --surface-alt: #1a2130;
    --border: #262f41;
    --text: #e8edfa;
    --muted: #98a4bf;
    --accent: #7d97ff;
    --accent-soft: #1e2540;
    --code-bg: #111725;
    --shadow: 0 12px 34px rgba(0, 0, 0, .45);
  }
}
* { box-sizing: border-box; }
html { scroll-behavior: smooth; }
body {
  margin: 0;
  background: var(--bg);
  color: var(--text);
  font: 16px/1.7 "Segoe UI Variable Text", "Segoe UI", "Leelawadee UI", "Noto Sans Thai", system-ui, -apple-system, sans-serif;
  -webkit-font-smoothing: antialiased;
}
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }
.layout { display: grid; grid-template-columns: 280px minmax(0, 1fr); gap: 0; max-width: 1400px; margin: 0 auto; }
.sidebar {
  position: sticky; top: 0; align-self: start; height: 100vh; overflow-y: auto;
  padding: 28px 22px; border-right: 1px solid var(--border); background: var(--surface);
}
.brand { display: flex; align-items: center; gap: 12px; margin-bottom: 6px; }
.brand img { width: 38px; height: 38px; }
.brand strong { font-size: 17px; letter-spacing: .2px; }
.brand span { display: block; font-size: 12px; color: var(--muted); font-weight: 400; }
.badge {
  display: inline-block; margin: 14px 6px 18px 0; padding: 3px 10px; border-radius: 999px;
  background: var(--accent-soft); color: var(--accent); font-size: 12px; font-weight: 600;
}
.nav { display: flex; flex-direction: column; gap: 4px; margin-bottom: 22px; }
.nav a { padding: 7px 11px; border-radius: 9px; color: var(--muted); font-weight: 500; font-size: 14.5px; }
.nav a:hover { background: var(--surface-alt); text-decoration: none; color: var(--text); }
.nav a.active { background: var(--accent-soft); color: var(--accent); }
.toc-title { font-size: 11.5px; text-transform: uppercase; letter-spacing: .09em; color: var(--muted); margin: 0 0 8px 4px; }
.toc ul { list-style: none; margin: 0; padding: 0; }
.toc ul ul { padding-left: 14px; }
.toc li { margin: 2px 0; }
.toc a { color: var(--muted); font-size: 14px; }
.toc a:hover { color: var(--accent); }
main { padding: 40px 48px 96px; min-width: 0; }
article { max-width: 900px; }
h1 { font-size: 34px; line-height: 1.25; margin: 0 0 6px; letter-spacing: -.01em; }
h2 { font-size: 24px; margin: 52px 0 14px; padding-top: 8px; border-top: 1px solid var(--border); }
h3 { font-size: 19px; margin: 34px 0 10px; }
h4 { font-size: 16px; margin: 24px 0 8px; }
p { margin: 12px 0; }
hr { border: none; border-top: 1px solid var(--border); margin: 40px 0; }
strong { font-weight: 650; }
figure { margin: 26px 0; }
figure img, article > p > img {
  max-width: 100%; height: auto; border-radius: 12px; border: 1px solid var(--border);
  box-shadow: var(--shadow); display: block;
}
article > p > img { margin: 22px 0; }
figcaption { color: var(--muted); font-size: 14px; margin-top: 10px; text-align: center; }
table { border-collapse: collapse; width: 100%; margin: 20px 0; font-size: 14.5px; display: block; overflow-x: auto; }
th, td { border: 1px solid var(--border); padding: 9px 12px; text-align: left; vertical-align: top; }
th { background: var(--surface-alt); font-weight: 600; }
article tbody tr:nth-child(even) td { background: var(--surface-alt); }
code { background: var(--code-bg); padding: 2px 6px; border-radius: 6px; font-size: 13.5px;
  font-family: "Cascadia Code", "JetBrains Mono", Consolas, monospace; }
pre { background: var(--surface); border: 1px solid var(--border); border-radius: 12px; padding: 16px 18px; overflow-x: auto; box-shadow: var(--shadow); }
pre code { background: none; padding: 0; font-size: 13.5px; line-height: 1.6; }
blockquote {
  margin: 20px 0; padding: 14px 18px; border-left: 4px solid var(--accent);
  background: var(--surface); border-radius: 0 10px 10px 0; color: var(--muted);
}
ul, ol { padding-left: 24px; }
li { margin: 5px 0; }
.footer { margin-top: 70px; padding-top: 22px; border-top: 1px solid var(--border); color: var(--muted); font-size: 13.5px; }
.footer a { color: var(--accent); }
@media (max-width: 900px) {
  .layout { grid-template-columns: 1fr; }
  .sidebar { position: static; height: auto; border-right: none; border-bottom: 1px solid var(--border); }
  main { padding: 26px 20px 70px; }
}
@media print {
  .sidebar { display: none; }
  .layout { grid-template-columns: 1fr; }
  body { background: #fff; color: #000; }
  a { color: #000; text-decoration: underline; }
}
"""

PAGE_TEMPLATE = """<!DOCTYPE html>
<html lang="th">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} · HeadSize Studio</title>
<meta name="description" content="{description}">
<link rel="icon" href="assets/icon.png" type="image/png">
<style>{css}</style>
</head>
<body>
<div class="layout">
  <aside class="sidebar">
    <div class="brand">
      <img src="assets/icon.png" alt="HeadSize Studio logo">
      <strong>HeadSize Studio<span>resize a head, keep the photo</span></strong>
    </div>
    <span class="badge">v{version}</span>
    <nav class="nav">
{nav}
    </nav>
    <p class="toc-title">On this page</p>
    <div class="toc">
{toc}
    </div>
  </aside>
  <main>
    <article>
{content}
    </article>
    <div class="footer">
      <p>HeadSize Studio {version} · MIT licence · built {built} ·
      <a href="https://github.com/{slug}">source on GitHub</a> ·
      <a href="https://github.com/{slug}/releases">releases</a> ·
      <a href="https://github.com/{slug}/issues">issues</a></p>
      <p>This page was generated from <code>{source}</code> by <code>tools/build_docs.py</code>.</p>
    </div>
  </main>
</div>
</body>
</html>
"""


def read_version() -> str:
    sys.path.insert(0, str(ROOT))
    from headsize.version import __version__

    return __version__


def render_markdown(text: str) -> tuple[str, str]:
    """Return ``(html, toc_html)`` for one Markdown document."""
    import markdown

    md = markdown.Markdown(
        extensions=["extra", "sane_lists", "toc", "attr_list", "admonition"],
        extension_configs={"toc": {"toc_depth": "2-3"}},
        output_format="html5",
    )
    body = md.convert(text)
    toc = md.toc
    return body, toc


def polish_html(html: str) -> str:
    """Wrap images in figures and keep the markup tidy."""
    # image + italic caption -> figure
    html = re.sub(
        r"<p>\s*(<img[^>]*>)\s*</p>\s*<p>\s*<em>(.*?)</em>\s*</p>",
        lambda m: f"<figure>{m.group(1)}<figcaption>{m.group(2)}</figcaption></figure>",
        html,
        flags=re.DOTALL,
    )
    # bare image -> figure
    html = re.sub(
        r"<p>\s*(<img[^>]*>)\s*</p>",
        lambda m: f"<figure>{m.group(1)}</figure>",
        html,
        flags=re.DOTALL,
    )
    return html


def rewrite_links(html: str, slug: str) -> str:
    """Point repository-relative links at something that resolves from docs/."""
    html = html.replace('href="../../releases"', f'href="https://github.com/{slug}/releases"')
    html = html.replace('href="../../issues"', f'href="https://github.com/{slug}/issues"')
    html = html.replace('href="../../"', f'href="https://github.com/{slug}"')

    def fix(match: re.Match) -> str:
        href = match.group(1)
        if href.startswith(("http://", "https://", "#", "mailto:", "data:")):
            return match.group(0)
        path_part, _, anchor = href.partition("#")
        if href.startswith("../"):
            # Files outside docs/ live on GitHub in the rendered version.
            return f'href="https://github.com/{slug}/blob/main/{href[3:]}"'
        if path_part.endswith(".md"):
            new_href = path_part[:-3] + ".html" + (f"#{anchor}" if anchor else "")
            return f'href="{new_href}"'
        return match.group(0)

    return re.sub(r'href="([^"]+)"', fix, html)


def build_page(
    source: Path,
    destination: Path,
    title: str,
    description: str,
    nav_html: str,
    version: str,
    slug: str,
) -> None:
    text = source.read_text(encoding="utf-8")
    body, toc = render_markdown(text)
    body = polish_html(body)
    body = rewrite_links(body, slug)
    import datetime

    page = PAGE_TEMPLATE.format(
        title=title,
        description=html_module.escape(description),
        css=CSS,
        version=version,
        nav=nav_html,
        toc=toc,
        content=body,
        slug=slug,
        source=source.name,
        built=datetime.date.today().isoformat(),
    )
    destination.write_text(page, encoding="utf-8")


def nav_for(active: str, slug: str = REPO_SLUG) -> str:
    items = []
    for _source, target, label, _description in PAGES:
        css = ' class="active"' if target == active else ""
        items.append(f'      <a href="{target}"{css}>{label}</a>')
    items.append(f'      <a href="https://github.com/{slug}">GitHub</a>')
    return "\n".join(items)


def check() -> list[str]:
    problems: list[str] = []
    for _source, target, _label, _description in PAGES + (("", "index.html", "", ""),):
        path = DOCS / target
        if not path.is_file():
            problems.append(f"missing {path.name}")
            continue
        text = path.read_text(encoding="utf-8")
        if len(text) < 2000:
            problems.append(f"{path.name} looks too small ({len(text)} bytes)")
        for match in re.finditer(r'(?:src|href)="([^"#][^"]*)"', text):
            target_link = match.group(1)
            if target_link.startswith(("http", "mailto:", "data:")):
                continue
            resolved = (path.parent / target_link.split("#")[0]).resolve()
            if not resolved.exists():
                problems.append(f"{path.name}: broken link -> {target_link}")
        if path.name != "index.html" and "unsubstituted" in text:
            problems.append(f"{path.name}: leftover template text")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="verify the built files")
    args = parser.parse_args(argv)

    version = read_version()
    slug = repo_slug()

    for source_name, target_name, label, description in PAGES:
        source = DOCS / source_name
        if not source.is_file():
            print(f"skip {source_name} (not found)", file=sys.stderr)
            continue
        build_page(
            source,
            DOCS / target_name,
            label,
            description,
            nav_for(target_name, slug),
            version,
            slug,
        )
        print(f"built docs/{target_name}")

    # index.html mirrors the overview page
    index = (DOCS / "index.html")
    index.write_text((DOCS / "readme.html").read_text(encoding="utf-8"), encoding="utf-8")
    print("built docs/index.html")

    if args.check:
        problems = check()
        for problem in problems:
            print(f"  problem: {problem}", file=sys.stderr)
        return 1 if problems else 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
