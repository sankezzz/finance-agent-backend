"""Pipeline stage definitions.

Defines the Stage enum (PARSE, CATEGORIZE, ANALYZE, RECOMMEND) and the
fixed ordering the orchestrator sequences agents in.
"""

from enum import Enum


class Stage(str, Enum):
    parse = "parse"
    categorize = "categorize"
    analyze = "analyze"
    recommend = "recommend"


# The linear order the orchestrator runs agents in.
STAGE_ORDER: list[Stage] = [
    Stage.parse,
    Stage.categorize,
    Stage.analyze,
    Stage.recommend,
]
