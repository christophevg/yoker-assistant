"""Unit tests for the ``md_to_html`` yoker tool.

Covers the markdown features supported by the vendored converter and the
XSS/link-injection regressions earned by the security-engineer review.
"""

from yoker_assistant.tools import convert_markdown, md_to_html

# Representative fixture exercising every supported markdown feature.
MARKDOWN_FIXTURE = """# Main Title

## Section Heading

### Subsection

This is a **bold** paragraph.

| Name | Count |
|------|------:|
| Alpha | 1 |
| Beta | 2 |

- First item
- Second item

---

Final paragraph."""


def test_md_to_html_is_callable_and_returns_str() -> None:
  """``md_to_html`` is callable and returns a string."""
  result = md_to_html(MARKDOWN_FIXTURE)
  assert isinstance(result, str)
  assert result != ""


def test_headers_h1_h2_h3() -> None:
  """Headers at three levels produce ``<h1>``/``<h2>``/``<h3>``."""
  html = md_to_html(MARKDOWN_FIXTURE)
  assert "<h1>Main Title</h1>" in html
  assert "<h2>Section Heading</h2>" in html
  assert "<h3>Subsection</h3>" in html


def test_bold_text() -> None:
  """``**bold**`` becomes ``<strong>bold</strong>``."""
  html = md_to_html(MARKDOWN_FIXTURE)
  assert "<strong>bold</strong>" in html


def test_table_with_separator() -> None:
  """Pipe-delimited table with a separator line renders as ``<table>``."""
  html = md_to_html(MARKDOWN_FIXTURE)
  assert "<table>" in html
  assert "</table>" in html
  assert "<thead>" in html
  assert "<tbody>" in html
  assert "<th>Name</th>" in html
  assert "<th>Count</th>" in html
  assert "<td>Alpha</td>" in html
  assert "<td>Beta</td>" in html
  # The separator line (|---|---:|) must not leak as a row.
  assert "<td>---</td>" not in html
  assert "<th>---</th>" not in html


def test_list_items_wrapped_in_ul() -> None:
  """Consecutive ``- item`` lines become ``<li>`` wrapped in ``<ul>``."""
  html = md_to_html(MARKDOWN_FIXTURE)
  assert "<ul>" in html
  assert "</ul>" in html
  assert "<li>First item</li>" in html
  assert "<li>Second item</li>" in html


def test_horizontal_rule() -> None:
  """A ``---`` line becomes an ``<hr>``."""
  html = md_to_html(MARKDOWN_FIXTURE)
  assert "<hr>" in html


def test_paragraph() -> None:
  """A plain paragraph becomes a ``<p>``."""
  html = md_to_html(MARKDOWN_FIXTURE)
  assert "<p>Final paragraph.</p>" in html


def test_xss_script_tag_is_escaped() -> None:
  """Raw ``<script>`` in markdown must be escaped, not rendered as a tag."""
  html = md_to_html("Body with <script>alert(1)</script> here")
  assert "<script>" not in html
  assert "&lt;script&gt;" in html
  assert "&lt;/script&gt;" in html


def test_xss_script_in_header_is_escaped() -> None:
  """Raw ``<script>`` in a header must be escaped."""
  html = md_to_html("# <script>alert(1)</script>")
  assert "<h1><script>" not in html
  assert "<h1>&lt;script&gt;alert(1)&lt;/script&gt;</h1>" in html


def test_xss_script_in_list_item_is_escaped() -> None:
  """Raw ``<script>`` in a list item must be escaped."""
  html = md_to_html("- <script>alert(1)</script>")
  assert "<li><script>" not in html
  assert "<li>&lt;script&gt;alert(1)&lt;/script&gt;</li>" in html


def test_xss_script_in_table_cell_is_escaped() -> None:
  """Raw ``<script>`` in a table cell must be escaped."""
  md = "| Col |\n|-----|\n| <script>alert(1)</script> |"
  html = md_to_html(md)
  assert "<td><script>" not in html
  assert "<td>&lt;script&gt;alert(1)&lt;/script&gt;</td>" in html


def test_link_injection_is_escaped() -> None:
  """Raw ``<a href=...>`` in markdown must be escaped, not rendered as a link."""
  html = md_to_html('Text with <a href="https://evil.example">link</a> here')
  assert "<a href" not in html
  assert "&lt;a href" in html
  assert "&lt;/a&gt;" in html


def test_ampersand_is_escaped() -> None:
  """Bare ``&`` in input text must be escaped to ``&amp;``."""
  html = md_to_html("A & B")
  assert "&amp;" in html
  # The raw unescaped ampersand must not appear inside a tag body.
  assert "<p>A & B</p>" not in html


def test_bold_survives_escaping() -> None:
  """``**`` markers survive HTML escaping; bold still works on escaped text."""
  html = md_to_html("**bold** with <tag>")
  assert "<strong>bold</strong>" in html
  assert "&lt;tag&gt;" in html


def test_convert_markdown_directly() -> None:
  """``convert_markdown`` is the underlying converter and returns a string."""
  html = convert_markdown("# Hello")
  assert html == "<h1>Hello</h1>"
