# This file is part of IMASPy.
# You should have received IMASPy LICENSE file with this project.
""" Represents a Top-level IDS (like NBI etc)
* :py:class:`IDSToplevel`
"""

# Set up logging immediately

from distutils.version import StrictVersion as V

import numpy as np

try:
    from functools import cached_property
except ImportError:
    from cached_property import cached_property

from imaspy.al_exception import ALException
from imaspy.context_store import context_store
from imaspy.dd_zip import dd_etree
from imaspy.ids_primitive import IDSPrimitive
from imaspy.ids_struct_array import IDSStructArray
from imaspy.ids_structure import IDSStructure
from imaspy.logger import logger

try:
    from imaspy.ids_defs import (
        CHAR_DATA,
        EMPTY_INT,
        IDS_TIME_MODE_HETEROGENEOUS,
        IDS_TIME_MODE_HOMOGENEOUS,
        IDS_TIME_MODE_INDEPENDENT,
        IDS_TIME_MODE_UNKNOWN,
        IDS_TIME_MODES,
        INTEGER_DATA,
        READ_OP,
        WRITE_OP,
    )
except:
    logger.critical("IMAS could not be imported. UAL not available!")


class IDSToplevel(IDSStructure):
    """This is any IDS Structure which has ids_properties as child node

    At minium, one should fill ids_properties/homogeneous_time
    IF a quantity is filled, the coordinates of that quantity must be filled as well
    """

    def __init__(
        self, parent, name, structure_xml, backend_version=None, backend_xml_path=None
    ):
        """Save backend_version and backend_xml and build translation layer."""
        super().__init__(parent, name, structure_xml)

        # Set an explicit backend_version or xml path
        # these will be used when put() or get() is called.
        self._backend_version = backend_version
        self._backend_xml_path = backend_xml_path

        if backend_xml_path or backend_version:
            self._read_backend_xml(backend_version, backend_xml_path)

    def _read_backend_xml(self, version=None, xml_path=None):
        """Find a DD xml from version or path, select the child corresponding to the
        current name and set the backend properties.

        This is defined on the Toplevel and not on the Root because that allows
        IDSes to be read from different versions. Still use the ElementTree memoization
        so performance will not suffer too much from this.
        """
        if xml_path is not None:
            self._backend_xml_path = xml_path
            logger.info("Generating backend %s from file %s", self._name, xml_path)
        elif version is not None:
            self._backend_version = version
            logger.info("Generating backend %s for version %s", self._name, version)
        else:
            return
        tree = dd_etree(version=version, xml_path=xml_path)

        # Parse given xml_path and build imaspy IDS structures for this toplevel only
        root = tree.getroot()
        ver = root.find("version")
        if ver is not None:
            if ver.text != version:
                if version is None:
                    self._backend_version = ver.text
                    logger.info("Found backend version %s", self._backend_version)
                else:
                    logger.warning(
                        "Backend version %s does not match file %s, proceeding anyway.",
                        version,
                        ver.text,
                    )
        else:
            # The version number in DD xml files was introduced in 3.30.0
            if version is not None and V(version) >= V("3.30.0"):
                logger.warning("No version number found in file %s", xml_path)

        self.set_backend_properties(
            root.find("./*[@name='{name}']".format(name=self._name))
        )

    def set_backend_properties(self, structure_xml):
        """Set backend properties for this IDSToplevel and provide some logging"""
        # TODO: better naming (structure_xml -> backend etc)
        # TODO: warn if backend xmls are not found in memory, so that you know
        # what you are missing?

        # change_nbc_version was introduced in version 3.28.0 (with changes
        # going back to 3.26.0). For versions older than that there is no
        # rename information available!
        if (
            self._version
            and self._backend_version
            and max(V(self._version), V(self._backend_version)) < V("3.28.0")
        ):
            logger.warning(
                "Rename information was added in 3.28.0. It is highly "
                "recommended to at least use this version."
            )

        super().set_backend_properties(structure_xml)

    def readHomogeneous(self, occurrence):
        """Read the value of homogeneousTime

        Returns:
            0: IDS_TIME_MODE_HETEROGENEOUS; Dynamic nodes may be asynchronous, their timebase is located as indicted in the "Coordinates" column of the documentation
            1: IDS_TIME_MODE_HOMOGENEOUS; All dynamic nodes are synchronous, their common timebase is the "time" node that is the child of the nearest parent IDS
            2: IDS_TIME_MODE_INDEPENDENT; No dynamic node is filled in the IDS (dynamic nodes _will_ be skipped by the Access Layer)
        """
        homogeneousTime = IDS_TIME_MODE_UNKNOWN
        if occurrence == 0:
            path = self._name
        else:
            path = self._name + "/" + str(occurrence)

        # only read from the backend if it is not defined locally.
        homogeneousTime = self.ids_properties.homogeneous_time

        if homogeneousTime.value == EMPTY_INT:
            status, ctx = self._ull.ual_begin_global_action(self._idx, path, READ_OP)
            context_store[ctx] = context_store[self._idx] + "/" + path
            if status != 0:
                raise ALException(
                    "Error calling ual_begin_global_action() in readHomogeneous()"
                    "operation",
                    status,
                )

            status, homogeneousTime = self._ull.ual_read_data(
                ctx, "ids_properties/homogeneous_time", "", INTEGER_DATA, 0
            )

            if status != 0:
                raise ALException("ERROR: homogeneous_time cannot be read.", status)

            status = self._ull.ual_end_action(ctx)
            context_store.pop(ctx)

            if status != 0:
                raise ALException(
                    "Error calling ual_end_action() in readHomogeneous() operation",
                    status,
                )
        return homogeneousTime

    def read_data_dictionary_version(self, occurrence):
        data_dictionary_version = ""
        path = self._name
        if occurrence != 0:
            path += "/" + str(occurrence)

        status, ctx = self._ull.ual_begin_global_action(self._idx, path, READ_OP)
        context_store[ctx] = context_store[self._idx] + "/" + path
        if status != 0:
            raise ALException(
                "Error calling ual_begin_global_action() in read_data_dictionary_version() operation",
                status,
            )

        status, data_dictionary_version = self._ull.ual_read_data_string(
            ctx, "ids_properties/version_put/data_dictionary", "", CHAR_DATA, 1
        )
        if status != 0:
            raise ALException("ERROR: data_dictionary_version cannot be read.", status)
        status = self._ull.ual_end_action(ctx)
        context_store.pop(ctx)
        if status != 0:
            raise ALException(
                "Error calling ual_end_action() in read_data_dictionary_version() operation",
                status,
            )
        return data_dictionary_version

    def get(self, occurrence=0, **kwargs):
        """Get data from UAL backend storage format and overwrite data in node

        Tries to dynamically build all needed information for the UAL. As this
        is the root node, it is simple to construct UAL paths and contexts at
        this level. Should have an open database.
        """
        path = None
        if occurrence == 0:
            path = self._name
        else:
            path = self._name + "/" + str(occurrence)

        homogeneousTime = self.readHomogeneous(occurrence)
        if homogeneousTime not in IDS_TIME_MODES:
            logger.error(
                "Unknown time mode %s, stop getting of %s", homogeneousTime, self._name
            )
            return

        backend_version = self.read_data_dictionary_version(occurrence)
        if self._backend_xml_path:
            # If we have specified a preference backend_version is completely ignored.
            logger.info("using backend_xml_path %s", self._backend_xml_path)
        elif self._backend_version:
            # If we have specified a preference:
            if backend_version != self._backend_version:
                logger.warning(
                    "Specified backend version '%s' does not "
                    "correspond to version_put '%s'",
                    self._backend_version,
                    backend_version,
                )
                backend_version = self._backend_version
            logger.info("using backend_version %s", self._backend_version)

        # building the backend_xml is only necessary in some cases
        if self._backend_xml_path or (
            backend_version and backend_version != self._parent._imas_version
        ):
            self._read_backend_xml(
                version=backend_version, xml_path=self._backend_xml_path
            )

        # TODO: Do not use global context
        status, ctx = self._ull.ual_begin_global_action(self._idx, path, READ_OP)
        if status != 0:
            raise ALException(
                "Error calling ual_begin_global_action() for {!s}".format(self._name),
                status,
            )
        context_store[ctx] = context_store[self._idx] + path

        logger.debug("{:53.53s} get".format(self._name))
        super().get(ctx, homogeneousTime, **kwargs)

        status = self._ull.ual_end_action(ctx)
        context_store.pop(ctx)
        if status != 0:
            raise ALException(
                "Error calling ual_end_action() for {!s}".format(self._name), status
            )

    def deleteData(self, occurrence=0):
        """Delete UAL backend storage data

        Tries to dynamically build all needed information for the UAL. As this
        is the root node, it is simple to construct UAL paths and contexts at
        this level. Should have an open database.
        """
        if not np.issubdtype(type(occurrence), np.integer):
            raise ValueError("Occurrence should be an integer")

        rel_path = self.getRelCTXPath(self._idx)
        if occurrence != 0:
            rel_path += "/" + str(occurrence)

        status, ctx = self._ull.ual_begin_global_action(self._idx, rel_path, WRITE_OP)
        context_store[ctx] = context_store[self._idx] + rel_path
        if status < 0:
            raise ALException(
                'ERROR: ual_begin_global_action failed for "{!s}"'.format(rel_path),
                status,
            )

        for child_name in self._children:
            child = getattr(self, child_name)
            if isinstance(child, (IDSStructArray, IDSPrimitive)):
                status = self._ull.ual_delete_data(ctx, child_name)
                if status != 0:
                    raise ALException(
                        'ERROR: ual_delete_data failed for "{!s}". Status code {!s}'.format(
                            rel_path + "/" + child_name
                        ),
                        status,
                    )
            else:
                status = child.delete(ctx)
                if status != 0:
                    raise ALException(
                        'ERROR: delete failed for "{!s}". Status code {!s}'.format(
                            rel_path + "/" + child_name
                        ),
                        status,
                    )
        status = self._ull.ual_end_action(ctx)
        context_store.pop(ctx)
        if status < 0:
            raise ALException(
                'ERROR: ual_end_action failed for "{!s}"'.format(rel_path), status
            )
        return 0

    def to_ualstore(self, ual_data_store, path=None, occurrence=0):
        """Put data into UAL backend storage format

        As all children _should_ support being put, just call `put` blindly.

        Tries to dynamically build all needed information for the UAL. As this
        is the root node, it is simple to construct UAL paths and contexts at
        this level. Should have an open database.
        """
        if path is not None:
            raise NotImplementedError("Explicit paths, implicitly handled by structure")

        path = self.path
        if occurrence != 0:
            path += "/" + str(occurrence)

        # Determine the time_mode.
        homogeneousTime = self.ids_properties.homogeneous_time.value
        if homogeneousTime == IDS_TIME_MODE_UNKNOWN:
            logger.error(
                "IDS %s is found to be EMPTY (homogeneous_time undefined). PUT quits with no action.",
                self,
            )
            return
        if homogeneousTime not in IDS_TIME_MODES:
            raise ALException(
                "ERROR: ids_properties.homogeneous_time should be set to IDS_TIME_MODE_HETEROGENEOUS, IDS_TIME_MODE_HOMOGENEOUS or IDS_TIME_MODE_INDEPENDENT."
            )
        if homogeneousTime == IDS_TIME_MODE_HOMOGENEOUS and len(self.time.value) == 0:
            raise ALException(
                "ERROR: the IDS%time vector of an homogeneous_time IDS must have a non-zero length."
            )

        # Delete the data in the store
        # TODO: handle mode correctly!
        self.deleteData(occurrence)

        # Begin a write action
        status, ctx = self._ull.ual_begin_global_action(self._idx, path, WRITE_OP)
        if status != 0:
            raise ALException(
                "Error calling ual_begin_global_action() for {!s}".format(
                    self._name, status
                )
            )

        context_store[ctx] = path
        for child_name in self._children:
            child = getattr(self, child_name)
            dbg_str = " " * self.depth + "- " + child_name
            if not isinstance(child, IDSPrimitive):
                logger.debug("{:53.53s} put".format(dbg_str))
            child.put(ctx, homogeneousTime)

        context_store.pop(ctx)
        status = self._ull.ual_end_action(ctx)
        if status != 0:
            raise ALException(
                "Error calling ual_end_action() for {!s}".format(self._name), status
            )

    def setExpIdx(self, idx):
        logger.warning(
            "setExpIdx is deprecated, call self.setPulseCtx instead", FutureWarning
        )
        self.setPulseCtx(idx)

    def put(self, occurrence=0, data_store=None):
        if data_store is None:
            data_store = self._data_store
            if hasattr(self.ids_properties, "version_put"):
                self.ids_properties.version_put.data_dictionary = (
                    self._backend_version or self._version
                )
                # TODO: self.ids_properties.version_put.access_layer =  # get the access layer version number here
                self.ids_properties.version_put.access_layer_language = "Python"
        self.to_ualstore(data_store, path=None, occurrence=occurrence)

    @property
    def _data_store(self):
        return self._parent._data_store

    @property
    def _idx(self):
        return self._data_store._idx

    @cached_property
    def backend_version(self):
        return self.__getattribute__("_backend_version")

    @classmethod
    def getMaxOccurrences(self):
        raise NotImplementedError("{!s}.getMaxOccurrences()".format(self))
        return cls._MAX_OCCURRENCES

    def initIDS(self):
        raise NotImplementedError("{!s}.initIDS()".format(self))

    def partialGet(self, dataPath, occurrence=0):
        raise NotImplementedError(
            "{!s}.partialGet(dataPath, occurrence=0)".format(self)
        )

    def getField(self, dataPath, occurrence=0):
        raise NotImplementedError("{!s}.getField(dataPath, occurrence=0)".format(self))

    def _getFromPath(self, dataPath, occurrence, analyzeTime, data_store=None):
        # Retrieve partial IDS data without reading the full database content
        raise NotImplementedError(
            "{!s}.getField(dataPath, occurrence, analyzeTime, data_store=None)".format(
                self
            )
        )
