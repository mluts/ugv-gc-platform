import pytest

from uav_gc.errors import NotFound, UsernameTaken
from uav_gc.models import Role
from uav_gc.users import UserStore


@pytest.fixture
def store():
    store = UserStore(":memory:")
    yield store
    store.close()


def test_create_and_get(store):
    user = store.create("alice", "hash-alice", Role.operator)

    assert user.id > 0
    assert user.username == "alice"
    assert user.role == Role.operator
    assert store.get(user.id) == user


def test_get_unknown_raises_not_found(store):
    with pytest.raises(NotFound):
        store.get(999)


def test_list_is_ordered_and_hides_hashes(store):
    store.create("alice", "h", Role.viewer)
    store.create("bob", "h", Role.admin)

    users = store.list()

    assert [u.username for u in users] == ["alice", "bob"]
    assert all(u.model_dump().keys() == {"id", "username", "role"} for u in users)


def test_count(store):
    assert store.count() == 0

    store.create("alice", "h", Role.viewer)

    assert store.count() == 1


def test_get_by_username(store):
    created = store.create("alice", "hash-alice", Role.operator)

    found = store.get_by_username("alice")

    assert found is not None
    assert found.id == created.id
    assert found.password_hash == "hash-alice"
    assert found.role == Role.operator
    assert store.get_by_username("nobody") is None


def test_duplicate_username_raises_username_taken(store):
    store.create("alice", "h", Role.viewer)

    with pytest.raises(UsernameTaken):
        store.create("alice", "h", Role.viewer)


def test_update_changes_password_and_role(store):
    user = store.create("alice", "old-hash", Role.viewer)

    updated = store.update(user.id, password_hash="new-hash", role=Role.admin)

    assert updated.role == Role.admin
    found = store.get_by_username("alice")
    assert found is not None
    assert found.password_hash == "new-hash"


def test_update_unknown_raises_not_found(store):
    with pytest.raises(NotFound):
        store.update(999, role=Role.admin)


def test_delete_removes_user(store):
    user = store.create("alice", "h", Role.viewer)

    store.delete(user.id)

    assert store.count() == 0
    assert store.get_by_username("alice") is None


def test_delete_unknown_raises_not_found(store):
    with pytest.raises(NotFound):
        store.delete(999)


def test_parent_directory_is_created(tmp_path):
    database = tmp_path / "nested" / "users.db"

    store = UserStore(str(database))
    try:
        assert database.exists()
    finally:
        store.close()
