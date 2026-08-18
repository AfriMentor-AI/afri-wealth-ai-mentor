"""Persona-vector probing — the latent-space layer of the eval suite (card C3.3).

The behavioral metrics (:mod:`evaluation.metrics`, LLM-as-judge) and the C3.2
consistency job measure persona expression from the model's **outputs**. This
module measures it from the model's **internal activations** — the third,
"latent-space probing" layer of the metric suite described in
``research/afrimentor-Research-paper/docs/paper-scope-decision.md``.

Method (after Chen et al. 2025, *Persona Vectors*, and Frising et al. 2025,
*Linear Personality Probing … A Big Five Study*):

  1. The CHIOMA target profile (``chioma_profile.v1.json``) gives, per trait, a
     set of ``markers`` (phrases that express the trait) and ``counter_markers``
     (phrases that express its opposite). These are the contrastive material.
  2. Each marker is embedded in a small set of neutral carrier sentences.
     Positives and negatives use the **identical** carriers, so template /
     formatting activation cancels in the difference below.
  3. A **persona vector** for a trait, at each layer, is the normalized
     difference of class means: ``normalize(mean(act⁺) − mean(act⁻))``.
  4. A **linear probe** scores how strongly a response expresses a trait by
     projecting the response's pooled activation onto the unit persona vector.
  5. A **separation diagnostic** on held-out markers (projection threshold at the
     positive/negative midpoint) shows the vector actually discriminates the
     trait — the "the vectors are real" evidence.

The heavy model lives behind the :data:`ActivationFn` seam — a callable mapping a
text to its per-layer pooled hidden states. The real implementation
(:class:`HFActivationExtractor`) imports torch/transformers/peft **lazily**, so
this module and its entire extract → probe → diagnose pipeline import and run on a
bare CPU interpreter (numpy only) with an injected fake activation function.

Scope: probing / monitoring only. Activation *steering* (adding a persona vector
during generation) is deferred to future work; the :class:`PersonaVectorSet` this
module produces is steering-ready.
"""
from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

logger = logging.getLogger(__name__)

# research/ root (this file is research/evaluation/persona_probe.py)
_RESEARCH_ROOT = Path(__file__).resolve().parents[1]

#: Machine-readable CHIOMA target profile published by card C1.4.
DEFAULT_PROFILE_PATH = (
    _RESEARCH_ROOT.parent
    / "services"
    / "persona-prompt-service"
    / "data"
    / "chioma_profile.v1.json"
)

#: An activation function maps a text -> per-layer pooled hidden states, an array
#: of shape ``(n_layers, hidden_dim)``. Injectable so the pipeline is testable
#: offline without loading a model.
ActivationFn = Callable[[str], np.ndarray]

#: Neutral carrier sentences a marker phrase is dropped into. The SAME set is used
#: for positive markers and negative counter-markers, so the carrier's own
#: activation cancels in the diff-of-means and only the marker content remains.
CARRIER_TEMPLATES: tuple[str, ...] = (
    "{phrase}",
    "As your mentor, let me say: {phrase}.",
    "Here is my honest advice — {phrase}.",
    "When it comes to your money and your business, {phrase}.",
)

#: Minimal built-in profile so the module runs even when the JSON is unavailable.
#: Two traits, each with a handful of markers / counter-markers — enough to build
#: contrastive pairs and exercise the full pipeline.
_FALLBACK_PROFILE: dict = {
    "profile_id": "chioma",
    "profile_version": "fallback",
    "traits": [
        {
            "key": "conscientiousness",
            "label": "Conscientiousness",
            "markers": ["make a plan", "set a deadline", "track it every week",
                        "commit to a specific target", "review your budget"],
            "counter_markers": ["maybe someday", "we will see", "no rush",
                                "figure it out later", "roughly whenever"],
        },
        {
            "key": "urgency",
            "label": "Urgency & Action Bias",
            "markers": ["start today", "take the first step now", "do not wait",
                        "act this morning", "execute immediately"],
            "counter_markers": ["wait for next year", "delay it", "sleep on it forever",
                                "hesitate for now", "put it off"],
        },
    ],
    "distinctive_traits": [],
}


# ── Profile loading ────────────────────────────────────────────────────────────

