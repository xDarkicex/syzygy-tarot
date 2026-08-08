"""The archetype quiz: 12 forced-choice questions that produce an MBTI type.

Framed mystically as discovering the archetype that runs you. Each of the four
MBTI dimensions (E/I, S/N, T/F, J/P) gets three questions; the type is the
majority vote on each. The type also maps to a tarot archetype so the profile
can present it as "Your archetype: The Hermit" rather than a clinical code.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class QuizQuestion:
    key: str
    dimension: str  # one of "EI", "SN", "TF", "JP"
    text: str
    a: str  # text for the first option
    a_letter: str  # letter a votes for (E/S/T/J)
    b: str  # text for the second option
    b_letter: str  # letter b votes for (I/N/F/P)


QUESTIONS: tuple[QuizQuestion, ...] = (
    # Energy: E/I
    QuizQuestion("energy_1", "EI", "After a long week, you recharge by:",
                 "being around people", "E", "being alone with your thoughts", "I"),
    QuizQuestion("energy_2", "EI", "In a group, you usually:",
                 "speak up and pull people in", "E", "listen first, speak when you mean it", "I"),
    QuizQuestion("energy_3", "EI", "Your best ideas arrive when:",
                 "talking them out loud with someone", "E", "sitting quietly on your own", "I"),
    # Information: S/N
    QuizQuestion("info_1", "SN", "When you look at a situation, you first notice:",
                 "the concrete facts, what's actually there", "S", "the pattern beneath, what it could become", "N"),
    QuizQuestion("info_2", "SN", "You tend to trust:",
                 "experience and what has worked before", "S", "hunches and the shape of a thing", "N"),
    QuizQuestion("info_3", "SN", "When learning something new, you prefer:",
                 "clear steps in order", "S", "the big picture and the why", "N"),
    # Decision: T/F
    QuizQuestion("decision_1", "TF", "When a choice is hard, you weigh:",
                 "logic, consequences, consistency", "T", "people, values, how it lands", "F"),
    QuizQuestion("decision_2", "TF", "You are more likely to say:",
                 "that doesn't hold up", "T", "that isn't fair to them", "F"),
    QuizQuestion("decision_3", "TF", "In a disagreement, you aim to:",
                 "find what's true, even if it stings", "T", "keep the bond whole, even if it bends", "F"),
    # Lifestyle: J/P
    QuizQuestion("life_1", "JP", "You are most at ease with:",
                 "a plan and a known shape to the day", "J", "room for things to shift as they come", "P"),
    QuizQuestion("life_2", "JP", "Deadlines tend to find you:",
                 "ahead, with room to spare", "J", "working best right at the edge", "P"),
    QuizQuestion("life_3", "JP", "Your ideal day is:",
                 "mapped out before it starts", "J", "whatever the morning brings", "P"),
)


@dataclass(frozen=True, slots=True)
class Archetype:
    type_code: str
    archetype: str
    card: str


# A light, defensible mapping of the 16 MBTI types to tarot archetypes.
ARCHETYPES: dict[str, Archetype] = {
    "INTJ": Archetype("INTJ", "The Strategist", "The Hermit"),
    "INTP": Archetype("INTP", "The Alchemist", "The Magician"),
    "ENTJ": Archetype("ENTJ", "The Architect", "The Emperor"),
    "ENTP": Archetype("ENTP", "The Catalyst", "The Fool"),
    "INFJ": Archetype("INFJ", "The Seer", "The High Priestess"),
    "INFP": Archetype("INFP", "The Dreamer", "The Moon"),
    "ENFJ": Archetype("ENFJ", "The Guide", "The Empress"),
    "ENFP": Archetype("ENFP", "The Beacon", "The Star"),
    "ISTJ": Archetype("ISTJ", "The Guardian", "The Hierophant"),
    "ISFJ": Archetype("ISFJ", "The Keeper", "The World"),
    "ESTJ": Archetype("ESTJ", "The Arbiter", "Justice"),
    "ESFJ": Archetype("ESFJ", "The Harmonizer", "The Sun"),
    "ISTP": Archetype("ISTP", "The Forger", "The Chariot"),
    "ISFP": Archetype("ISFP", "The Contemplative", "The Hanged Man"),
    "ESTP": Archetype("ESTP", "The Maker", "The Tower"),
    "ESFP": Archetype("ESFP", "The Lover", "The Lovers"),
}


def compute_type(answers: dict[str, str]) -> str:
    """Given question-key -> chosen letter, produce a 4-letter MBTI code.

    Unknown keys are ignored. Ties resolve to the first pole listed for the
    dimension (I, N, T, P).
    """
    votes: dict[str, list[str]] = {"EI": [], "SN": [], "TF": [], "JP": []}
    by_key = {q.key: q for q in QUESTIONS}
    for key, chosen in answers.items():
        q = by_key.get(key)
        if q is None:
            continue
        letter = chosen.strip().upper()
        if letter in (q.a_letter, q.b_letter):
            votes[q.dimension].append(letter)

    def pole(dimension: str) -> str:
        pool = votes[dimension]
        if not pool:
            return {"EI": "I", "SN": "N", "TF": "T", "JP": "P"}[dimension]
        first = pool[0]
        second = "I" if first == "E" else "E"
        return first if pool.count(first) >= pool.count(second) else second

    return f"{pole('EI')}{pole('SN')}{pole('TF')}{pole('JP')}"


def archetype_for(type_code: str) -> Archetype:
    return ARCHETYPES.get(type_code, Archetype(type_code, "The Wanderer", "The Fool"))
