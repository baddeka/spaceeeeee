"""The idea maker: turns a topic into a few buildable ideas, each with a brief for the developer."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, ValidationError

IDEATOR_TOOLS = ["Read", "Grep", "Glob", "Skill", "WebSearch"]

IDEATOR_PROMPT = """\
You are idearen, the idea maker in a small software office. coderen, the developer, builds what you \
propose, and checkren reviews coderen's work.

The user gives you a topic. Propose 3 to 5 distinct ideas for software the developer could build on \
that topic. Make them concrete and buildable, not slogans: each one is a specific tool, app, page, \
script or feature for a specific kind of user.

Before you answer, load your skills with the Skill tool: brainstorm for finding and choosing ideas, \
write-brief for each idea's task, and market-check when the topic needs to know what already exists. \
Use web search only when current facts matter (existing products, recent changes); otherwise rely \
on what you know.

Look at the current directory first. If it already has a project, fit the ideas to it (its \
language, framework and purpose) and say so in the briefs. If it is empty, any stack is fine; prefer \
simple ones the developer can finish in one session.

For each idea:
- title: a short name, under 8 words.
- pitch: one or two sentences on what it is and who it is for.
- why: the problem it solves or what makes it stand out.
- scope: small (one sitting), medium (a few hours), or large (needs to be split).
- task: a complete brief the developer can start from without asking questions: what to build, \
the main features, acceptance criteria, what is out of scope, and the suggested stack.

Set recommended to the index (starting at 0) of the idea with the best value for its effort. \
Never change files; you only propose.
"""


class Idea(BaseModel):
    title: str = Field(description="Short name of the idea, under 8 words")
    pitch: str = Field(description="One or two sentences: what it is and who it is for")
    why: str = Field(description="The problem it solves or what makes it stand out")
    scope: Literal["small", "medium", "large"]
    task: str = Field(
        description="Complete brief for the developer: what to build, main features, acceptance "
        "criteria, what is out of scope, suggested stack"
    )


class IdeasOutput(BaseModel):
    ideas: list[Idea]
    recommended: int = Field(description="0-based index of the idea to build first")


class IdeasError(Exception):
    pass


def parse_ideas(structured: dict | None) -> list[dict]:
    """Validates the model's answer and returns the ideas, with exactly one marked recommended."""
    if structured is None:
        raise IdeasError("the idea maker returned no ideas")
    try:
        output = IdeasOutput.model_validate(structured)
    except ValidationError as e:
        raise IdeasError(f"the idea maker returned malformed ideas: {e}") from e
    if not output.ideas:
        raise IdeasError("the idea maker returned an empty list")
    best = output.recommended if 0 <= output.recommended < len(output.ideas) else 0
    return [
        idea.model_dump() | {"recommended": n == best, "handed": False}
        for n, idea in enumerate(output.ideas)
    ]


def idea_request(topic: str, reply_in: str, notes: str = "") -> str:
    """The idea maker's message; `notes` (attached files, earlier ideas) start with a blank line."""
    return f"Topic: {topic}{notes}\n\nPropose 3 to 5 ideas on this topic. {reply_in}"


def task_from_idea(idea: dict, topic: str, intro: str, guard: str) -> str:
    """The developer's task for a handed-off idea: the brief, with the idea's context on top.

    The brief was written by a model that may have read web pages, not by the user, so the
    developer is told where its trust ends.
    """
    return (
        f"{intro} {idea['title']}\n"
        f"Topic: {topic}\n"
        f"Pitch: {idea['pitch']}\n"
        f"Why: {idea['why']}\n\n"
        f"{idea['task']}\n\n"
        f"{guard}"
    )
