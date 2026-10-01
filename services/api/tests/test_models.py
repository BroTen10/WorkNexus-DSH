from sqlalchemy.exc import IntegrityError

from app.models import (
    AuditEvent,
    BackgroundJob,
    BudgetPolicy,
    Department,
    EmailVerificationCode,
    ExternalService,
    KnowledgeBase,
    KnowledgeBinding,
    Membership,
    Organization,
    PluginInstall,
    ProjectSpace,
    RoleAssignment,
    SessionMeta,
    UsageRecord,
    User,
)
from app.models.base import Base


def test_sixteen_core_entities_exist():
    expected = {
        User, EmailVerificationCode, Organization, Department, ProjectSpace, Membership,
        RoleAssignment, AuditEvent, UsageRecord, BudgetPolicy, PluginInstall, SessionMeta,
        KnowledgeBase, KnowledgeBinding, ExternalService, BackgroundJob,
    }
    assert len(expected) == 16
    assert all(model.__tablename__ for model in expected)


def test_membership_is_unique_per_user_and_space(session):
    session.add(Membership(user_id="u1", organization_id="o1", department_id="d1", space_type="project", project_space_id="s1"))
    session.commit()
    session.add(Membership(user_id="u1", organization_id="o1", department_id="d1", space_type="project", project_space_id="s1"))
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
    else:
        raise AssertionError("duplicate membership was accepted")


def test_usage_record_allows_null_token_fields(session):
    row = UsageRecord(
        usage_id="usage-1",
        user_id="u1",
        organization_id="o1",
        provider="deepseek",
        model="m",
        source="adapter_estimate",
    )
    session.add(row)
    session.commit()
    assert row.prompt_tokens is None
    assert row.completion_tokens is None
    assert row.total_tokens is None
    assert row.estimated_cost is None


def test_audit_and_usage_are_append_only_by_contract(session):
    audit_columns = set(AuditEvent.__table__.columns)
    usage_columns = set(UsageRecord.__table__.columns)
    assert not {"updated_at", "deleted_at"} & {column.name for column in audit_columns}
    assert not {"updated_at", "deleted_at"} & {column.name for column in usage_columns}
    assert any(column.name == "corrects_event_id" for column in audit_columns)
    assert AuditEvent.__table__.c.retention_days.default.arg == 1095
    assert UsageRecord.__table__.c.retention_days.default.arg == 1095


def test_plugin_install_is_official_mirror(session):
    row = PluginInstall(organization_id="o1", plugin_id="p", version="1.0.0", state="installed")
    session.add(row)
    session.commit()
    assert row.authoritative_source == "official-plugin-manager"
    assert row.official_state == "installed"


def test_session_meta_has_no_official_session_content_columns():
    column_names = {column.name for column in SessionMeta.__table__.columns}
    assert not {"content", "prompt", "transcript", "messages", "output"} & column_names


def test_budget_policy_scope_constraint():
    constraints = {constraint.name for constraint in BudgetPolicy.__table__.constraints}
    assert "ck_budget_policy_scope" in constraints
