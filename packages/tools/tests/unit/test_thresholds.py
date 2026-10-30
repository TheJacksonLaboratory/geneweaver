"""A run's threshold choice as requests carry it (curation, 2026-10-16)."""

import pytest
from geneweaver.tools.abba import ABBAInput
from geneweaver.tools.thresholds import ThresholdOptions
from pydantic import ValidationError


def test_every_gene_unless_a_threshold_is_chosen() -> None:
    """The default is every gene."""
    options = ThresholdOptions()
    assert options.threshold == "none"
    assert options.threshold_choice() == {"threshold": "none"}
    assert options.membership_kwargs() == {"mode": "none"}


def test_custom_carries_only_the_cutoffs_given() -> None:
    """Only the cutoffs given are echoed and applied."""
    options = ThresholdOptions(threshold="custom", p_value=0.01, effect_low=-2)
    assert options.threshold_choice() == {"threshold": "custom", "p_value": 0.01, "effect_low": -2}
    assert options.membership_kwargs() == {"mode": "custom", "p_value": 0.01, "effect_low": -2}


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        ({"threshold": "uploader", "p_value": 0.05}, "only with threshold 'custom'"),
        ({"p_value": 0.05}, "only with threshold 'custom'"),
        ({"threshold": "custom", "correlation_low": 0.9, "correlation_high": 0.1}, "above"),
        ({"threshold": "custom", "q_value": 2}, "less than or equal to 1"),
        ({"threshold": "sometimes"}, "threshold"),
    ],
)
def test_a_choice_that_cannot_mean_one_thing_is_refused(fields, message) -> None:
    """Ambiguous or inverted choices are refused, naming the problem."""
    with pytest.raises(ValidationError, match=message):
        ThresholdOptions(**fields)


def test_abba_takes_the_same_choice() -> None:
    """ABBA's search reads membership the way every other tool does."""
    request = ABBAInput(genes=["Drd2"], threshold="custom", q_value=0.05)
    assert request.membership_kwargs() == {"mode": "custom", "q_value": 0.05}
