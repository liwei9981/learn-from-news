from __future__ import annotations

from html import escape
from pathlib import Path
from re import sub

from app.models import NotebookPackage


def create_infographic_html(package: NotebookPackage, output_dir: str = ".local/artifacts") -> Path:
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    slug = _slugify(package.primary_article.title)[:60] or "learning-pack"
    path = Path(output_dir) / f"{slug}.html"
    blocks = _infographic_blocks(package)
    block_html = "\n".join(
        f"""
        <section class="block">
          <div class="num">{idx}</div>
          <h2>{escape(title)}</h2>
          <p>{escape(body)}</p>
        </section>
        """
        for idx, (title, body) in enumerate(blocks, start=1)
    )
    path.write_text(
        f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(package.title)}</title>
  <style>
    body {{
      margin: 0;
      font-family: Inter, Arial, sans-serif;
      color: #16202a;
      background: #f4f6f8;
    }}
    main {{
      max-width: 980px;
      margin: 0 auto;
      padding: 36px 28px;
    }}
    header {{
      border-bottom: 4px solid #0f766e;
      padding-bottom: 20px;
      margin-bottom: 24px;
    }}
    h1 {{
      font-size: 34px;
      line-height: 1.15;
      margin: 0 0 12px;
    }}
    .source {{
      color: #52616f;
      font-size: 15px;
    }}
    .grid {{
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 16px;
    }}
    .block {{
      background: #ffffff;
      border: 1px solid #d7dee5;
      border-radius: 8px;
      padding: 18px;
      min-height: 150px;
    }}
    .num {{
      width: 28px;
      height: 28px;
      border-radius: 50%;
      background: #0f766e;
      color: white;
      display: grid;
      place-items: center;
      font-weight: 700;
      margin-bottom: 12px;
    }}
    h2 {{
      font-size: 18px;
      margin: 0 0 8px;
    }}
    p {{
      font-size: 15px;
      line-height: 1.5;
      margin: 0;
    }}
    footer {{
      margin-top: 24px;
      color: #52616f;
      font-size: 13px;
    }}
    @media (max-width: 720px) {{
      .grid {{ grid-template-columns: 1fr; }}
      h1 {{ font-size: 27px; }}
    }}
  </style>
</head>
<body>
  <main>
    <header>
      <h1>{escape(package.primary_article.title)}</h1>
      <div class="source">{escape(package.primary_article.source)} | {escape(str(package.primary_article.url))}</div>
    </header>
    <div class="grid">
      {block_html}
    </div>
    <footer>Generated for a concise NotebookLM learning workflow. Podcast target: about 15 minutes.</footer>
  </main>
</body>
</html>
""",
        encoding="utf-8",
    )
    return path


def _infographic_blocks(package: NotebookPackage) -> list[tuple[str, str]]:
    article = package.primary_article
    sources = package.sources[1:]
    return [
        ("The News", article.summary[:240] or article.title),
        ("Why It Matters", "Look for the signal behind the event: market structure, governance, deployment speed, and regional impact."),
        ("Technology Angle", "Identify the AI infrastructure, data, compute, model, or product capability that changes what organizations can deploy."),
        ("Policy Angle", "Assess how trust, regulation, standards, and public-sector adoption shape the path from experiment to production."),
        ("China-Singapore Relevance", "Map where Singapore's governance discipline and China's deployment scale can create practical AI collaboration."),
        ("Sources to Compare", "; ".join(source.source for source in sources[:5]) or "Use additional mainstream and deep-context sources."),
    ]


def _slugify(value: str) -> str:
    return sub(r"[^a-zA-Z0-9]+", "-", value.lower()).strip("-")

