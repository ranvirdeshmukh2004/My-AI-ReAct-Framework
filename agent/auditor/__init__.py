"""
auditor — AI Agent Quality Audit System
=========================================
Provides post-response auditing:
- Quality Scorer: Rates accuracy, completeness, relevance, citations
- Fact Checker: Verifies claims against tool observations
- Cost Auditor: Analyzes efficiency of tool usage and token consumption
"""

from agent.auditor.base import AuditReport, QualityScore, FactCheckResult, CostReport
from agent.auditor.quality_scorer import run_quality_audit
from agent.auditor.cost_auditor import run_cost_audit


def run_full_audit(
    query: str,
    answer: str,
    steps: list,
    sources: list,
    token_usage: dict,
    timing: dict,
    auditor_model: str = None,
) -> AuditReport:
    """
    Run all auditors and return a combined AuditReport.
    Quality + Fact Check use a single LLM call.
    Cost Audit is pure Python (no LLM).
    """
    # Cost audit — always runs (free, no LLM)
    cost = run_cost_audit(steps, token_usage, timing)

    # Quality + Fact Check — single LLM call
    quality = None
    fact_check = None
    try:
        quality, fact_check = run_quality_audit(
            query=query,
            answer=answer,
            steps=steps,
            sources=sources,
            model=auditor_model,
        )
    except Exception:
        pass  # Audit LLM failure never blocks the response

    return AuditReport(
        quality=quality,
        fact_check=fact_check,
        cost=cost,
    )
