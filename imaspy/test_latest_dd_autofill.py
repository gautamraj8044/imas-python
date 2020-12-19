"""A testcase checking if writing and then reading works for the latest full
data dictionary version.
"""

import logging
import os
from pathlib import Path

import numpy as np
import pytest

import imaspy
from imaspy.ids_defs import ASCII_BACKEND, IDS_TIME_MODE_INDEPENDENT, MEMORY_BACKEND
from imaspy.test_helpers import fill_with_random_data, visit_children

root_logger = logging.getLogger("imaspy")
logger = root_logger
logger.setLevel(logging.DEBUG)


def test_latest_dd_autofill_consistency(ids_name):
    ids = imaspy.ids_root.IDSRoot(1, 0, verbosity=1)
    fill_with_random_data(ids[ids_name])

    # check that each element in ids[ids_name] has _parent set.
    visit_children(ids[ids_name], has_parent)


def has_parent(child):
    """Check that the child has _parent set"""
    assert child._parent is not None


# TODO: use a separate folder for the MDSPLUS DB and clear it after the testcase
def test_latest_dd_autofill(ids_name, backend):
    """Write and then read again a full IDSRoot and all IDSToplevels."""
    ids = open_ids(backend, "w")
    fill_with_random_data(ids[ids_name])

    ids[ids_name].put()

    ids2 = open_ids(backend, "a")
    ids2[ids_name].get()

    if backend == MEMORY_BACKEND:
        # this one does not store anything between instantiations
        pass
    else:
        for (k1, node1), (k2, node2) in zip(
            ids[ids_name].items(), ids2[ids_name].items()
        ):
            if isinstance(node1, np.ndarray):
                assert np.array_equal(node1.value, node2.value)
            else:
                assert node1.value == node2.value


def open_ids(backend, mode):
    ids = imaspy.ids_root.IDSRoot(1, 0, verbosity=1)
    ids.open_ual_store(os.environ.get("USER", "root"), "test", "3", backend, mode=mode)
    return ids
