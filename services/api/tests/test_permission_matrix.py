import pytest

from app.services.permission import ACTIONS, can, matrix_is_complete


@pytest.mark.parametrize(
    "role,action,expected",
    [
        ("owner", "plugin.enable", True),
        ("owner", "member.remove", True),
        ("owner", "organization.delete", True),
        ("owner", "ownership.transfer", True),
        ("admin", "member.remove", True),
        ("admin", "plugin.enable", True),
        ("admin", "budget.write", True),
        ("admin", "organization.delete", False),
        ("admin", "ownership.transfer", False),
        ("member", "space.read", True),
        ("member", "space.write", True),
        ("member", "member.invite", False),
        ("viewer", "space.read", True),
        ("viewer", "usage.read", True),
        ("viewer", "session.create", False),
    ],
)
def test_role_matrix(role, action, expected):
    actor = {"role": role}
    assert can(actor, action, {"type": "space", "id": "s1"}) is expected


def test_matrix_covers_every_role_and_action():
    assert matrix_is_complete() is True
    assert len(ACTIONS) == 17
    for role in ("owner", "admin", "member", "viewer"):
        assert all(action in ACTIONS for action in ("space.read", "plugin.enable", "session.create"))
