"""Deterministic PR change classification used to select review experts."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ExpertDefinition:
    key: str
    label: str
    focus: str


EXPERTS: dict[str, ExpertDefinition] = {
    "risk_analysis": ExpertDefinition("risk_analysis", "Reliability Review", "errors, concurrency, and operational risk"),
    "issue_detection": ExpertDefinition("issue_detection", "Code Quality Review", "concrete defects and correctness"),
    "test_suggestions": ExpertDefinition("test_suggestions", "Test Review", "missing and high-value test coverage"),
    "security_review": ExpertDefinition("security_review", "Security Review", "authentication, authorization, secrets, and untrusted input"),
    "performance_review": ExpertDefinition("performance_review", "Performance Review", "queries, I/O, algorithms, and resource use"),
    "business_compliance_review": ExpertDefinition("business_compliance_review", "Business & Compliance Review", "business rules, auditability, privacy, and retention"),
}

DEFAULT_ENABLED_AGENTS = list(EXPERTS)

_SIGNALS: dict[str, tuple[str, ...]] = {
    "security_review": ("auth", "authorize", "authorization", "permission", "role", "rbac", "token", "jwt", "password", "secret", "api_key", "apikey", "credential", "oauth", "session", "csrf", "encrypt", "decrypt", "sql injection", "xss", "cors", "upload"),
    "performance_review": ("select ", "insert ", "update ", "delete ", "query", "database", "sql", "orm", "cache", "pagination", "batch", "loop", "for ", "while ", "asyncio", "thread", "memory", "stream", "n+1"),
    "business_compliance_review": ("order", "payment", "invoice", "refund", "price", "amount", "balance", "billing", "approval", "workflow", "policy", "compliance", "consent", "privacy", "pii", "gdpr", "retention", "audit", "ledger", "accounting"),
}

_CODE_EXTENSIONS = {".py", ".ts", ".tsx", ".js", ".jsx", ".java", ".go", ".rs", ".rb", ".php", ".cs", ".sql", ".sh", ".yaml", ".yml", ".json", ".toml", ".ini", ".tf"}


def extract_changed_files(pr_diff: str) -> list[str]:
    """Return unique target paths from a unified diff."""
    files: list[str] = []
    for line in pr_diff.splitlines():
        if not line.startswith("+++ b/"):
            continue
        path = line[6:].strip()
        if path and path != "/dev/null" and path not in files:
            files.append(path)
    return files


def _is_code_file(path: str) -> bool:
    return any(path.lower().endswith(extension) for extension in _CODE_EXTENSIONS)


def build_routing_plan(pr_diff: str, enabled_agents: list[str] | None, project_description: str = "") -> dict:
    """Classify a PR with explainable rules and return its selected experts."""
    allowed = set(enabled_agents) if enabled_agents is not None else set(DEFAULT_ENABLED_AGENTS)
    files = extract_changed_files(pr_diff)
    haystack = f"{project_description}\n{pr_diff}".lower()
    selected: list[str] = []
    reasons: dict[str, list[str]] = {}

    def select(agent: str, reason: str) -> None:
        if agent in allowed and agent not in selected:
            selected.append(agent)
        if agent in allowed:
            reasons.setdefault(agent, []).append(reason)

    code_files = [path for path in files if _is_code_file(path)]
    if code_files:
        select("issue_detection", f"Detected source or configuration changes in {len(code_files)} file(s).")
        select("test_suggestions", "Source changes require regression-test coverage review.")

    if any(path.lower().endswith((".sql", ".yaml", ".yml", ".tf", ".toml", ".ini")) for path in files):
        select("risk_analysis", "Detected infrastructure, database, or runtime configuration changes.")

    for agent, keywords in _SIGNALS.items():
        matches = [keyword for keyword in keywords if keyword in haystack]
        if matches:
            select(agent, f"Matched change signals: {', '.join(matches[:4])}.")

    if not selected and "issue_detection" in allowed:
        select("issue_detection", "Fallback review for changes without a classified domain signal.")

    return {"changed_files": files, "selected_agents": selected, "reasons": reasons, "signals": {agent: reasons[agent] for agent in selected if agent in reasons}}


def validate_enabled_agents(agent_names: list[str]) -> list[str]:
    """Reject unknown agent names before they enter persisted settings."""
    unknown = sorted(set(agent_names) - set(EXPERTS))
    if unknown:
        raise ValueError(f"Unknown review agents: {', '.join(unknown)}")
    return list(dict.fromkeys(agent_names))
