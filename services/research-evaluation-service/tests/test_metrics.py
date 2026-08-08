"""Unit tests for the personality-consistency metric suite v0 (card C1.3)."""

import json

import pytest

from app.metrics.consistency import (
    line_to_line,
    prompt_to_line,
    qa_consistency,
    score_consistency,
)
from app.metrics.profile import (
    LEVEL_VALUES,
    TargetProfile,
    TraitTarget,
    load_profile,
)
from app.metrics.report import (
    EvaluationReport,
    ReportBundle,
    score_dialogue,
    score_dialogues,
)
from app.metrics.schemas import (
    ConsistencyResult,
    Dialogue,
    ProbeResponse,
    Speaker,
    TraitFitResult,
    Turn,
)
from app.metrics.scoring import (
    LexicalScorer,
    SimilarityScorer,
    cosine,
    cosine_dense,
    tokenize,
)
from app.metrics.trait_fit import (
    NEUTRAL,
    _marker_hits,
    _saturate,
    estimate_trait_value,
    score_dialogue_traits,
    score_probe_traits,
)
from scripts.run_metrics import (
    DEFAULT_DIALOGUE_DIR,
    DEFAULT_PROBE_PATH,
    load_dialogues,
    load_probes,
    main,
    render_json,
    render_text,
)

# --- Profile Tests ---


def test_level_values():
    assert LEVEL_VALUES["VERY_LOW"] == 0.05
    assert LEVEL_VALUES["HIGH"] == 0.85
    assert LEVEL_VALUES["VERY_HIGH"] == 0.95


def test_load_profile():
    profile = load_profile()
    assert isinstance(profile, TargetProfile)
    assert profile.profile_id == "chioma"
    assert len(profile.traits) == 5
    assert len(profile.distinctive_traits) == 4
    assert len(profile.all_traits) == 9

    target_vec = profile.target_vector()
    assert len(target_vec) == 9
    assert target_vec[0] == 0.95  # conscientiousness target (VERY_HIGH = 0.95)

    c_trait = profile.by_key("conscientiousness")
    assert c_trait is not None
    assert c_trait.label == "Conscientiousness"


def test_load_profile_invalid_level(tmp_path):
    bad_data = {
        "schema_version": "v0",
        "profile_id": "bad",
        "profile_version": "v0",
        "display_name": "Bad Profile",
        "traits": [
            {
                "key": "bad_trait",
                "label": "Bad",
                "target_level": "SUPER_HIGH",
                "behaviour": "test",
            }
        ],
    }
    bad_file = tmp_path / "bad.json"
    bad_file.write_text(json.dumps(bad_data))
    with pytest.raises(ValueError, match="unknown target_level"):
        load_profile(bad_file)


# --- Scoring Backend Tests ---


def test_tokenize():
    tokens = tokenize("Hello, world! This is a TEST.")
    assert "hello" in tokens
    assert "world" in tokens
    assert "test" in tokens
    assert "this" not in tokens  # stopword removed

    tokens_all = tokenize("Hello world!", drop_stopwords=False)
    assert tokens_all == ["hello", "world"]


def test_cosine_sparse():
    v1 = {"a": 1.0, "b": 2.0}
    v2 = {"a": 1.0, "b": 2.0}
    assert pytest.approx(cosine(v1, v2), 0.001) == 1.0

    v3 = {"c": 1.0}
    assert cosine(v1, v3) == 0.0
    assert cosine({}, v1) == 0.0


def test_cosine_dense():
    assert pytest.approx(cosine_dense([1.0, 0.0], [1.0, 0.0])) == 1.0
    assert pytest.approx(cosine_dense([1.0, 0.0], [0.0, 1.0])) == 0.0
    assert cosine_dense([], []) == 0.0

    with pytest.raises(ValueError, match="vector length mismatch"):
        cosine_dense([1.0], [1.0, 2.0])


def test_lexical_scorer():
    scorer = LexicalScorer()
    assert isinstance(scorer, SimilarityScorer)
    sim = scorer.similarity("budget and planning", "budget allocation planning")
    assert sim > 0.0

    matrix = scorer.similarity_matrix(["budget plan", "savings investment", "budget plan"])
    assert len(matrix) == 3
    assert matrix[0][0] == 1.0
    assert matrix[0][2] == 1.0


# --- Trait Fit Tests ---


def test_marker_hits_and_saturate():
    assert _saturate(0) == 0.0
    assert _saturate(3) == 0.5
    assert _marker_hits("We must build a solid budget", ["budget", "solid budget"]) == 2


def test_estimate_trait_value():
    trait = TraitTarget(
        key="test",
        label="Test",
        target_level="HIGH",
        behaviour="testing",
        markers=["good", "great"],
        counter_markers=["bad", "terrible"],
    )
    val, evid = estimate_trait_value("This is neutral", trait)
    assert val == NEUTRAL
    assert evid == 0

    val_pos, evid_pos = estimate_trait_value("Good and great result", trait)
    assert val_pos > NEUTRAL
    assert evid_pos == 2


