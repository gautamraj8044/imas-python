# This file is part of IMASPy.
# You should have received IMASPy LICENSE file with this project.
""" IDS StructArray represents an Array of Structures in the IDS tree.
This contains references to :py:class:`IDSStructure`s

* :py:class:`IDSStructArray`
"""


from packaging.version import Version as V

from imaspy.al_exception import ALException
from imaspy.context_store import context_store
from imaspy.ids_defs import needs_imas
from imaspy.ids_mixin import IDSMixin
from imaspy.ids_structure import IDSStructure, get_coordinates
from imaspy.setup_logging import root_logger as logger


class IDSStructArray(IDSStructure, IDSMixin):
    """IDS array of structures (AoS) node

    Represents a node in the IDS tree. Does not itself contain data,
    but contains references to IDSStructures
    """

    def getAOSPath(self, ignore_nbc_change=1):
        raise NotImplementedError("{!s}.getAOSPath(ignore_nbc_change=1)".format(self))

    @staticmethod
    def getAoSElement(self):
        logger.warning(
            "getAoSElement is deprecated, you should never need this", FutureWarning
        )
        return self._element_structure

    @staticmethod
    def getBackendInfo(parentCtx, index, homogeneousTime):  # Is this specific?
        raise NotImplementedError("getBackendInfo(parentCtx, index, homogeneousTime)")

    def __init__(self, parent, name, structure_xml, base_path_in="element"):
        """Initialize IDSStructArray from XML specification

        Args:
            parent: Parent structure. Can be anything, but at database write
                time should be something with a path attribute
            name: Name of the node itself. Will be used in path generation when
                stored in DB
            structure_xml: Object describing the structure of the IDS. Usually
                an instance of `xml.etree.ElementTree.Element`
            base_path_in: Not implemented yet
        """
        super().__init__(parent, name, structure_xml)

        self._base_path = base_path_in
        self._convert_ids_types = False

        # signal that this is an array-type addressing
        self._array_type = True

        # Which xml settings to use for backends
        self._backend_child_xml = None
        self._backend_name = None

        # Initialize with an 0-length list
        self.value = []

        self._convert_ids_types = True

    @property
    def _element_structure(self):
        """Prepare an element structure JIT"""
        struct = IDSStructure(self, self._name + "_el", self._structure_xml)
        return struct

    def __setattr__(self, key, value):
        object.__setattr__(self, key, value)

    def __getattr__(self, key):
        object.__getattribute__(self, key)

    def __getitem__(self, item):
        # value is a list, so the given item should be convertable to integer
        list_idx = int(item)
        return self.value[list_idx]

    def __setitem__(self, item, value):
        # value is a list, so the given item should be convertable to integer
        list_idx = int(item)
        if hasattr(self, "_convert_ids_types") and self._convert_ids_types:
            # Convert IDS type on set time. Never try this for hidden attributes!
            if list_idx in self.value:
                struct = self.value[list_idx]
                struct.value = value
        self.value[list_idx] = value

    def __iter__(self):
        return iter(self.value)

    def append(self, elt):
        """Append elements to the end of the array of structures.

        Parameters
        ----------
        """
        if not isinstance(elt, list):
            elements = [elt]
        else:
            elements = elt
        for e in elements:
            # Just blindly append for now
            # TODO: Maybe check if user is not trying to append weird elements
            if self.metadata.maxoccur and len(self.value) >= self.metadata.maxoccur:
                raise RuntimeError(
                    "Maxoccur is set to %s for %s, not adding %s"
                    % (
                        self.metadata.maxoccur,
                        self._base_path,
                        elt,
                    )
                )
                return
            e._convert_ids_types = True
            e._parent = self
            self.value.append(e)
            # only now can we process the backend properties
            if self._backend_child_xml:
                e.set_backend_properties(self._backend_child_xml)

    def resize(self, nbelt, keep=False):
        """Resize an array of structures.

        nbelt : int
            The number of elements for the targeted array of structure,
            which can be smaller or bigger than the size of the current
            array if it already exists.
        keep : bool, optional
            Specifies if the targeted array of structure should keep
            existing data in remaining elements after resizing it.
        """
        if not keep:
            self.value = []
        cur = len(self.value)
        if nbelt > cur:
            new_els = []
            for _ in range(nbelt - cur):
                new_el = self._element_structure
                new_el._parent = self
                new_el._convert_ids_types = True
                new_els.append(new_el)
            self.append(new_els)
        elif nbelt < cur:
            raise NotImplementedError("Making IDSStructArrays smaller")
            for i in range(nbelt, cur):
                self.value.pop()
        elif not keep:  # case nbelt = cur
            raise NotImplementedError("Overwriting IDSStructArray elements")
            self.append(
                [
                    process_charge_state__structArrayElement(self._base_path)
                    for i in range(nbelt)
                ]
            )

    def _getData(
        self, aosCtx, indexFrom, indexTo, homogeneousTime, nodePath, analyzeTime
    ):
        raise NotImplementedError(
            "{!s}._getData(aosCtx, indexFrom, indexTo, homogeneousTime, nodePath, analyzeTime)".format(
                self
            )
        )

    @needs_imas
    def get(self, parentCtx, homogeneousTime):
        """Get data from UAL backend storage format and overwrite data in node

        Tries to dynamically build all needed information for the UAL.
        """
        timeBasePath = self.getTimeBasePath(homogeneousTime, 0)
        nodePath = self.getRelCTXPath(parentCtx)
        status, aosCtx, size = self._ull.ual_begin_arraystruct_action(
            parentCtx, nodePath, timeBasePath, 0
        )
        if status < 0:
            raise ALException(
                'ERROR: ual_begin_arraystruct_action failed for "process/products/element"',
                status,
            )

        if size < 1:
            return
        if aosCtx > 0:
            context_store[aosCtx] = (
                context_store[parentCtx] + "/" + nodePath + "/" + str(1)
            )
        self.resize(size)
        for i in range(size):
            context_store.update(
                aosCtx, context_store[parentCtx] + "/" + nodePath + "/" + str(i + 1)
            )  # Update context
            self.value[i].get(aosCtx, homogeneousTime)
            self._ull.ual_iterate_over_arraystruct(aosCtx, 1)

        if aosCtx > 0:
            context_store.pop(aosCtx)
            self._ull.ual_end_action(aosCtx)

    @needs_imas
    def put(self, parentCtx, homogeneousTime, **kwargs):
        """Put data into UAL backend storage format

        As all children _should_ support being put, just call `put` blindly.
        """
        timeBasePath = self.getTimeBasePath(homogeneousTime)
        # TODO: This might be to simple for array of array of structures
        nodePath = self.getRelCTXPath(parentCtx)
        status, aosCtx, size = self._ull.ual_begin_arraystruct_action(
            parentCtx, nodePath, timeBasePath, len(self.value)
        )
        if status != 0 or aosCtx < 0:
            raise ALException(
                'ERROR: ual_begin_arraystruct_action failed for "{!s}"'.format(
                    self._name
                ),
                status,
            )
        context_store[aosCtx] = context_store[parentCtx] + "/" + nodePath + "/" + str(0)

        for i in range(size):
            context_store.update(
                aosCtx, context_store[parentCtx] + "/" + nodePath + "/" + str(i + 1)
            )  # Update context
            # This loops over the whole array
            dbg_str = " " * self.depth + "- [" + str(i + 1) + "]"
            logger.debug("{:53.53s} put".format(dbg_str))
            self.value[i].put(aosCtx, homogeneousTime, **kwargs)
            status = self._ull.ual_iterate_over_arraystruct(aosCtx, 1)
            if status != 0:
                raise ALException(
                    'ERROR: ual_iterate_over_arraystruct failed for "{!s}"'.format(
                        self._name
                    ),
                    status,
                )

        status = self._ull.ual_end_action(aosCtx)
        context_store.pop(aosCtx)
        if status != 0:
            raise ALException(
                'ERROR: ual_end_action failed for "{!s}"'.format(self._name), status
            )

    def set_backend_properties(self, structure_xml):
        """set the (structure) backend properties of each child
        and store the structure_xml for new children"""

        _, skip = IDSMixin.set_backend_properties(self, structure_xml)
        # skip if structure_xml was already seen
        if skip:
            return

        # the children have the same structure_xml as the current element
        for child in self:
            child.set_backend_properties(structure_xml)

        # Set _backend_xml_structure which can be used to set_backend_properties
        # on future self._element_structure s
        self._backend_child_xml = structure_xml

        # we do not want to keep the 'other' reference around though
        for child in self:
            try:
                del child._backend_structure_xml
            except AttributeError:
                pass
