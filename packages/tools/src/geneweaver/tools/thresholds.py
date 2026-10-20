"""A run's gene set threshold choice, as requests carry it.

Curation decided (Tessa, Heidi; 2026-10-16) that a gene set is not inherently thresholded:
it is its full list of genes and scores, and whoever runs an analysis may threshold it for
that run. The rule itself -- which genes each choice keeps -- is applied in the database
(`geneweaver.db.query.membership`); this is the request's shape and its checks, shared by
the API's tool runs and ABBA's input so they cannot drift.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

ThresholdMode = Literal["none", "uploader", "custom"]

_CUTOFFS = (
    "p_value",
    "q_value",
    "correlation_low",
    "correlation_high",
    "effect_low",
    "effect_high",
)


class ThresholdOptions(BaseModel):
    """Which of each gene set's genes take part in a run."""

    threshold: ThresholdMode = Field(
        default="none",
        description=(
            "'none' (default): every gene in each gene set. 'uploader': each gene set's own "
            "stored threshold. 'custom': the cutoffs given here, per score type."
        ),
    )
    p_value: float | None = Field(
        default=None, ge=0, le=1, description="custom: p-value gene sets keep genes <= this."
    )
    q_value: float | None = Field(
        default=None, ge=0, le=1, description="custom: q-value gene sets keep genes <= this."
    )
    correlation_low: float | None = Field(
        default=None, description="custom: correlation gene sets keep genes >= this."
    )
    correlation_high: float | None = Field(
        default=None, description="custom: correlation gene sets keep genes <= this."
    )
    effect_low: float | None = Field(
        default=None, description="custom: effect gene sets keep genes >= this."
    )
    effect_high: float | None = Field(
        default=None, description="custom: effect gene sets keep genes <= this."
    )

    @model_validator(mode="after")
    def _check_cutoffs(self) -> "ThresholdOptions":
        """Cutoffs with ``custom`` and only then; ranges the right way round.

        ``custom`` with no cutoff would cut nothing yet be reported as thresholded, so it is
        refused, as the analysis page refuses it.
        """
        given = [name for name in _CUTOFFS if getattr(self, name) is not None]
        if given and self.threshold != "custom":
            raise ValueError(
                f"Cutoffs ({', '.join(given)}) apply only with threshold 'custom', "
                f"not {self.threshold!r}."
            )
        if self.threshold == "custom" and not given:
            raise ValueError(
                "threshold 'custom' needs at least one cutoff (p_value, q_value, "
                "correlation_low/high, effect_low/high); for every gene, use 'none'."
            )
        for name in ("correlation", "effect"):
            low, high = getattr(self, f"{name}_low"), getattr(self, f"{name}_high")
            if low is not None and high is not None and low > high:
                raise ValueError(f"{name}_low ({low}) is above {name}_high ({high}).")
        return self

    def threshold_choice(self) -> dict[str, Any]:
        """The choice alone, for echoing with a result: the mode and any cutoffs given."""
        return {"threshold": self.threshold} | {
            name: getattr(self, name) for name in _CUTOFFS if getattr(self, name) is not None
        }

    def membership_kwargs(self) -> dict[str, Any]:
        """Keyword arguments for `geneweaver.db.query.membership.Thresholds`."""
        choice = self.threshold_choice()
        return {"mode": choice.pop("threshold"), **choice}