def load_persona_profile(path: str | Path = DEFAULT_PROFILE_PATH) -> dict:
    """Load the CHIOMA target profile JSON, falling back to a built-in profile.

    The profile is the C1.4 machine-readable spec; each trait carries ``markers``
    and ``counter_markers`` (both optional per the profile schema). Returns the
    :data:`_FALLBACK_PROFILE` when the file is missing or unreadable, so the
    probing pipeline always has contrastive material to work with.
    """
    path = Path(path)
    try:
        with open(path) as f:
            profile = json.load(f)
        logger.info("Loaded persona profile %s (%s)",
                    profile.get("profile_id"), profile.get("profile_version"))
        return profile
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("persona profile unavailable at %s (%s) — using fallback", path, exc)
        return _FALLBACK_PROFILE


def iter_traits(profile: dict) -> list[dict]:
    """All scorable traits (Big Five ``traits`` + ``distinctive_traits``)."""
    return list(profile.get("traits", [])) + list(profile.get("distinctive_traits", []))


# ── Contrastive pair construction ───────────────────────────────────────────────

def _expand(phrases: list[str], templates: tuple[str, ...]) -> list[str]:
    """Drop each phrase into every carrier template."""
    out: list[str] = []
    for phrase in phrases:
        p = phrase.strip()
        if not p:
            continue
        for tmpl in templates:
            out.append(tmpl.format(phrase=p))
    return out


def build_contrastive_pairs(
    profile: dict,
    *,
    templates: tuple[str, ...] = CARRIER_TEMPLATES,
    heldout_fraction: float = 0.3,
    max_markers: int | None = None,
) -> dict[str, dict]:
    """Build per-trait positive / negative text sets from markers & counter-markers.

    For each trait, markers and counter-markers are split into a train slice (used
    to build the persona vector) and a held-out slice (used by the separation
    diagnostic), then each phrase is expanded across the carrier ``templates``.

    Returns ``{trait_key: {"label", "train": {"positive", "negative"},
    "heldout": {"positive", "negative"}}}``. Traits with no markers or no
    counter-markers are skipped (a diff-of-means needs both sides), and a warning
    is logged so the gap is visible rather than silent.
    """
    if not 0.0 <= heldout_fraction < 1.0:
        raise ValueError("heldout_fraction must be in [0.0, 1.0)")

    pairs: dict[str, dict] = {}
    for trait in iter_traits(profile):
        key = trait.get("key")
        markers = [m for m in trait.get("markers", []) if m and m.strip()]
        counters = [m for m in trait.get("counter_markers", []) if m and m.strip()]
        if not key or not markers or not counters:
            logger.warning("trait %r skipped: needs both markers and counter_markers", key)
            continue
        if max_markers:
            markers, counters = markers[:max_markers], counters[:max_markers]

        def _split(items: list[str]) -> tuple[list[str], list[str]]:
            # Deterministic tail split; keep >=1 sample in train, and only hold out
            # when there are enough items for both slices to be non-empty.
            n_held = int(round(len(items) * heldout_fraction))
            n_held = min(n_held, len(items) - 1)
            if n_held <= 0:
                return items, []
            return items[:-n_held], items[-n_held:]

        m_train, m_held = _split(markers)
        c_train, c_held = _split(counters)

        pairs[key] = {
            "label": trait.get("label", key),
            "train": {
                "positive": _expand(m_train, templates),
                "negative": _expand(c_train, templates),
            },
            "heldout": {
                "positive": _expand(m_held, templates),
                "negative": _expand(c_held, templates),
            },
        }
    return pairs


# ── Persona vectors ──────────────────────────────────────────────────────────

def _stack_activations(texts: list[str], activation_fn: ActivationFn) -> np.ndarray:
    """Activations for ``texts`` stacked as ``(n_texts, n_layers, hidden_dim)``."""
    acts = [np.asarray(activation_fn(t), dtype=np.float64) for t in texts]
    return np.stack(acts, axis=0)


def _unit_normalize(vecs: np.ndarray, axis: int = -1, eps: float = 1e-12) -> np.ndarray:
    """L2-normalize along ``axis``; zero vectors are left as zeros."""
    norm = np.linalg.norm(vecs, axis=axis, keepdims=True)
    return vecs / np.maximum(norm, eps)