def test_score_dialogue_traits():
    d = Dialogue(
        dialogue_id="d1",
        system_prompt="Be a helpful mentor",
        turns=[
            Turn(speaker=Speaker.user, text="How to budget?"),
            Turn(speaker=Speaker.mentor, text="Create a systematic savings budget plan."),
        ],
    )
    res = score_dialogue_traits(d)
    assert isinstance(res, TraitFitResult)
    assert res.source == "dialogue"
    assert -1.0 <= res.cosine_similarity <= 1.0
    assert res.worst_trait is not None


def test_score_probe_traits():
    probes = [
        ProbeResponse(
            probe_id="p1",
            trait="conscientiousness",
            question="Do you plan?",
            answer="I am very systematic and keep detailed budgets.",
        ),
        ProbeResponse(
            probe_id="p2",
            trait="conscientiousness",
            question="Do you leave things to chance?",
            answer="I never leave anything to chance.",
            reverse_scored=True,
        ),
    ]
    res = score_probe_traits(probes)
    assert isinstance(res, TraitFitResult)
    assert res.source == "probes"
    assert len(res.per_trait) == 1
    assert res.per_trait[0].trait == "conscientiousness"


def test_score_probe_traits_invalid_trait():
    probes = [
        ProbeResponse(
            probe_id="p1",
            trait="nonexistent_trait",
            question="Q?",
            answer="A",
        )
    ]
    with pytest.raises(ValueError, match="targets unknown trait"):
        score_probe_traits(probes)


# --- Consistency Tests ---


def test_consistency_metrics():
    d = Dialogue(
        dialogue_id="d1",
        system_prompt="Provide structured financial guidance and active cashflow steps.",
        turns=[
            Turn(speaker=Speaker.user, text="How do I manage financial cashflow?"),
            Turn(
                speaker=Speaker.mentor,
                text="First, audit financial cashflow and create structured guidance steps.",
            ),
            Turn(speaker=Speaker.user, text="What is step two for financial guidance?"),
            Turn(
                speaker=Speaker.mentor,
                text="Second, allocate financial reserves and structured guidance steps.",
            ),
        ],
    )

    p2l, n_p2l = prompt_to_line(d)
    assert n_p2l == 2
    assert p2l > 0.0

    l2l, n_l2l = line_to_line(d)
    assert n_l2l == 1
    assert l2l > 0.0

    qa, n_qa = qa_consistency(d)
    assert n_qa == 2
    assert qa > 0.0

    c_res = score_consistency(d)
    assert isinstance(c_res, ConsistencyResult)
    assert 0.0 <= c_res.aggregate <= 1.0


def test_consistency_edge_cases():
    # Single mentor turn -> line_to_line returns 1.0 with n=0
    d_single = Dialogue(
        dialogue_id="d_single",
        system_prompt="Prompt",
        turns=[Turn(speaker=Speaker.mentor, text="Only one turn here.")],
    )
    c_res = score_consistency(d_single)
    assert c_res.n_line_to_line == 0
    assert c_res.line_to_line == 1.0
    assert c_res.n_qa_pairs == 0
    assert c_res.qa_consistency == 1.0


# --- Report & CLI Tests ---


def test_score_dialogue_and_bundle():
    d1 = Dialogue(
        dialogue_id="d1",
        system_prompt="System prompt mentor",
        turns=[
            Turn(speaker=Speaker.user, text="Hi"),
            Turn(speaker=Speaker.mentor, text="Hello, let us create a budget plan."),
        ],
    )
    d2 = Dialogue(
        dialogue_id="d2",
        system_prompt="System prompt mentor",
        turns=[
            Turn(speaker=Speaker.user, text="Advice"),
            Turn(speaker=Speaker.mentor, text="Focus on emergency funds and savings."),
        ],
    )

    rep = score_dialogue(d1)
    assert isinstance(rep, EvaluationReport)
    assert rep.dialogue_id == "d1"
    assert 0.0 <= rep.composite_score <= 1.0

    row = rep.summary_row()
    assert row["dialogue_id"] == "d1"
    assert "composite" in row

    bundle = score_dialogues([d1, d2])
    assert isinstance(bundle, ReportBundle)
    assert len(bundle.reports) == 2
    assert bundle.mean_composite > 0.0
    assert len(bundle.summary_rows()) == 2


def test_run_metrics_script_helpers():
    dialogues = load_dialogues(DEFAULT_DIALOGUE_DIR)
    assert len(dialogues) >= 3

    probes = load_probes(DEFAULT_PROBE_PATH)
    assert len(probes) > 0

    bundle = score_dialogues(dialogues)
    text_out = render_text(bundle)
    assert "AfriMentor AI" in text_out
    assert "toy-001-on-persona" in text_out

    json_out = render_json(bundle)
    parsed = json.loads(json_out)
    assert parsed["suite_version"] == "v0"
    assert parsed["dialogue_count"] >= 3


def test_main_cli(tmp_path):
    out_file = tmp_path / "test_out.json"
    ret = main(["--out", str(out_file), "--format", "json"])
    assert ret == 0
    assert out_file.exists()

    data = json.loads(out_file.read_text())
    assert data["card"] == "C1.3"
