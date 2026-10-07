"""Question intent classification for version handling.

current_state : asks what is true NOW           -> only latest versions count
historical    : asks how something changed       -> all versions, in date order
lookup        : everything else                  -> all versions, ranked by relevance

Rule-based on purpose: deterministic, free, testable. Stage 6.5 replaces this
with an LLM router (domain + request type) behind the same function name.
"""
import re

HISTORICAL = re.compile(
    r"\b(how (has|have|did|does)\b.*\b(change|changed|evolve|evolved|progress|progressed|grow|grown|move|moved)"
    r"|changed?|changes|changing|over time|progression|history|evolution|evolved"
    r"|trend|used to|previously|originally|at first|initially"
    r"|from \w+ to \w+|went from)\b"
)

CURRENT = re.compile(
    r"\b(current|currently|now|latest|still|today|at the moment|right now"
    r"|presently|these days|as of now|most recent|anymore)\b"
)


def classify_intent(question):
    q = question.lower()
    if HISTORICAL.search(q):
        return "historical"
    if CURRENT.search(q):
        return "current_state"
    return "lookup"