@dataclass
class PersonaVectorSet:
    """Per-trait persona vectors, one direction per layer.

    ``vectors[trait_key]`` is a unit-normalized array of shape
    ``(n_layers, hidden_dim)``. ``raw`` holds the un-normalized diff-of-means for
    inspection. Persisted as a single ``.npz`` plus a sidecar ``.json`` of metadata.
    """

    vectors: dict[str, np.ndarray]
    raw: dict[str, np.ndarray] = field(default_factory=dict)
    n_layers: int = 0
    hidden_dim: int = 0
    pooling: str = "mean"
    profile_version: str = "unknown"
    best_layer: dict[str, int] = field(default_factory=dict)

    @property
    def traits(self) -> list[str]:
        return list(self.vectors.keys())

    def save(self, path: str | Path) -> None:
        """Write vectors to ``path`` (.npz) and metadata to ``path`` + ``.meta.json``."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        arrays = {f"vec::{k}": v for k, v in self.vectors.items()}
        arrays.update({f"raw::{k}": v for k, v in self.raw.items()})
        np.savez(path, **arrays)
        meta = {
            "n_layers": self.n_layers,
            "hidden_dim": self.hidden_dim,
            "pooling": self.pooling,
            "profile_version": self.profile_version,
            "best_layer": self.best_layer,
            "traits": self.traits,
        }
        Path(str(path) + ".meta.json").write_text(json.dumps(meta, indent=2))

    @classmethod
    def load(cls, path: str | Path) -> "PersonaVectorSet":
        path = Path(path)
        npz_path = path if path.suffix == ".npz" else Path(str(path) + ".npz")
        data = np.load(npz_path)
        vectors = {k[5:]: data[k] for k in data.files if k.startswith("vec::")}
        raw = {k[5:]: data[k] for k in data.files if k.startswith("raw::")}
        meta_path = Path(str(npz_path)[:-4] + ".npz.meta.json")
        if not meta_path.exists():
            meta_path = Path(str(path) + ".meta.json")
        meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
        return cls(
            vectors=vectors,
            raw=raw,
            n_layers=meta.get("n_layers", 0),
            hidden_dim=meta.get("hidden_dim", 0),
            pooling=meta.get("pooling", "mean"),
            profile_version=meta.get("profile_version", "unknown"),
            best_layer={k: int(v) for k, v in meta.get("best_layer", {}).items()},
        )


def extract_persona_vectors(
    pairs: dict[str, dict],
    activation_fn: ActivationFn,
    *,
    pooling: str = "mean",
    profile_version: str = "unknown",
) -> PersonaVectorSet:
    """Extract per-trait, per-layer persona vectors by contrastive diff-of-means.

    For each trait, the vector at layer ``l`` is
    ``normalize(mean_p act⁺[l] − mean_n act⁻[l])`` over the trait's *train* texts.
    ``activation_fn`` is injectable, so this runs offline with a fake extractor.
    """
    vectors: dict[str, np.ndarray] = {}
    raw: dict[str, np.ndarray] = {}
    n_layers = hidden_dim = 0

    for key, spec in pairs.items():
        pos = spec["train"]["positive"]
        neg = spec["train"]["negative"]
        if not pos or not neg:
            logger.warning("trait %r has an empty train slice — skipping", key)
            continue
        pos_acts = _stack_activations(pos, activation_fn)   # (n_pos, L, H)
        neg_acts = _stack_activations(neg, activation_fn)   # (n_neg, L, H)
        diff = pos_acts.mean(axis=0) - neg_acts.mean(axis=0)  # (L, H)
        raw[key] = diff
        vectors[key] = _unit_normalize(diff, axis=-1)
        n_layers, hidden_dim = diff.shape

    return PersonaVectorSet(
        vectors=vectors,
        raw=raw,
        n_layers=n_layers,
        hidden_dim=hidden_dim,
        pooling=pooling,
        profile_version=profile_version,
    )


# ── Linear probe + separation diagnostic ────────────────────────────────────────

class PersonaProbe:
    """Score persona-trait expression by projecting activations onto persona vectors.

    ``score_trait(activations, trait, layer)`` projects a response's pooled
    activation at ``layer`` onto the unit persona vector for ``trait`` — a signed
    scalar where higher means stronger expression of that CHIOMA trait. With no
    explicit layer, the trait's selected ``best_layer`` (if any) is used, else the
    set's default.
    """

    def __init__(self, vector_set: PersonaVectorSet, default_layer: int | None = None):
        self.vs = vector_set
        self.default_layer = default_layer

    def _layer_for(self, trait: str, layer: int | None) -> int:
        if layer is not None:
            return layer
        if trait in self.vs.best_layer:
            return self.vs.best_layer[trait]
        if self.default_layer is not None:
            return self.default_layer
        return self.vs.n_layers - 1  # last layer by default

    def score_trait(self, activations: np.ndarray, trait: str, layer: int | None = None) -> float:
        if trait not in self.vs.vectors:
            raise KeyError(f"no persona vector for trait {trait!r}")
        activations = np.asarray(activations, dtype=np.float64)
        lyr = self._layer_for(trait, layer)
        return float(np.dot(activations[lyr], self.vs.vectors[trait][lyr]))

    def score_all(self, activations: np.ndarray, layer: int | None = None) -> dict[str, float]:
        return {t: self.score_trait(activations, t, layer) for t in self.vs.traits}


def _separation_at_layer(pos_proj: np.ndarray, neg_proj: np.ndarray) -> tuple[float, float]:
    """Classification accuracy + mean margin for positive vs negative projections.

    Threshold is the midpoint of the class-mean projections; accuracy is the
    fraction of held-out samples on the correct side; margin is
    ``mean(pos) − mean(neg)`` (positive when the vector points the expected way).
    """
    threshold = (pos_proj.mean() + neg_proj.mean()) / 2.0
    correct = int((pos_proj > threshold).sum() + (neg_proj <= threshold).sum())
    total = len(pos_proj) + len(neg_proj)
    accuracy = correct / total if total else 0.0
    margin = float(pos_proj.mean() - neg_proj.mean())
    return accuracy, margin


def probe_separation(
    vector_set: PersonaVectorSet,
    pairs: dict[str, dict],
    activation_fn: ActivationFn,
) -> dict[str, dict]:
    """Held-out separation per trait / layer — the "vectors are real" diagnostic.

    Projects each trait's *held-out* positives and negatives onto its persona
    vector at every layer and reports accuracy + margin. Falls back to the train
    slice for a trait whose held-out slice is empty (few markers), flagging it.
    Returns ``{trait: {"per_layer": [{layer, accuracy, margin}], "best_layer",
    "best_accuracy", "best_margin", "slice"}}``.
    """
    report: dict[str, dict] = {}
    for trait, vec in vector_set.vectors.items():
        spec = pairs.get(trait, {})
        held = spec.get("heldout", {})
        pos_texts, neg_texts = held.get("positive", []), held.get("negative", [])
        slice_used = "heldout"
        if not pos_texts or not neg_texts:
            train = spec.get("train", {})
            pos_texts, neg_texts = train.get("positive", []), train.get("negative", [])
            slice_used = "train"
        if not pos_texts or not neg_texts:
            continue

        pos_acts = _stack_activations(pos_texts, activation_fn)  # (n, L, H)
        neg_acts = _stack_activations(neg_texts, activation_fn)

        per_layer = []
        for lyr in range(vec.shape[0]):
            pos_proj = pos_acts[:, lyr, :] @ vec[lyr]
            neg_proj = neg_acts[:, lyr, :] @ vec[lyr]
            acc, margin = _separation_at_layer(pos_proj, neg_proj)
            per_layer.append({"layer": lyr, "accuracy": acc, "margin": margin})

        best = max(per_layer, key=lambda r: (r["accuracy"], r["margin"]))
        vector_set.best_layer[trait] = best["layer"]
        report[trait] = {
            "per_layer": per_layer,
            "best_layer": best["layer"],
            "best_accuracy": best["accuracy"],
            "best_margin": best["margin"],
            "slice": slice_used,
        }
    return report


def select_best_layers(
    vector_set: PersonaVectorSet,
    pairs: dict[str, dict],
    activation_fn: ActivationFn,
) -> dict[str, int]:
    """Populate and return ``vector_set.best_layer`` from the separation diagnostic."""
    probe_separation(vector_set, pairs, activation_fn)
    return dict(vector_set.best_layer)


# ── MLflow logging ───────────────────────────────────────────────────────────

def log_probe_to_mlflow(report: dict[str, dict]) -> None:
    """Log the separation diagnostic to the active MLflow run under stable keys.

    Per trait: ``probe_sep_acc_<trait>``, ``probe_sep_margin_<trait>``,
    ``probe_best_layer_<trait>``. Plus run-level means ``probe_sep_acc_mean`` /
    ``probe_sep_margin_mean`` so the latent layer sits beside the behavioral
    ``avg_*`` metrics C1/C2/C3 log. Imported lazily to keep the module CPU-clean.
    """
    if not report:
        return
    import mlflow

    accs, margins = [], []
    for trait, r in report.items():
        mlflow.log_metric(f"probe_sep_acc_{trait}", r["best_accuracy"])
        mlflow.log_metric(f"probe_sep_margin_{trait}", r["best_margin"])
        mlflow.log_metric(f"probe_best_layer_{trait}", r["best_layer"])
        accs.append(r["best_accuracy"])
        margins.append(r["best_margin"])
    if accs:
        mlflow.log_metric("probe_sep_acc_mean", sum(accs) / len(accs))
        mlflow.log_metric("probe_sep_margin_mean", sum(margins) / len(margins))


# ── Real activation extractor (GPU / model node) ─────────────────────────────────

class HFActivationExtractor:
    """Extract per-layer pooled hidden states from a base model (+ optional adapter).

    The real :data:`ActivationFn`. torch / transformers / peft are imported lazily
    inside :meth:`_ensure_loaded`, so importing this class costs nothing on CPU and
    the probing pipeline stays testable without the ML stack installed.

    ``__call__(text)`` runs a forward pass with ``output_hidden_states=True`` and
    pools the token hidden states per layer (mean over the attention-masked tokens,
    or the last non-pad token when ``pooling='last'``), returning a numpy array of
    shape ``(n_layers, hidden_dim)``.
    """

    def __init__(
        self,
        base_model_id: str,
        adapter_path: str | None = None,
        *,
        pooling: str = "mean",
        load_in_4bit: bool = True,
        max_length: int = 256,
    ) -> None:
        if pooling not in ("mean", "last"):
            raise ValueError("pooling must be 'mean' or 'last'")
        self.base_model_id = base_model_id
        self.adapter_path = adapter_path
        self.pooling = pooling
        self.load_in_4bit = load_in_4bit
        self.max_length = max_length
        self._model = None
        self._tokenizer = None

    def _ensure_loaded(self) -> None:
        if self._model is not None:
            return
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        kwargs: dict = {"device_map": "auto", "output_hidden_states": True}
        if self.load_in_4bit:
            from transformers import BitsAndBytesConfig

            kwargs["quantization_config"] = BitsAndBytesConfig(
                load_in_4bit=True,
                bnb_4bit_compute_dtype=torch.bfloat16,
                bnb_4bit_quant_type="nf4",
                bnb_4bit_use_double_quant=True,
            )

        model = AutoModelForCausalLM.from_pretrained(self.base_model_id, **kwargs)
        if self.adapter_path:
            from peft import PeftModel

            model = PeftModel.from_pretrained(model, self.adapter_path)
        model.eval()

        tokenizer = AutoTokenizer.from_pretrained(self.base_model_id)
        if tokenizer.pad_token is None:
            tokenizer.pad_token = tokenizer.eos_token

        self._model, self._tokenizer = model, tokenizer

    def __call__(self, text: str) -> np.ndarray:
        self._ensure_loaded()
        import torch

        enc = self._tokenizer(
            text,
            return_tensors="pt",
            truncation=True,
            max_length=self.max_length,
        ).to(self._model.device)

        with torch.no_grad():
            out = self._model(**enc, output_hidden_states=True)

        # hidden_states: tuple of (n_layers+1) tensors, each (1, seq, hidden)
        mask = enc["attention_mask"][0].bool()  # (seq,)
        pooled_layers = []
        for hs in out.hidden_states:
            h = hs[0]  # (seq, hidden)
            if self.pooling == "last":
                idx = int(mask.nonzero()[-1]) if mask.any() else h.shape[0] - 1
                vec = h[idx]
            else:
                vec = h[mask].mean(dim=0) if mask.any() else h.mean(dim=0)
            pooled_layers.append(vec.float().cpu().numpy())

        return np.stack(pooled_layers, axis=0)  # (n_layers, hidden_dim)
