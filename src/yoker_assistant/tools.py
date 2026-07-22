"""Custom yoker tools defined by this package.

Provides the ``md_to_html`` tool, which converts a markdown string to an HTML
body fragment (no ``<html>`` wrapper). Email wrapping/sending is the loop's
job (P2-005), not this tool's.
"""

# Vendored from c3/bin/md-to-html.py — reuses the existing conversion logic
# per owner instruction. HTML-escaping fix applied for XSS prevention.

import re
from html import escape
from typing import Annotated

from yoker.tools.annotations import Text


def _esc(s: str) -> str:
  """HTML-escape ``&``, ``<``, ``>`` in input text (no quote escaping)."""
  return escape(s, quote=False)


def convert_table(lines: list[str]) -> list[str]:
  """Convert a markdown pipe-delimited table to an HTML table fragment."""
  html = ["<table>"]

  for i, line in enumerate(lines):
    if not line.strip():
      continue

    raw_cells = [c.strip() for c in line.split("|") if c.strip()]

    # Skip separator lines (|---|---|) — checked on RAW cells, before escaping,
    # so the ``-``/``:``/space`` set check is not confused by escaping.
    if all(set(c) <= {"-", ":", " "} for c in raw_cells):
      continue

    # Escape cell content first, then apply bold substitution to the escaped
    # text. The ** marker survives escaping, so bold still works; the
    # <strong>/</strong> tags are added by us, not from input.
    cells = [re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", _esc(c)) for c in raw_cells]

    if i == 0:
      html.append("  <thead>")
      html.append("    <tr>")
      for cell in cells:
        html.append(f"      <th>{cell}</th>")
      html.append("    </tr>")
      html.append("  </thead>")
      html.append("  <tbody>")
    else:
      html.append("    <tr>")
      for cell in cells:
        html.append(f"      <td>{cell}</td>")
      html.append("    </tr>")

  html.append("  </tbody>")
  html.append("</table>")
  return html


def convert_markdown(md: str) -> str:
  """Convert markdown to an HTML body fragment.

  Handles headers, bold, tables, lists, horizontal rules, and paragraphs.
  Returns the HTML body (no ``<html>`` wrapper).
  """
  lines = md.split("\n")
  html_lines = []
  i = 0

  while i < len(lines):
    line = lines[i]

    # Horizontal rule
    if line.strip() == "---":
      html_lines.append("<hr>")
      i += 1
      continue

    # Headers — escape header text before wrapping in tags
    if line.startswith("### "):
      html_lines.append(f"<h3>{_esc(line[4:].strip())}</h3>")
      i += 1
      continue
    if line.startswith("## "):
      html_lines.append(f"<h2>{_esc(line[3:].strip())}</h2>")
      i += 1
      continue
    if line.startswith("# "):
      html_lines.append(f"<h1>{_esc(line[2:].strip())}</h1>")
      i += 1
      continue

    # Table detection
    if "|" in line and i + 1 < len(lines) and "|" in lines[i + 1]:
      # Collect table lines
      table_lines = []
      while i < len(lines) and "|" in lines[i]:
        table_lines.append(lines[i])
        i += 1
      html_lines.extend(convert_table(table_lines))
      continue

    # List items — escape list item text before wrapping in tags
    if line.startswith("- "):
      html_lines.append(f"<li>{_esc(line[2:].strip())}</li>")
      i += 1
      continue

    # Empty line
    if not line.strip():
      html_lines.append("")
      i += 1
      continue

    # Paragraph — escape the whole line first, then apply bold substitution
    # to the escaped text. ** survives escaping; <strong>/</strong> are ours.
    escaped_line = _esc(line)
    escaped_line = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", escaped_line)

    if escaped_line.strip():
      html_lines.append(f"<p>{escaped_line}</p>")

    i += 1

  html = "\n".join(html_lines)

  # Wrap consecutive <li> in <ul>
  html = re.sub(r"(<li>.*?</li>\n)+", lambda m: f"<ul>\n{m.group(0)}</ul>\n", html)

  return html


def md_to_html(
  markdown: Annotated[str, Text("Markdown source to convert to HTML")],
) -> str:
  """Convert a markdown string to an HTML body fragment.

  Handles headers, bold, tables, lists, horizontal rules, and paragraphs.
  Returns the HTML body (no ``<html>`` wrapper).
  """
  return convert_markdown(markdown)
