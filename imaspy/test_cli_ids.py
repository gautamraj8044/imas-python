from importlib.metadata import version

from click.testing import CliRunner
import pytest

from imaspy.command.subcommands.ids import info, open_from_file
from imaspy.ids_defs import (
    ASCII_BACKEND,
    IDS_TIME_MODE_INDEPENDENT,
    IDS_TIME_MODE_HOMOGENEOUS,
)
from imaspy.ids_root import IDSRoot
from imaspy.test_helpers import open_ids


@pytest.fixture
def filled_ascii_datastore(tmp_path, ids_minimal_types, worker_id, requires_imas):
    filename = "test_1_0_minimal.ids"  # Generated by open_ids
    ids = open_ids(ASCII_BACKEND, "w", worker_id, tmp_path, xml_path=ids_minimal_types)
    ids.minimal["int_type"] = 99
    ids["minimal"].ids_properties.homogeneous_time = IDS_TIME_MODE_HOMOGENEOUS
    ids.minimal.put()
    ids.close()
    yield tmp_path, filename, ids_minimal_types, worker_id


@pytest.mark.cli
@pytest.mark.xfail(reason="IMAS-4533")
def test_ids_info_function(filled_ascii_datastore):
    tmp_path, filename, ids_minimal_types, _ = filled_ascii_datastore

    info([f"{tmp_path / filename}", f"--xml_path={ids_minimal_types}"])


@pytest.mark.cli
@pytest.mark.xfail(reason="IMAS-4533")
def test_ids_info(filled_ascii_datastore):
    tmp_path, filename, ids_minimal_types, _ = filled_ascii_datastore

    runner = CliRunner()
    result = runner.invoke(
        info,
        [
            str(tmp_path / filename),
            "--name=minimal/int_type",
            f"--xml_path={ids_minimal_types}",
        ],
    )
    assert result.exit_code == 0
    assert result.output == "Hello world!\n"


@pytest.mark.cli
@pytest.mark.xfail(reason="IMAS-4533")
def test_open_from_file(filled_ascii_datastore):
    tmp_path, filename, ids_minimal_types, _ = filled_ascii_datastore

    open_from_file(tmp_path / filename, xml_path=ids_minimal_types)


@pytest.mark.cli
def test_reopen_ids(filled_ascii_datastore):
    tmp_path, _, ids_minimal_types, worker_id = filled_ascii_datastore

    ids2 = open_ids(ASCII_BACKEND, "r", worker_id, tmp_path, xml_path=ids_minimal_types)
    ids2.minimal.get()
    assert ids2.minimal.ids_properties.version_put.access_layer_language == "Python"
