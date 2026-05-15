"""
base.py — Validation Result Dataclasses
=========================================
Structured containers for all validator outputs.
Each validator produces a score (0-10) and detailed results.
"""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class ConsensusResult:
    """Multi-model consensus validation result."""
    score: int = 10                 # 0-10
    agreement: str = "not_run"      # "full", "partial", "contradiction", "not_run"
    agent_summary: str = ""         # Key points from agent
    validator_summary: str = ""     # Key points from validator model
    differences: list = field(default_factory=list)  # List of disagreement strings
    validator_model: str = ""       # Which model verified


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
    skipped: bool = False           # True if no math steps found (auto 10/10)


@dataclass
class ToolRerunItem:
    """A single tool re-execution verification."""
    tool: str = ""
    input_text: str = ""
    original_output: str = ""
    fresh_output: str = ""
    match: bool = True


@dataclass
class ToolRerunResult:
    """Tool re-execution result."""
    score: int = 10                 # 0-10
    total_checks: int = 0
    passed: int = 0
    failed: int = 0
    checks: list = field(default_factory=list)  # list of ToolRerunItem dicts
    skipped: bool = False           # True if no re-runnable tools found


@dataclass
class SourceCheckItem:
    """A single source URL verification."""
    url: str = ""
    accessible: bool = False
    status_code: int = 0
    error: str = ""


@dataclass
class SourceURLResult:
    """Source URL accessibility result."""
    score: int = 10                 # 0-10
    total_checks: int = 0
    accessible: int = 0
    failed: int = 0
    checks: list = field(default_factory=list)  # list of SourceCheckItem dicts
    skipped: bool = False           # True if no sources found


@dataclass
class ValidationReport:
    """Combined validation report from all validators."""
    consensus: ConsensusResult | None = None
    math: MathResult | None = None
    tool_rerun: ToolRerunResult | None = None
    source_url: SourceURLResult | None = None
    overall_score: float = 0.0      # Weighted 0-10
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def __post_init__(self):
        """Compute weighted overall score from sub-validators."""
        if self.overall_score == 0.0:
            self._compute_overall()

    def _compute_overall(self):
        """
        Weighted score:
          Consensus: 40%, Math: 20%, ToolRerun: 20%, SourceURL: 20%
        If a validator didn't run / was skipped, redistribute its weight.
        """
        weights = []
        scores = []

        if self.consensus and self.consensus.agreement != "not_run":
            weights.append(0.40)
            scores.append(self.consensus.score)
        if self.math:
            weights.append(0.20)
            scores.append(self.math.score)
        if self.tool_rerun:
            weights.append(0.20)
            scores.append(self.tool_rerun.score)
        if self.source_url:
            weights.append(0.20)
            scores.append(self.source_url.score)

        if not weights:
            self.overall_score = 0.0
            return

        # Normalize weights so they sum to 1.0
        total_weight = sum(weights)
        self.overall_score = round(
            sum(s * (w / total_weight) for s, w in zip(scores, weights)), 1
        )

    def to_dict(self) -> dict:
        """Convert to a JSON-serializable dict for session state storage."""
        result = {
            "overall_score": self.overall_score,
            "timestamp": self.timestamp,
        }

        if self.consensus:
            result["consensus"] = {
                "score": self.consensus.score,
                "agreement": self.consensus.agreement,
                "agent_summary": self.consensus.agent_summary,
                "validator_summary": self.consensus.validator_summary,
                "differences": self.consensus.differences,
                "validator_model": self.consensus.validator_model,
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

        if self.tool_rerun:
            result["tool_rerun"] = {
                "score": self.tool_rerun.score,
                "total_checks": self.tool_rerun.total_checks,
                "passed": self.tool_rerun.passed,
                "failed": self.tool_rerun.failed,
                "checks": self.tool_rerun.checks,
                "skipped": self.tool_rerun.skipped,
            }

        if self.source_url:
            result["source_url"] = {
                "score": self.source_url.score,
                "total_checks": self.source_url.total_checks,
                "accessible": self.source_url.accessible,
                "failed": self.source_url.failed,
                "checks": self.source_url.checks,
                "skipped": self.source_url.skipped,
            }

        return result

    @classmethod
    def from_dict(cls, data: dict) -> "ValidationReport":
        """Reconstruct from a dict (for history replay)."""
        if not data:
            return cls()

        consensus = None
        if "consensus" in data:
            consensus = ConsensusResult(**data["consensus"])

        math = None
        if "math" in data:
            math = MathResult(**data["math"])

        tool_rerun = None
        if "tool_rerun" in data:
            tool_rerun = ToolRerunResult(**data["tool_rerun"])

        source_url = None
        if "source_url" in data:
            source_url = SourceURLResult(**data["source_url"])

        return cls(
            consensus=consensus,
            math=math,
            tool_rerun=tool_rerun,
            source_url=source_url,
            overall_score=data.get("overall_score", 0.0),
            timestamp=data.get("timestamp", ""),
        )
