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


def figma_tools(*texts: str | None) -> list[str] | None:
    """Figma's tools for a run whose request has a figma.com link, else none.

    A run given MCP tools connects every MCP server the user set up, whose tool descriptions all
    take up its context, so only a run that has a design to read pays for that.
    """
    return FIGMA_TOOLS if any("figma.com/" in (text or "").lower() for text in texts) else None

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


# What a color is for, in words the page can rely on whatever language the roles are written in.
TOKENS = ("background", "surface", "text", "muted", "accent", "extra")
# Roles written before colors had tokens, or by a model that left the token out, are read by their words.
TOKEN_WORDS = {
    "background": ("background", "фон"),
    "surface": ("surface", "card", "поверхност", "карточк"),
    "muted": ("muted", "secondary", "втор", "приглуш"),
    "text": ("text", "текст", "ink", "чернил"),
    "accent": ("accent", "primary", "акцент", "кнопк"),
}


class Swatch(BaseModel):
    token: str = Field(
        default="",
        description="One of: background (the page), surface (cards, panels), text, muted (secondary text), "
        "accent (the main action), extra (anything else). Give exactly one each of background, text and accent.",
    )
    role: str = Field(description="What the color is for, in the user's language")
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
        found["palette"] = _tokens(
            [{**s, "hex": s["hex"].strip()} for s in found["palette"] if HEX.fullmatch(s["hex"].strip())]
        )
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


def _tokens(palette: list[dict]) -> list[dict]:
    """Gives every color its token, so the page can tell the background from the text in any language.

    A token the model gave is kept when it is a known one and not taken; otherwise the role's words
    decide, and what is still unnamed fills background, text and accent in the order colors are listed.
    """
    taken: set[str] = set()
    for swatch in palette:
        token = swatch.get("token", "").strip().lower()
        swatch["token"] = token if token in TOKENS and (token == "extra" or token not in taken) else ""
        taken.add(swatch["token"])
    for swatch in palette:
        if not swatch["token"]:
            role = swatch["role"].lower()
            # "muted text" is muted, not text: the more specific word is looked for first.
            named = next((t for t, words in TOKEN_WORDS.items() if t not in taken and any(w in role for w in words)), "")
            swatch["token"] = named
            taken.add(named)
    for token in ("background", "text", "accent"):
        if token not in taken and (free := next((s for s in palette if not s["token"]), None)):
            free["token"] = token
            taken.add(token)
    for swatch in palette:
        swatch["token"] = swatch["token"] or "extra"
    return palette


def css_variables(direction: dict) -> str:
    """The direction as CSS variables, for frontren to paste into the stylesheet as they are."""
    lines = []
    extras = 0
    for swatch in direction["palette"]:
        if swatch["token"] == "extra":
            extras += 1
            name = f"extra-{extras}"
        else:
            name = swatch["token"]
        lines.append(f"  --color-{name}: {swatch['hex']}; /* {_cell(swatch['role'])} */")
    lines.append(f"  --font-heading: \"{direction['heading_font']}\", system-ui, sans-serif;")
    lines.append(f"  --font-body: \"{direction['body_font']}\", system-ui, sans-serif;")
    return ":root {\n" + "\n".join(lines) + "\n}"


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
        "Use these as CSS variables, exactly:",
        "",
        "```css",
        css_variables(direction),
        "```",
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
