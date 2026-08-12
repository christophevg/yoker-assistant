"""
Rich Output-only UI handler implementation.
"""

from __future__ import annotations

import os
import traceback
from pathlib import Path
from typing import Any

from pyfiglet import Figlet
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.style import Style
from yoker import __version__
from yoker.core import Agent
from yoker.exceptions import NetworkError, ToolError
from yoker.ui.handler import UIHandler

PROMPT_STYLE = Style(color="black", bgcolor="grey93")
THINKING_STYLE = Style(color="grey74")
CONTENT_STYLE = Style(color="bright_black")
TOOL_STYLE = Style(color="cyan")
TOOL_RESULT_STYLE = Style(color="bright_black")
STATS_STYLE = Style(color="bright_blue", dim=True)
ERROR_STYLE = Style(color="red", bold=True)


class RichUIHandler(UIHandler):
  """
  Rich Output-only UI handler implementation.
  """

  def __init__(
    self,
    show_thinking: bool = True,
    show_tool_calls: bool = True,
    show_stats: bool = False,
    show_time: bool = True,
    console: Console | None = None,
  ) -> None:
    self.show_thinking = show_thinking
    self.show_tool_calls = show_tool_calls
    self.show_stats = show_stats
    self.console = console if console is not None else Console()

  # Lifecycle

  async def start(self, agent: Agent, title: str = "Yoker", version: str = __version__) -> None:
    banner = str(Figlet(font="standard").renderText(title)).rstrip()
    banner = f"[blue bold]{banner} {version}[/blue bold]"

    harness = agent.config.harness
    harness_line = f"[blue]Harness[/blue]: {harness.name}"
    if harness.version:
      harness_line += f" v{harness.version}"
    if harness.author:
      harness_line += f" by {harness.author}"

    motd_lines = banner.split("\n") + [
      f"[blue]Model[/blue]: {agent.model} (provider: {agent.config.backend.provider})",
      harness_line,
      f"[blue]Thinking[/blue]: {agent.thinking_mode.value}",
      f"[blue]Agent[/blue]: {agent.definition.name}",
      f"[dim]{agent.definition.description.strip()}[/dim]",
    ]
    if agent.definition.source_path:
      relative_path = Path(os.path.relpath(agent.definition.source_path))
      motd_lines.append(f"[blue]Source[/blue]: {relative_path}")

    if agent.tools:
      motd_lines.append(f"[blue]Tools[/blue]: {', '.join(list(agent.tools.keys()))}")

    motd_lines.append("[dim]Press Ctrl+D (or Ctrl+Z on Windows) to quit.[/dim]")

    self.console.print(Panel("\n".join(motd_lines), title="👋 Welcome..."))

  async def shutdown(self, reason: str) -> None:
    pass

  # Output

  def output_info(self, text: str) -> None:
    self.console.print(text)

  # Prompt

  def output_prompt(self, text: str) -> None:
    self.console.print()
    self.console.print(Panel(text, style=PROMPT_STYLE, box=box.SIMPLE_HEAD))

  # Content Output

  def start_content_stream(self) -> None:
    self.console.print("⏺ ", end="", style=CONTENT_STYLE)

  def stream_content(self, chunk: str, content_type: str = "text/plain") -> None:
    self.console.print(chunk, end="", style=CONTENT_STYLE)

  def end_content_stream(self, total_length: int) -> None:
    self.console.print()  # final newline

  def output_content(self, content: str, content_type: str = "text/plain") -> None:
    """Output non-streamed content (delegates to streaming path)."""
    self.start_content_stream()
    self.stream_content(content, content_type)
    self.end_content_stream(len(content))

  # Thinking

  def start_thinking_stream(self) -> None:
    if self.show_thinking:
      self.console.print()

  def stream_thinking(self, chunk: str) -> None:
    if self.show_thinking:
      self.console.print(chunk, style=THINKING_STYLE, end="")

  def end_thinking_stream(self, total_length: int) -> None:
    if self.show_thinking:
      self.console.print()

  def output_thinking(self, text: str) -> None:
    self.start_thinking_stream()
    self.stream_thinking(text)
    self.end_thinking_stream(len(text))

  # Tooling

  def output_tool_call(self, tool_name: str, args: dict[str, Any]) -> None:
    if self.show_tool_calls:
      self.console.print(f"⏺ {tool_name}", end="", style=TOOL_STYLE)
      details = self._format_tool_details(tool_name, args)
      self.console.print(f"({details})")

  def output_tool_result(self, tool_name: str, success: bool, result: str) -> None:
    if not self.show_tool_calls:
      return

    if success:
      self.console.print("  [green]✓ Success[/green]", end="")
      # TODO implement more extensive result summary
      self.console.print(f" ({len(result)} chars)", style=TOOL_RESULT_STYLE)
    else:
      self.console.print("  [red]𐄂 Fail[/red]")
      self._print_error(result if result else "Failed")

  def output_tool_content(
    self,
    tool_name: str,
    operation: str,
    path: str,
    content: str | None,
    content_type: str,
    metadata: dict[str, Any],
  ) -> None:
    if not self.show_tool_calls:
      return

    filename = Path(path).name

    # Dispatch based on content_type
    if content_type == "application/x-summary":
      self._show_summary(operation, filename, metadata)
    elif content_type in ("diff", "text/x-diff"):
      self._show_diff_content(content, filename, operation, metadata)
    else:
      self._show_full_content(content, filename, operation, metadata)

  # Stats

  def output_stats(
    self,
    duration_ms: int,
    prompt_tokens: int,
    eval_tokens: int,
    usage_limits: dict[str, object] | None = None,
  ) -> None:
    """Output turn statistics.

    Args:
      duration_ms: Duration in milliseconds.
      prompt_tokens: Number of prompt tokens.
      eval_tokens: Number of evaluation tokens.
      usage_limits: Optional backend API usage limits (unused in this handler).
    """
    if self.show_stats:
      total = prompt_tokens + eval_tokens
      duration_s = duration_ms / 1000.0
      self.console.print(f"📊 {duration_s:.1f}s, {total} tokens", style=STATS_STYLE)

  # Error

  def output_error(self, error: Exception, include_traceback: bool = False) -> None:
    self.console.print()
    if isinstance(error, NetworkError):
      # Show compact user-friendly message by default
      if error.recoverable:
        msg = f"{error.message}\n\nYour message was preserved. Try again or type a new message."
      else:
        msg = f"{error.message}\n\nUnable to recover. Please restart the session."
      # Include debug message (with exception chain) if traceback requested
      debug_exc = error if include_traceback else None
      self._print_error(msg, debug_exc)
    elif isinstance(error, ToolError):
      msg = f"Tool Error ({error.tool_name}): {error}"
      self._print_error(msg, error if include_traceback else None)
    else:
      msg = f"Error: {error}"
      self._print_error(msg, error if include_traceback else None)

  # Formatting Helpers

  def _print_error(self, msg: str, exc: Exception | None = None) -> None:
    if exc:
      # For NetworkError, show debug message (with exception chain) instead of full traceback
      if isinstance(exc, NetworkError):
        # Show the debug message with exception chain
        msg += f"\n\n[dim]{exc.get_debug_message()}[/dim]"
      else:
        # For other exceptions, show full Python traceback
        tb = "".join(traceback.TracebackException.from_exception(exc).format())
        msg += "\n\n[black]" + tb

    self.console.print(Panel(msg, title="ERROR", style=ERROR_STYLE))

  @staticmethod
  def _capitalize(name: str) -> str:
    """Capitalize first letter of name for display.

    Args:
      name: Name to capitalize.

    Returns:
      Name with first letter capitalized.
    """
    if name:
      return name[0].upper() + name[1:]
    return name

  @staticmethod
  def _extract_filename(arguments: dict[str, Any]) -> str:
    """Extract filename from tool arguments.

    Args:
      arguments: Tool arguments dictionary.

    Returns:
      Filename (basename) of the path argument, or first arg value if no path.
    """
    # Special case: git tool shows operation, not path
    if "operation" in arguments:
      return str(arguments["operation"])

    # Look for common path argument names
    for key in ("file_path", "path", "filepath"):
      if key in arguments:
        return Path(arguments[key]).name

    # Fallback: use first argument value
    # if arguments:
    #   first_value = next(iter(arguments.values()))
    #   return str(first_value)

    return ""

  def _format_tool_details(self, tool_name: str, arguments: dict[str, Any]) -> str:
    """Format tool arguments for display.

    Args:
      tool_name: Name of the tool.
      arguments: Tool arguments dictionary.

    Returns:
      Formatted string showing relevant arguments.
    """
    # Special formatting for git tool: show operation, path, and args
    if tool_name == "git":
      operation = arguments.get("operation", "")
      path = arguments.get("path", "")
      args = arguments.get("args", {})

      # Build details string
      parts = [str(operation)] if operation else []
      if path:
        parts.append(f"on {path}")
      if args:
        # Show key args (first 2 to keep it concise)
        args_str = ", ".join(f"{k}={v}" for k, v in list(args.items())[:2])
        if len(args) > 2:
          args_str += ", ..."
        parts.append(f"({args_str})")

      return " ".join(parts) if parts else str(arguments)

    # Special formatting for websearch: show query
    if tool_name == "websearch":
      query = arguments.get("query", "")
      if query:
        return str(query)
      return str(arguments)

    # For other tools: show not-None values, limit to first 5 chars for strings
    def str_summary(value: str) -> str:
      if "\n" in value:
        return f"{len(value)} chars"
      return value

    return " ".join(
      [
        key + "=" + str_summary(value) if isinstance(value, str) else str(value)
        for key, value in arguments.items()
      ]
    )

    # return self._extract_filename(arguments)

  def _show_summary(
    self,
    operation: str,
    filename: str,
    metadata: dict[str, Any],
  ) -> None:
    """Show operation summary.

    Args:
      operation: Operation type.
      filename: Basename of file.
      metadata: Summary metadata.
    """
    if operation == "write":
      lines = metadata.get("lines", 0)
      is_new_file = metadata.get("is_new_file", False)
      is_binary = metadata.get("is_binary", False)

      if is_binary:
        byte_size = metadata.get("bytes", 0)
        self.console.print(f"  {filename} ({byte_size // 1024} KB binary)")
      elif lines == 0:
        self.console.print(f"  {filename} (0 lines, empty)")
      elif is_new_file:
        self.console.print(f"  Creating new file {filename} ({lines} lines)")
      else:
        self.console.print(f"  Overwriting {filename} ({lines} lines)")

    elif operation in ("insert_before", "insert_after"):
      line_number = metadata.get("line_number", 0)
      inserted_lines = metadata.get("inserted_lines", 1)
      self.console.print(f"  Insert at line {line_number} in {filename}: {inserted_lines} line(s)")

    elif operation == "replace":
      self.console.print(f"  Replace in {filename}")

    elif operation == "delete":
      line_number = metadata.get("line_number")
      if line_number:
        self.console.print(f"  Delete line {line_number} in {filename}")
      else:
        self.console.print(f"  Delete in {filename}")

  def _show_full_content(
    self,
    content: str | None,
    filename: str,
    operation: str,
    metadata: dict[str, Any],
  ) -> None:
    """Show full content with line numbers.

    Args:
      content: Content text (may be None for summary fallback).
      filename: Basename of file.
      operation: Operation type.
      metadata: Additional metadata.
    """
    if content is None:
      # Fall back to summary
      self._show_summary(operation, filename, metadata)
      return

    # Show header
    self.console.print(f"\n  {filename}")

    # Show content with line numbers
    lines = content.splitlines()
    for i, line in enumerate(lines, start=1):
      # Escape brackets in user content to prevent Rich markup
      escaped_line = line.replace("[", "\\[").replace("]", "\\]")
      self.console.print(f"  {i:4d}│{escaped_line}")

    # Show truncation indicator if needed
    if metadata.get("truncated"):
      original_lines = metadata.get("original_line_count", 0)
      remaining = original_lines - len(lines)
      self.console.print(f"  ... ({remaining} more lines)")

  def _show_diff_content(
    self,
    content: str | None,
    filename: str,
    operation: str,
    metadata: dict[str, Any],
  ) -> None:
    """Show unified diff with colors.

    Args:
      content: Diff content text (may be None for summary fallback).
      filename: Basename of file.
      operation: Operation type.
      metadata: Additional metadata.
    """
    if content is None:
      # Fall back to summary
      self._show_summary(operation, filename, metadata)
      return

    # Show header
    self.console.print(f"  {filename}")

    # Show diff with colors (using Rich styles)
    lines = content.splitlines()
    for line in lines:
      # Skip file header lines
      if line.startswith("--- ") or line.startswith("+++ "):
        continue
      # Skip diff header
      if line.startswith("diff --"):
        continue

      # Escape brackets in user content
      escaped_line = line.replace("[", "\\[").replace("]", "\\]")

      # Color based on prefix (using Rich styles)
      if line.startswith("@@"):
        self.console.print(f"  [cyan]{escaped_line}[/]")
      elif line.startswith("-"):
        self.console.print(f"  [red]{escaped_line}[/]")
      elif line.startswith("+"):
        self.console.print(f"  [green]{escaped_line}[/]")
      else:
        self.console.print(f"  {escaped_line}")

    # Show truncation indicator if needed
    if metadata.get("truncated"):
      original_lines = metadata.get("original_diff_lines", 0)
      remaining = original_lines - len(lines)
      self.console.print(f"  ... ({remaining} more lines)")

  # Not Implemented

  async def get_input(self, prompt: str = "> ") -> str | None:
    pass

  async def get_secret_input(self, prompt: str = "> ") -> str | None:
    pass

  async def output_step_title(self, step: int, total: int, title: str) -> None:
    pass

  def output_command_result(self, result: str) -> None:
    pass
