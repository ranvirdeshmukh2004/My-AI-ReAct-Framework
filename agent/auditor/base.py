"""
base.py — Audit Result Dataclasses
====================================
Structured containers for all audit outputs.
"""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class QualityScore:
    """Quality assessment of the agent's response."""
    accuracy: int = 0           # 0-10: Does the answer match observations?
    completeness: int = 0       # 0-10: Did it address all parts of the query?
    relevance: int = 0          # 0-10: Is the answer on-topic?
    citation_quality: int = 0   # 0-10: Are sources properly cited?
    overall: float = 0.0        # Weighted average
    summary: str = ""           # One-line verdict

    def __post_init__(self):
        if self.overall == 0.0 and any([self.accuracy, self.completeness, self.relevance, self.citation_quality]):
            self.overall = round(
                (self.accuracy * 0.35 + self.completeness * 0.25 +
                 self.relevance * 0.25 + self.citation_quality * 0.15), 1
            )


@dataclass
class FactCheckClaim:
    """A single factual claim and its verification status."""
    claim: str = ""
    status: str = "unverified"  # "verified", "unverified", "hallucinated"
    evidence: str = ""          # Which observation supports this


@dataclass
class FactCheckResult:
    """Fact-check summary across all claims."""
    total_claims: int = 0
    verified: int = 0
    unverified: int = 0
    hallucinated: int = 0
    claims: list = field(default_factory=list)  # list of FactCheckClaim dicts


@dataclass
class CostReport:
    """Efficiency analysis of the agent run."""
    iterations: int = 0
    tool_calls: int = 0
    optimal_tool_calls: int = 0
    total_tokens: int = 0
    llm_calls: int = 0
    total_ms: float = 0.0
    llm_ms: float = 0.0
    vector_search_ms: float = 0.0
    efficiency_rating: str = "Good"  # "Optimal", "Good", "Fair", "Wasteful"
    suggestions: list = field(default_factory=list)


@dataclass
class AuditReport:
    """Combined audit report from all auditors."""
    quality: QualityScore | None = None
    fact_check: FactCheckResult | None = None
    cost: CostReport | None = None
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> dict:
        """Convert to a JSON-serializable dict for session state storage."""
        result = {"timestamp": self.timestamp}

        if self.quality:
            result["quality"] = {
                "accuracy": self.quality.accuracy,
                "completeness": self.quality.completeness,
                "relevance": self.quality.relevance,
                "citation_quality": self.quality.citation_quality,
                "overall": self.quality.overall,
                "summary": self.quality.summary,
            }

        if self.fact_check:
            result["fact_check"] = {
                "total_claims": self.fact_check.total_claims,
                "verified": self.fact_check.verified,
                "unverified": self.fact_check.unverified,
                "hallucinated": self.fact_check.hallucinated,
                "claims": self.fact_check.claims,
            }

        if self.cost:
            result["cost"] = {
                "iterations": self.cost.iterations,
                "tool_calls": self.cost.tool_calls,
                "optimal_tool_calls": self.cost.optimal_tool_calls,
                "total_tokens": self.cost.total_tokens,
                "llm_calls": self.cost.llm_calls,
                "total_ms": self.cost.total_ms,
                "llm_ms": self.cost.llm_ms,
                "vector_search_ms": self.cost.vector_search_ms,
                "efficiency_rating": self.cost.efficiency_rating,
                "suggestions": self.cost.suggestions,
            }

        return result

    @classmethod
    def from_dict(cls, data: dict) -> "AuditReport":
        """Reconstruct from a dict (for history replay)."""
        if not data:
            return cls()

        quality = None
        if "quality" in data:
            q = data["quality"]
            quality = QualityScore(**q)

        fact_check = None
        if "fact_check" in data:
            f = data["fact_check"]
            fact_check = FactCheckResult(**f)

        cost = None
        if "cost" in data:
            c = data["cost"]
            cost = CostReport(**c)

        return cls(
            quality=quality,
            fact_check=fact_check,
            cost=cost,
            timestamp=data.get("timestamp", ""),
        )
