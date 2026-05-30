"""Seed data for development and testing.

Populates the database with realistic test data on app startup if empty.
Seeded projects return mock PR lists instead of calling the GitHub API.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from backend.core.database import SessionLocal
from backend.core.security import encrypt_token
from backend.models import AgentTiming, AppSettings, Project, Review, ReviewStatus


def _now() -> datetime:
    return datetime.now(timezone.utc)


# Seed PR list data — returned for seeded projects instead of calling GitHub API.
# Format matches the GitHub PR list API response fields used in the endpoint.
SEED_PR_LISTS: dict[int, list[dict]] = {
    1: [
        {
            "number": 1,
            "title": "Add user authentication middleware",
            "user": {"login": "alice-dev"},
            "created_at": (_now() - timedelta(days=3)).isoformat(),
            "updated_at": (_now() - timedelta(days=3)).isoformat(),
            "head": {"ref": "feat/auth-middleware"},
            "base": {"ref": "main"},
            "labels": [{"name": "enhancement", "color": "84b6eb"}, {"name": "auth", "color": "d4c5f9"}],
            "state": "open",
            "draft": False,
            "merged_at": None,
        },
        {
            "number": 2,
            "title": "Fix database connection pool config",
            "user": {"login": "bob-coder"},
            "created_at": (_now() - timedelta(days=2)).isoformat(),
            "updated_at": (_now() - timedelta(days=2)).isoformat(),
            "head": {"ref": "fix/db-pool-config"},
            "base": {"ref": "main"},
            "labels": [{"name": "bug", "color": "d73a4a"}, {"name": "database", "color": "0075ca"}],
            "state": "open",
            "draft": False,
            "merged_at": None,
        },
        {
            "number": 3,
            "title": "Update API rate limiting rules",
            "user": {"login": "alice-dev"},
            "created_at": (_now() - timedelta(days=1)).isoformat(),
            "updated_at": (_now() - timedelta(days=1)).isoformat(),
            "head": {"ref": "feat/rate-limit-v2"},
            "base": {"ref": "main"},
            "labels": [{"name": "enhancement", "color": "84b6eb"}, {"name": "security", "color": "d93f0b"}],
            "state": "open",
            "draft": False,
            "merged_at": None,
        },
        {
            "number": 4,
            "title": "Refactor logging module to use structured logging",
            "user": {"login": "charlie-ops"},
            "created_at": (_now() - timedelta(hours=12)).isoformat(),
            "updated_at": (_now() - timedelta(hours=12)).isoformat(),
            "head": {"ref": "refactor/structured-logging"},
            "base": {"ref": "main"},
            "labels": [{"name": "refactor", "color": "bfdadc"}],
            "state": "open",
            "draft": False,
            "merged_at": None,
        },
        {
            "number": 5,
            "title": "Add health check endpoint",
            "user": {"login": "bob-coder"},
            "created_at": (_now() - timedelta(hours=6)).isoformat(),
            "updated_at": (_now() - timedelta(hours=6)).isoformat(),
            "head": {"ref": "feat/health-check"},
            "base": {"ref": "main"},
            "labels": [{"name": "enhancement", "color": "84b6eb"}],
            "state": "open",
            "draft": False,
            "merged_at": None,
        },
        # Closed / merged PRs
        {
            "number": 6,
            "title": "Fix typo in README installation instructions",
            "user": {"login": "diana-newbie"},
            "created_at": (_now() - timedelta(days=10)).isoformat(),
            "updated_at": (_now() - timedelta(days=7)).isoformat(),
            "head": {"ref": "fix/readme-typo"},
            "base": {"ref": "main"},
            "labels": [{"name": "documentation", "color": "0075ca"}],
            "state": "closed",
            "draft": False,
            "merged_at": (_now() - timedelta(days=7)).isoformat(),
        },
        {
            "number": 7,
            "title": "Add experimental GraphQL endpoint",
            "user": {"login": "charlie-ops"},
            "created_at": (_now() - timedelta(days=14)).isoformat(),
            "updated_at": (_now() - timedelta(days=12)).isoformat(),
            "head": {"ref": "feat/graphql-poc"},
            "base": {"ref": "main"},
            "labels": [{"name": "experimental", "color": "f9d0c4"}, {"name": "wontfix", "color": "d93f0b"}],
            "state": "closed",
            "draft": False,
            "merged_at": None,
        },
        {
            "number": 8,
            "title": "Upgrade dependencies to latest versions",
            "user": {"login": "alice-dev"},
            "created_at": (_now() - timedelta(days=20)).isoformat(),
            "updated_at": (_now() - timedelta(days=18)).isoformat(),
            "head": {"ref": "chore/deps-upgrade"},
            "base": {"ref": "main"},
            "labels": [{"name": "dependencies", "color": "0366d6"}],
            "state": "closed",
            "draft": False,
            "merged_at": (_now() - timedelta(days=18)).isoformat(),
        },
    ],
    2: [
        {
            "number": 1,
            "title": "Initial project setup and CI configuration",
            "user": {"login": "diana-newbie"},
            "created_at": (_now() - timedelta(days=5)).isoformat(),
            "updated_at": (_now() - timedelta(days=5)).isoformat(),
            "head": {"ref": "feat/initial-setup"},
            "base": {"ref": "main"},
            "labels": [{"name": "enhancement", "color": "84b6eb"}, {"name": "ci", "color": "fef2c0"}],
            "state": "open",
            "draft": False,
            "merged_at": None,
        },
        {
            "number": 2,
            "title": "Add README documentation",
            "user": {"login": "diana-newbie"},
            "created_at": (_now() - timedelta(days=3)).isoformat(),
            "updated_at": (_now() - timedelta(days=3)).isoformat(),
            "head": {"ref": "docs/readme"},
            "base": {"ref": "main"},
            "labels": [{"name": "documentation", "color": "0075ca"}],
            "state": "open",
            "draft": True,
            "merged_at": None,
        },
        {
            "number": 3,
            "title": "Remove deprecated API v1 endpoints",
            "user": {"login": "bob-coder"},
            "created_at": (_now() - timedelta(days=12)).isoformat(),
            "updated_at": (_now() - timedelta(days=10)).isoformat(),
            "head": {"ref": "chore/remove-v1-api"},
            "base": {"ref": "main"},
            "labels": [{"name": "refactor", "color": "bfdadc"}],
            "state": "closed",
            "draft": False,
            "merged_at": (_now() - timedelta(days=10)).isoformat(),
        },
    ],
}


def seed_database() -> None:
    """Populate database with seed data if empty. Safe to call on every startup."""
    db = SessionLocal()
    try:
        existing = db.query(Project).count()
        if existing > 0:
            return

        try:
            fake_pat = encrypt_token("fake-pat-for-seed-data")
        except Exception:
            fake_pat = "seed-placeholder-encrypted-pat"

        # ── Global settings ──────────────────────────────────────
        db.add(AppSettings(id=1, encrypted_pat=fake_pat))

        # ── Project 1: fully populated with reviews ──────────────────────
        p1 = Project(
            name="Seed Demo Project",
            repo_owner="test-owner",
            repo_name="seed-demo",
            description=(
                "A demo project with sample AI review data. This project showcases "
                "all PR review features including risk analysis, issue detection, and test suggestions."
            ),
            is_seeded=True,
            tags='["开源", "Demo"]',
            is_favorite=True,
            permission="Owner",
        )
        db.add(p1)
        db.flush()

        # ── Project 2: no reviews, just PR list ──────────────────────────
        p2 = Project(
            name="Empty Test Project",
            repo_owner="test-owner",
            repo_name="empty-test",
            description=(
                "A minimal test project with no reviews yet. Use this to test "
                "the empty state and initial review trigger flow."
            ),
            is_seeded=True,
            tags='["开源"]',
            permission="Viewer",
        )
        db.add(p2)
        db.flush()

        # ── Review 1 (PR #1 in P1): FULL data — summary, risk, issues, tests, comment, timings
        r1 = Review(
            project_id=p1.id,
            pr_number=1,
            pr_title="Add user authentication middleware",
            status=ReviewStatus.succeeded,
            stage="completed",
            diff_content=(
                "diff --git a/src/auth/middleware.py b/src/auth/middleware.py\n"
                "new file mode 100644\n"
                "--- /dev/null\n"
                "+++ b/src/auth/middleware.py\n"
                '@@ -0,0 +1,45 @@\n'
                '+import jwt\n'
                '+from functools import wraps\n'
                '+from flask import request, g, jsonify\n'
                '+\n'
                '+SECRET_KEY = "hardcoded-secret"\n'
                '+\n'
                '+def authenticate(f):\n'
                '+    @wraps(f)\n'
                '+    def decorated(*args, **kwargs):\n'
                '+        token = request.headers.get("Authorization")\n'
                '+        if not token:\n'
                '+            return jsonify({"error": "No token"}), 401\n'
                '+        try:\n'
                '+            payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])\n'
                '+            g.user = payload["sub"]\n'
                '+        except jwt.ExpiredSignatureError:\n'
                '+            return jsonify({"error": "Token expired"}), 401\n'
                '+        except jwt.InvalidTokenError:\n'
                '+            return jsonify({"error": "Invalid token"}), 401\n'
                '+        return f(*args, **kwargs)\n'
                '+    return decorated\n'
                '+\n'
                '+def require_role(role):\n'
                '+    def decorator(f):\n'
                '+        @wraps(f)\n'
                '+        def wrapped(*args, **kwargs):\n'
                '+            return f(*args, **kwargs)\n'
                '+        return wrapped\n'
                '+    return decorator\n'
                '+\n'
                '+@app.route("/login", methods=["POST"])\n'
                '+def login():\n'
                '+    data = request.get_json()\n'
                '+    username = data["username"]\n'
                '+    password = data["password"]\n'
                '+    token = jwt.encode({"sub": username}, SECRET_KEY, algorithm="HS256")\n'
                '+    return jsonify({"token": token})\n'
            ),
            summary_result={
                "overview": "This PR adds JWT-based authentication middleware to the API, including a login endpoint and role-based access control decorators.",
                "scope": ["Authentication", "Authorization", "API Security"],
                "key_changes": [
                    "New auth middleware with JWT token verification",
                    "Login endpoint that issues JWT tokens",
                    "Role-based access control decorator (not yet functional)",
                    "Token validation in request pipeline",
                ],
                "files_changed": ["src/auth/middleware.py (new)", "src/app.py (modified)"],
            },
            risk_result={
                "risk_items": [
                    {
                        "level": "high",
                        "reason": "Hardcoded JWT secret key in source code",
                        "file": "src/auth/middleware.py",
                        "code_segment": 'SECRET_KEY = "hardcoded-secret"',
                        "suggestion": "Move secret to environment variable or secrets manager",
                    },
                    {
                        "level": "high",
                        "reason": "Password field sourced directly from request JSON without validation",
                        "file": "src/auth/middleware.py",
                        "code_segment": 'password = data["password"]',
                        "suggestion": "Add input validation for password complexity and length",
                    },
                    {
                        "level": "medium",
                        "reason": "No rate limiting on login endpoint — vulnerable to brute force attacks",
                        "file": "src/auth/middleware.py",
                        "code_segment": "@app.route('/login', methods=['POST'])",
                        "suggestion": "Add rate limiting middleware for the login endpoint",
                    },
                    {
                        "level": "low",
                        "reason": "require_role decorator is not implemented (passes through all requests)",
                        "file": "src/auth/middleware.py",
                        "code_segment": "return f(*args, **kwargs)",
                        "suggestion": "Implement role checking logic before merging",
                    },
                ],
                "overall_risk": "high",
            },
            issue_result={
                "issues": [
                    {
                        "severity": "critical",
                        "description": "Hardcoded secret key — exposed in source control",
                        "file": "src/auth/middleware.py",
                        "line": 6,
                        "suggestion": 'Use os.environ.get("JWT_SECRET") to load secret from environment',
                    },
                    {
                        "severity": "high",
                        "description": "Missing input validation — username and password not validated before use",
                        "file": "src/auth/middleware.py",
                        "line": 38,
                        "suggestion": "Validate username/password are non-empty strings, check password complexity",
                    },
                    {
                        "severity": "medium",
                        "description": "KeyError if JSON body missing username/password fields",
                        "file": "src/auth/middleware.py",
                        "line": 37,
                        "suggestion": "Use data.get('username') with default values or explicit validation",
                    },
                    {
                        "severity": "medium",
                        "description": "No database lookup — TODO left incomplete, accepts any username/password",
                        "file": "src/auth/middleware.py",
                        "line": 39,
                        "suggestion": "Implement database user lookup before merging; add bcrypt password hashing",
                    },
                    {
                        "severity": "low",
                        "description": "Missing audit logging for authentication events",
                        "file": "src/auth/middleware.py",
                        "line": 25,
                        "suggestion": "Log authentication attempts (success and failure) for security auditing",
                    },
                ]
            },
            test_result={
                "suggested_tests": [
                    {
                        "target": "authenticate decorator",
                        "scenario": "Request with valid JWT token should pass through to route handler",
                        "priority": "high",
                    },
                    {
                        "target": "authenticate decorator",
                        "scenario": "Request without Authorization header should return 401",
                        "priority": "high",
                    },
                    {
                        "target": "authenticate decorator",
                        "scenario": "Request with expired JWT token should return 401 with appropriate message",
                        "priority": "high",
                    },
                    {
                        "target": "login endpoint",
                        "scenario": "Valid username/password should return JWT token in response",
                        "priority": "high",
                    },
                    {
                        "target": "login endpoint",
                        "scenario": "Invalid credentials should return 401 with error message",
                        "priority": "medium",
                    },
                    {
                        "target": "login endpoint",
                        "scenario": "Brute force protection — 5 failed login attempts should trigger rate limiting",
                        "priority": "medium",
                    },
                    {
                        "target": "require_role decorator",
                        "scenario": "User without required role should receive 403 Forbidden",
                        "priority": "medium",
                    },
                    {
                        "target": "SECRET_KEY loading",
                        "scenario": "App should fail to start when JWT_SECRET env var is not set",
                        "priority": "medium",
                    },
                    {
                        "target": "Database integration",
                        "scenario": "Password field in database should store bcrypt hash, not plaintext",
                        "priority": "high",
                    },
                    {
                        "target": "Concurrency",
                        "scenario": "Multiple concurrent requests should each pass authentication independently",
                        "priority": "low",
                    },
                ]
            },
            comment_content=(
                "## AI Review Summary\n\n"
                "### Overview\n"
                "This PR adds JWT-based authentication middleware to the API, including a login "
                "endpoint and role-based access control decorators.\n\n"
                "### Risk Level: **HIGH** 🔴\n\n"
                "### Key Changes\n"
                "- New auth middleware with JWT token verification\n"
                "- Login endpoint that issues JWT tokens\n"
                "- Role-based access control decorator (not yet functional)\n"
                "- Token validation in request pipeline\n\n"
                "### Issues Found (5)\n"
                "| Severity | Description | File |\n"
                "|----------|-------------|------|\n"
                "| 🔴 Critical | Hardcoded secret key exposed in source control | `src/auth/middleware.py:6` |\n"
                "| 🟠 High | Missing input validation for username/password | `src/auth/middleware.py:38` |\n"
                "| 🟡 Medium | KeyError if JSON body missing fields | `src/auth/middleware.py:37` |\n"
                "| 🟡 Medium | No database lookup — TODO left incomplete | `src/auth/middleware.py:39` |\n"
                "| ⚪ Low | Missing audit logging for auth events | `src/auth/middleware.py:25` |\n\n"
                "### Suggested Tests\n"
                "10 test scenarios suggested covering authentication, authorization, and edge cases.\n\n"
                "> View full review details on PRism: https://github.com\n"
            ),
            started_at=_now() - timedelta(minutes=5),
            completed_at=_now() - timedelta(minutes=3),
            created_at=_now() - timedelta(minutes=5),
        )
        db.add(r1)
        db.flush()

        # Agent timings for r1 (summary → [risk, issues, tests] → comment_compose)
        db.add_all([
            AgentTiming(
                review_id=r1.id, agent_name="summary",
                start_time=_now() - timedelta(minutes=5),
                end_time=_now() - timedelta(minutes=4, seconds=45),
            ),
            AgentTiming(
                review_id=r1.id, agent_name="risk_analysis",
                start_time=_now() - timedelta(minutes=4, seconds=45),
                end_time=_now() - timedelta(minutes=4, seconds=30),
            ),
            AgentTiming(
                review_id=r1.id, agent_name="issue_detection",
                start_time=_now() - timedelta(minutes=4, seconds=45),
                end_time=_now() - timedelta(minutes=4, seconds=20),
            ),
            AgentTiming(
                review_id=r1.id, agent_name="test_suggestions",
                start_time=_now() - timedelta(minutes=4, seconds=45),
                end_time=_now() - timedelta(minutes=4, seconds=25),
            ),
            AgentTiming(
                review_id=r1.id, agent_name="comment_compose",
                start_time=_now() - timedelta(minutes=4, seconds=20),
                end_time=_now() - timedelta(minutes=3),
            ),
        ])

        # ── Review 2 (PR #2 in P1): completed, simpler data
        r2 = Review(
            project_id=p1.id,
            pr_number=2,
            pr_title="Fix database connection pool config",
            status=ReviewStatus.succeeded,
            stage="completed",
            summary_result={
                "overview": "Fixes the database connection pool configuration to prevent connection leaks under load.",
                "scope": ["Database", "Configuration"],
                "key_changes": [
                    "Increased pool size from 5 to 20",
                    "Added connection timeout of 30s",
                    "Enabled connection recycling after 1 hour",
                ],
                "files_changed": ["config/database.yml"],
            },
            risk_result={
                "risk_items": [
                    {
                        "level": "medium",
                        "reason": "Increasing pool size affects all service instances sharing the DB",
                        "file": "config/database.yml",
                        "code_segment": "pool: 20",
                        "suggestion": "Verify DB max_connections can handle 20 * instance_count",
                    },
                ],
                "overall_risk": "medium",
            },
            issue_result={
                "issues": [
                    {
                        "severity": "low",
                        "description": "Pool timeout of 30s may be too high for high-traffic scenarios",
                        "file": "config/database.yml",
                        "line": 5,
                        "suggestion": "Consider setting a lower timeout (10s) and implementing retry logic",
                    },
                ]
            },
            test_result={
                "suggested_tests": [
                    {
                        "target": "Connection pool",
                        "scenario": "Concurrent connections up to pool limit should all succeed",
                        "priority": "high",
                    },
                    {
                        "target": "Connection timeout",
                        "scenario": "Request exceeding timeout should fail gracefully with clear error",
                        "priority": "medium",
                    },
                ]
            },
            comment_content=(
                "## AI Review Summary\n\n"
                "### Overview\n"
                "Fixes database connection pool configuration to prevent connection leaks.\n\n"
                "### Risk Level: MEDIUM 🟡\n\n"
                "No critical issues found. One low-severity suggestion."
            ),
            started_at=_now() - timedelta(hours=1),
            completed_at=_now() - timedelta(minutes=58),
            created_at=_now() - timedelta(hours=1),
        )
        db.add(r2)
        db.flush()

        db.add_all([
            AgentTiming(
                review_id=r2.id, agent_name="summary",
                start_time=_now() - timedelta(hours=1),
                end_time=_now() - timedelta(minutes=59, seconds=45),
            ),
            AgentTiming(
                review_id=r2.id, agent_name="risk_analysis",
                start_time=_now() - timedelta(minutes=59, seconds=45),
                end_time=_now() - timedelta(minutes=59, seconds=30),
            ),
            AgentTiming(
                review_id=r2.id, agent_name="issue_detection",
                start_time=_now() - timedelta(minutes=59, seconds=45),
                end_time=_now() - timedelta(minutes=59, seconds=20),
            ),
            AgentTiming(
                review_id=r2.id, agent_name="test_suggestions",
                start_time=_now() - timedelta(minutes=59, seconds=45),
                end_time=_now() - timedelta(minutes=59, seconds=25),
            ),
            AgentTiming(
                review_id=r2.id, agent_name="comment_compose",
                start_time=_now() - timedelta(minutes=59, seconds=20),
                end_time=_now() - timedelta(minutes=58),
            ),
        ])

        # ── Review 3 (PR #3 in P1): queued — demonstrates pending state
        r3 = Review(
            project_id=p1.id,
            pr_number=3,
            pr_title="Update API rate limiting rules",
            status=ReviewStatus.queued,
            stage=None,
            created_at=_now() - timedelta(minutes=1),
        )
        db.add(r3)
        db.flush()

        # ── Review 4 (PR #4 in P1): succeeded, basic data
        r4 = Review(
            project_id=p1.id,
            pr_number=4,
            pr_title="Refactor logging module to use structured logging",
            status=ReviewStatus.succeeded,
            stage="completed",
            summary_result={
                "overview": "Refactors the logging module to use structured JSON logging for better observability.",
                "scope": ["Logging", "Observability"],
                "key_changes": [
                    "Replaced print() with structlog",
                    "Added request ID to log context",
                    "Configured log levels by environment",
                ],
                "files_changed": ["src/utils/logger.py"],
            },
            risk_result={
                "risk_items": [],
                "overall_risk": "low",
            },
            issue_result={
                "issues": [],
            },
            test_result={
                "suggested_tests": [
                    {
                        "target": "Logger",
                        "scenario": "Structured logs should contain request_id in context",
                        "priority": "high",
                    },
                ]
            },
            comment_content=(
                "## AI Review Summary\n\n"
                "### Overview\n"
                "Refactors logging to structured JSON format.\n\n"
                "### Risk Level: LOW 🟢\n\n"
                "No issues found. One test suggested."
            ),
            started_at=_now() - timedelta(hours=2),
            completed_at=_now() - timedelta(hours=1, minutes=58),
            created_at=_now() - timedelta(hours=2),
        )
        db.add(r4)
        db.flush()

        db.add_all([
            AgentTiming(
                review_id=r4.id, agent_name="summary",
                start_time=_now() - timedelta(hours=2),
                end_time=_now() - timedelta(minutes=119, seconds=45),
            ),
            AgentTiming(
                review_id=r4.id, agent_name="risk_analysis",
                start_time=_now() - timedelta(minutes=119, seconds=45),
                end_time=_now() - timedelta(minutes=119, seconds=35),
            ),
            AgentTiming(
                review_id=r4.id, agent_name="issue_detection",
                start_time=_now() - timedelta(minutes=119, seconds=45),
                end_time=_now() - timedelta(minutes=119, seconds=30),
            ),
            AgentTiming(
                review_id=r4.id, agent_name="test_suggestions",
                start_time=_now() - timedelta(minutes=119, seconds=45),
                end_time=_now() - timedelta(minutes=119, seconds=25),
            ),
            AgentTiming(
                review_id=r4.id, agent_name="comment_compose",
                start_time=_now() - timedelta(minutes=119, seconds=20),
                end_time=_now() - timedelta(minutes=118),
            ),
        ])

        # ── Review 5 (PR #5 in P1): failed — demonstrates error state
        r5 = Review(
            project_id=p1.id,
            pr_number=5,
            pr_title="Add health check endpoint",
            status=ReviewStatus.failed,
            stage=None,
            error_message="LLM API returned status 429: Rate limit exceeded. Please try again later.",
            started_at=_now() - timedelta(minutes=30),
            completed_at=_now() - timedelta(minutes=29),
            created_at=_now() - timedelta(minutes=30),
        )
        db.add(r5)

        db.commit()
    finally:
        db.close()
