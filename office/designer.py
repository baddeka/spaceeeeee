"""frontren's style directions: a few distinct looks found from references, and DESIGN.md for the one picked."""

from __future__ import annotations

import re

from pydantic import BaseModel, Field, ValidationError

# Looking for a style only reads: the project, the user's files, the web and Figma.
STYLE_TOOLS = ["Read", "Glob", "Grep", "WebSearch", "WebFetch", "Skill"]

# Figma's MCP server under each name Claude Code may give it: added by hand as "figma", the Figma
# plugin, or the claude.ai connector. Only its reading tools: frontren reads designs, never edits them.
FIGMA_SERVERS = ("figma", "Figma", "plugin_figma_figma", "claude_ai_Figma")
FIGMA_READ_TOOLS = (
    "whoami",
    "create_session",
    "get_design_context",
    "get_screenshot",
    "get_metadata",
    "get_variable_defs",
    "search_design_system",
    "get_libraries",
)
FIGMA_TOOLS = [f"mcp__{server}__{tool}" for server in FIGMA_SERVERS for tool in FIGMA_READ_TOOLS]

DESIGN_FILE = "DESIGN.md"

STYLE_PROMPT = """\
You are frontren, the frontend developer in a four-person office: idearen comes up with ideas, backren \
builds the backend, you build the frontend, and checkren reviews the work. Before you build an \
interface, the user picks its style: you propose a few distinct directions, the user chooses one, and \
it becomes the project's DESIGN.md.

Before you answer, load the design-directions skill with the Skill tool and follow it.

Start from what the user gave: the brief, the files they attached (open each with Read; screenshots \
show what they like), and a figma.com link if there is one, which you read with the Figma tools when \
you have them. Look at the project too: an existing DESIGN.md, its pages and styles.

Then find references on the web with a few searches in design galleries such as Dribbble, Behance, \
Awwwards, Land-book, Mobbin and Pinterest. Cite only addresses you found in search results or \
opened; never make one up. Keep the research short, about five searches or page reads in all.

Propose three directions that differ in mood, palette and type, not just in color. Set recommended to \
the index (starting at 0) of the one you would pick. Never change files; you only propose.
"""


class Swatch(BaseModel):
    role: str = Field(description="What the color is for: background, surface, text, muted text, accent, ...")
    hex: str = Field(description="The color as #rrggbb")


class Reference(BaseModel):
    title: str = Field(description="What the reference is, e.g. its site and page")
    url: str = Field(description="An http(s) address found in search results or opened, never made up")
    take: str = Field(description="What to take from it: the layout, the type, the colors, a detail")


class Direction(BaseModel):
    name: str = Field(description="Two or three words, e.g. Calm Paper")
    mood: str = Field(description="Three words for how it feels")
    summary: str = Field(description="Two sentences on what the interface looks like")
    palette: list[Swatch] = Field(
        description="4 to 6 colors with their roles; text on its background reaches a contrast of 4.5:1"
    )
    heading_font: str = Field(description="A Google Fonts family for headings, with Cyrillic for a Russian interface")
    body_font: str = Field(description="A Google Fonts family for text, with Cyrillic for a Russian interface")
    shapes: str = Field(description="Corners, borders, shadows, spacing and density")
    components: str = Field(description="Buttons, inputs, cards, icons and images in this style")
    references: list[Reference] = Field(description="Up to four references")
    fits: str = Field(description="Why it suits this product and the people who use it")


class StylesOutput(BaseModel):
    directions: list[Direction]
    recommended: int = Field(description="0-based index of the direction to pick")


class StylesError(Exception):
    pass


HEX = re.compile(r"#[0-9a-fA-F]{6}")
MAX_REFERENCES = 4


def parse_styles(structured: dict | None) -> tuple[list[dict], int]:
    """Validates frontren's answer: the directions that have a usable palette, and the recommended one.

    Colors that are not #rrggbb and links that are not http(s) are dropped: the page shows the colors
    and opens the links.
    """
    if structured is None:
        raise StylesError("frontren returned no styles")
    try:
        output = StylesOutput.model_validate(structured)
    except ValidationError as e:
        raise StylesError(f"frontren returned malformed styles: {e}") from e
    directions = []
    best = 0
    for n, direction in enumerate(output.directions):
        found = direction.model_dump()
        found["palette"] = [{**s, "hex": s["hex"].strip()} for s in found["palette"] if HEX.fullmatch(s["hex"].strip())]
        found["references"] = [
            {**r, "url": r["url"].strip()} for r in found["references"] if _web_address(r["url"])
        ][:MAX_REFERENCES]
        if len(found["palette"]) < 2:
            continue
        if n == output.recommended:
            best = len(directions)
        directions.append(found)
    if not directions:
        raise StylesError("frontren returned no style with a usable palette")
    return directions, best


def _web_address(url: str) -> bool:
    return re.match(r"https?://[^\s/]+", url.strip(), re.IGNORECASE) is not None


def style_request(brief: str, task: str | None, reply_in: str, notes: str = "") -> str:
    """frontren's message; `notes` (attached files, earlier directions) start with a blank line."""
    what = brief or "(none given: work it out from the project and its current task)"
    current = f"\nThe current task: {task}" if task else ""
    return f"What the interface is for: {what}{current}{notes}\n\nPropose three style directions. {reply_in}"


def design_md(direction: dict) -> str:
    """The project's DESIGN.md for the chosen direction, which frontren follows from then on."""
    lines = [
        f"# Design: {direction['name']}",
        "",
        direction["summary"],
        "",
        f"Mood: {direction['mood']}",
        "",
        "Chosen in Rens Office from frontren's style directions. frontren follows this file; edit it to change the style.",
        "",
        "## Colors",
        "",
        "| Role | Color |",
        "|---|---|",
        *(f"| {_cell(s['role'])} | `{s['hex']}` |" for s in direction["palette"]),
        "",
        "## Type",
        "",
        f"- Headings: {direction['heading_font']}",
        f"- Text: {direction['body_font']}",
        "",
        "Both come from Google Fonts, with a system font as the fallback.",
        "",
        "## Shapes and spacing",
        "",
        direction["shapes"],
        "",
        "## Components",
        "",
        direction["components"],
        "",
        "## Why this style",
        "",
        direction["fits"],
    ]
    if direction["references"]:
        lines += ["", "## References", "", *(f"- {r['title']}: {r['url']} ({r['take']})" for r in direction["references"])]
    return "\n".join(lines) + "\n"


def _cell(text: str) -> str:
    return text.replace("|", "/").replace("\n", " ")
