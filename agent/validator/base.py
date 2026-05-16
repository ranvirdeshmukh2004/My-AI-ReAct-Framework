"""
base.py — Validation Result Dataclasses
=========================================
Structured containers for all validator outputs.

Primary: QualityResult — 5-criteria evaluation of every response.
Bonus: MathResult — deterministic math re-verification (when applicable).
"""

from dataclasses import dataclass, field
from datetime import datetime


# ============================================
# Quality Evaluation (always runs)
# ============================================

@dataclass
class QualityResult:
    """
    Response quality evaluation across 5 universal criteria.
    Each scored 1-10 by an independent evaluator model.
    """
    relevance: int = 5          # Does it address the question?
    completeness: int = 5       # Does it cover all parts?
    accuracy: int = 5           # Are facts correct?
    clarity: int = 5            # Is it well-organized?
    helpfulness: int = 5        # Is it genuinely useful?
    reasoning: str = ""         # Evaluator's reasoning
    evaluator_model: str = ""   # Which model evaluated

    @property
    def weighted_score(self) -> float:
        """
        Weighted average:
        Relevance 25%, Completeness 25%, Accuracy 20%, Clarity 15%, Helpfulness 15%
        """
        return round(
            self.relevance * 0.25 +
            self.completeness * 0.25 +
            self.accuracy * 0.20 +
            self.clarity * 0.15 +
            self.helpfulness * 0.15,
            1,
        )


# ============================================
# Math Re-Verification (bonus, when applicable)
# ============================================

@dataclass
class MathCheckItem:
    """A single math calculation verification."""
    expression: str = ""
    agent_result: str = ""
    verified_result: str = ""
    match: bool = True


@dataclass
class MathResult:
    """Math re-verification result."""
    score: int = 10                 # 0-10
    total_checks: int = 0
    passed: int = 0
    failed: int = 0
    checks: list = field(default_factory=list)  # list of MathCheckItem dicts
    skipped: bool = False           # True if no math steps found


# ============================================
# Combined Validation Report
# ============================================

@dataclass
class ValidationReport:
    """Combined validation report — quality-first scoring."""
    quality: QualityResult | None = None
    math: MathResult | None = None
    overall_score: float = 0.0      # Weighted 0-10
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def __post_init__(self):
        """Compute overall score from quality + math bonus."""
        if self.overall_score == 0.0:
            self._compute_overall()

    def _compute_overall(self):
        """
        Overall score = Quality weighted average.
        If math was checked and failed, apply a penalty.
        If math was checked and passed, no bonus (it's expected).
        """
        if not self.quality:
            self.overall_score = 0.0
            return

        base = self.quality.weighted_score

        # Math penalty: if math checks failed, reduce score
        if self.math and not self.math.skipped and self.math.total_checks > 0:
            math_pass_rate = self.math.passed / self.math.total_checks
            if math_pass_rate < 1.0:
                # Penalty proportional to failure rate (max -2 points)
                penalty = (1 - math_pass_rate) * 2.0
                base = max(1.0, base - penalty)

        self.overall_score = round(base, 1)

    def to_dict(self) -> dict:
        """Convert to a JSON-serializable dict for session state storage."""
        result = {
            "overall_score": self.overall_score,
            "timestamp": self.timestamp,
        }

        if self.quality:
            result["quality"] = {
                "relevance": self.quality.relevance,
                "completeness": self.quality.completeness,
                "accuracy": self.quality.accuracy,
                "clarity": self.quality.clarity,
                "helpfulness": self.quality.helpfulness,
                "weighted_score": self.quality.weighted_score,
                "reasoning": self.quality.reasoning,
                "evaluator_model": self.quality.evaluator_model,
            }

        if self.math:
            result["math"] = {
                "score": self.math.score,
                "total_checks": self.math.total_checks,
                "passed": self.math.passed,
                "failed": self.math.failed,
                "checks": self.math.checks,
                "skipped": self.math.skipped,
            }

        return result

    @classmethod
    def from_dict(cls, data: dict) -> "ValidationReport":
        """Reconstruct from a dict (for history replay)."""
        if not data:
            return cls()

        quality = None
        if "quality" in data:
            q = data["quality"]
            quality = QualityResult(
                relevance=q.get("relevance", 5),
                completeness=q.get("completeness", 5),
                accuracy=q.get("accuracy", 5),
                clarity=q.get("clarity", 5),
                helpfulness=q.get("helpfulness", 5),
                reasoning=q.get("reasoning", ""),
                evaluator_model=q.get("evaluator_model", ""),
            )

        math = None
        if "math" in data:
            math = MathResult(**data["math"])

        return cls(
            quality=quality,
            math=math,
            overall_score=data.get("overall_score", 0.0),
            timestamp=data.get("timestamp", ""),
        )
