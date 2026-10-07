import logging
from pathlib import Path

import pytest

from uav_gc import config
from uav_gc.config import ConfigError, load_config

VALID = """\
[link]
device = "tcp:127.0.0.1:5762"

[auth]
secret = "s3cret"
"""


def _write(tmp_path: Path, text: str) -> Path:
    path = tmp_path / "config.toml"
    path.write_text(text)
    return path


def test_valid_file_and_defaults(tmp_path):
    cfg = load_config(_write(tmp_path, VALID))

    assert cfg.http.host == "127.0.0.1"
    assert cfg.http.port == 8080
    assert cfg.link.device == "tcp:127.0.0.1:5762"
    assert cfg.link.baud == 115200
    assert cfg.log.level == "INFO"
    assert cfg.auth.token_ttl_min == 30
    assert cfg.users.admin_username is None
    assert cfg.users.admin_password is None
    assert cfg.users.database == str(tmp_path / "data" / "users.db")


def test_missing_file_names_path(tmp_path):
    missing = tmp_path / "absent.toml"

    with pytest.raises(ConfigError, match="absent.toml"):
        load_config(missing)


def test_missing_section_names_section(tmp_path):
    text = '[link]\ndevice = "tcp:127.0.0.1:5762"\n'

    with pytest.raises(ConfigError, match="auth"):
        load_config(_write(tmp_path, text))


def test_missing_link_section_names_section(tmp_path):
    text = '[auth]\nsecret = "s3cret"\n'

    with pytest.raises(ConfigError, match="link"):
        load_config(_write(tmp_path, text))


def test_unknown_key(tmp_path):
    text = VALID + "\n[http]\nprot = 8080\n"

    with pytest.raises(ConfigError, match="prot"):
        load_config(_write(tmp_path, text))


def test_wrong_type(tmp_path):
    text = VALID + '\n[http]\nport = "eighty"\n'

    with pytest.raises(ConfigError, match="port"):
        load_config(_write(tmp_path, text))


def test_missing_device(tmp_path):
    text = '[link]\n\n[auth]\nsecret = "s3cret"\n'

    with pytest.raises(ConfigError, match="device"):
        load_config(_write(tmp_path, text))


def test_empty_secret(tmp_path):
    text = '[link]\ndevice = "tcp:127.0.0.1:5762"\n\n[auth]\nsecret = ""\n'

    with pytest.raises(ConfigError, match="secret"):
        load_config(_write(tmp_path, text))


def test_missing_secret(tmp_path):
    text = '[link]\ndevice = "tcp:127.0.0.1:5762"\n\n[auth]\ntoken_ttl_min = 30\n'

    with pytest.raises(ConfigError, match="secret"):
        load_config(_write(tmp_path, text))


def test_validation_error_does_not_echo_config(tmp_path):
    text = (
        '[link]\ndevice = "tcp:127.0.0.1:5762"\n\n'
        '[users]\nadmin_password = "hunter2"\n'
    )

    with pytest.raises(ConfigError) as exc:
        load_config(_write(tmp_path, text))

    assert "hunter2" not in str(exc.value)


def test_relative_database_resolves_next_to_file(tmp_path):
    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    text = VALID + '\n[users]\ndatabase = "data/users.db"\n'

    cfg = load_config(_write(elsewhere, text))

    assert cfg.users.database == str(elsewhere / "data" / "users.db")


def test_absolute_database_is_kept(tmp_path):
    absolute = tmp_path / "users.db"
    text = VALID + f'\n[users]\ndatabase = "{absolute}"\n'

    cfg = load_config(_write(tmp_path, text))

    assert cfg.users.database == str(absolute)


def test_example_secret_warns(tmp_path, caplog):
    text = (
        '[link]\ndevice = "tcp:127.0.0.1:5762"\n\n'
        f'[auth]\nsecret = "{config.EXAMPLE_SECRET}"\n'
    )

    with caplog.at_level(logging.WARNING, logger="uav_gc.config"):
        load_config(_write(tmp_path, text))

    assert any("auth.secret" in record.getMessage() for record in caplog.records)
