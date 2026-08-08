"""Behavioral consistency metrics, per Abdulhai et al. (2025).

Three sub-scores, each in [0, 1]:

``prompt_to_line``
    Does each mentor turn stay aligned with the persona system prompt? Mean
    similarity between the prompt and every mentor turn. Detects persona drift
    away from the instruction over a conversation.

``line_to_line``
    Do the mentor's turns stay consistent with one another? Mean pairwise
    similarity across mentor turns. Detects a voice that wanders mid-session.

``qa_consistency``
    Does the mentor actually answer what the user asked? Mean similarity between
    each user turn and the mentor reply that follows it. Detects non-responsive
    or evasive answers.

All three are similarity-based, so they inherit the backend's limits — under the
v0 :class:`~app.metrics.scoring.LexicalScorer` they measure vocabulary overlap,
not semantic agreement.
"""

from __future__ import annotations

from app.metrics.schemas import ConsistencyResult, Dialogue, Speaker
from app.metrics.scoring import SimilarityScorer, default_scorer


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def prompt_to_line(
    dialogue: Dialogue,
    scorer: SimilarityScorer | None = None,
) -> tuple[float, int]:
    """Mean similarity between the system prompt and each mentor turn."""
    scorer = scorer or default_scorer()
    mentor_turns = dialogue.mentor_turns
    if not mentor_turns:
        return 1.0, 0
    scores = [scorer.similarity(dialogue.system_prompt, t.text) for t in mentor_turns]
    return round(_mean(scores), 6), len(scores)


def line_to_line(
    dialogue: Dialogue,
    scorer: SimilarityScorer | None = None,
) -> tuple[float, int]:
    """Mean pairwise similarity across the mentor's own turns.

    Needs at least two mentor turns; with fewer there is nothing to compare, so
    the score is 1.0 with a comparison count of 0.
    """
    scorer = scorer or default_scorer()
    texts = [t.text for t in dialogue.mentor_turns]
    if len(texts) < 2:
        return 1.0, 0
    matrix = scorer.similarity_matrix(texts)
    pairs = [
        matrix[i][j] for i in range(len(texts)) for j in range(i + 1, len(texts))
    ]
    return round(_mean(pairs), 6), len(pairs)


def qa_consistency(
    dialogue: Dialogue,
    scorer: SimilarityScorer | None = None,
) -> tuple[float, int]:
    """Mean similarity between each user turn and the mentor's next reply.

    Only adjacent user→mentor transitions count as a Q&A pair. Consecutive
    mentor turns after a reply are treated as continuation, not fresh answers.
    """
    scorer = scorer or default_scorer()
    turns = dialogue.turns
    scores: list[float] = []
    for index, turn in enumerate(turns[:-1]):
        following = turns[index + 1]
        if turn.speaker is Speaker.user and following.speaker is Speaker.mentor:
            scores.append(scorer.similarity(turn.text, following.text))
    if not scores:
        return 1.0, 0
    return round(_mean(scores), 6), len(scores)


def score_consistency(
    dialogue: Dialogue,
    scorer: SimilarityScorer | None = None,
) -> ConsistencyResult:
    """Compute all three behavioral consistency sub-scores for one dialogue."""
    scorer = scorer or default_scorer()
    p2l, n_p2l = prompt_to_line(dialogue, scorer)
    l2l, n_l2l = line_to_line(dialogue, scorer)
    qa, n_qa = qa_consistency(dialogue, scorer)
    return ConsistencyResult(
        prompt_to_line=p2l,
        line_to_line=l2l,
        qa_consistency=qa,
        n_prompt_to_line=n_p2l,
        n_line_to_line=n_l2l,
        n_qa_pairs=n_qa,
    )
