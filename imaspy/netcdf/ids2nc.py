# This file is part of IMASPy.
# You should have received the IMASPy LICENSE file with this project.
"""NetCDF IO support for IMASPy. Requires [netcdf] extra dependencies.
"""

from typing import Iterator, Tuple

import netCDF4

from imaspy.ids_base import IDSBase
from imaspy.ids_data_type import IDSDataType
from imaspy.ids_primitive import IDSPrimitive
from imaspy.ids_struct_array import IDSStructArray
from imaspy.ids_structure import IDSStructure
from imaspy.ids_toplevel import IDSToplevel
from imaspy.netcdf.nc_metadata import NCMetadata


def nc_tree_iter(
    node: IDSStructure, aos_index: Tuple[int, ...] = ()
) -> Iterator[Tuple[Tuple[int, ...], IDSBase]]:
    """Tree iterator that tracks indices of all ancestor array of structures.

    Args:
        node: IDS node to iterate over

    Yields:
        (aos_index, node) for all filled leaf nodes and array of structures nodes.
    """
    for child in node.iter_nonempty_():
        if isinstance(child, IDSStructArray):
            yield (aos_index, child)
            for i in range(len(child)):
                yield from nc_tree_iter(child[i], aos_index + (i,))

        elif isinstance(child, IDSStructure):
            yield from nc_tree_iter(child, aos_index)

        else:
            yield (aos_index, child)


def ids2nc(ids: IDSToplevel, group: netCDF4.Group):
    """Store IDS using IMAS conventions in the provided group.

    Args:
        ids: IDS to store
        group: Empty netCDF4 Group
    """
    # Get NCMetadata for this IDS
    # TODO: cache this?
    ncmeta = NCMetadata(ids.metadata)

    # Keep track of used dimensions, and the maximum size
    used_dimensions = {}  # dim_name: size
    # Keep track of filled data
    filled_data = {}  # path: {aos_indices: node}

    # homogeneous_time boolean
    homogeneous_time = ids.ids_properties.homogeneous_time == 1

    # Loop over the IDS to calculate the dimensions sizes
    for aos_index, node in nc_tree_iter(ids):
        dimensions = ncmeta.get_dimensions(node.metadata.path_string, homogeneous_time)
        if node.metadata.ndim:
            shape = node.shape
            for i in range(-node.metadata.ndim, 0):
                dim_name = dimensions[i]
                used_dimensions[dim_name] = max(
                    used_dimensions.get(dim_name, 0), shape[i]
                )
        if isinstance(node, IDSPrimitive):
            filled_data.setdefault(node.metadata.path_string, {})[aos_index] = node

    # Create NC dimensions
    for dimension, size in used_dimensions.items():
        group.createDimension(dimension, size)

    # Loop over the IDS another time to store the data
    for path in filled_data:
        metadata = ids.metadata[path]

        # Determine datatype
        dtype = metadata.data_type.numpy_dtype
        if dtype is None and metadata.data_type == IDSDataType.STR:
            dtype = str
        assert dtype is not None

        # Create variable
        var = group.createVariable(
            metadata.path_string.replace("/", "."),
            dtype,
            ncmeta.get_dimensions(metadata.path_string, homogeneous_time),
            compression=None if dtype is str else "zlib",
            complevel=1,
        )

        # Fill attributes:
        if metadata.units:
            var.units = metadata.units
        var.documentation = metadata.documentation
        coordinates = ncmeta.get_coordinates(metadata.path_string, homogeneous_time)
        if coordinates:
            var.coordinates = coordinates

        # Fill variable
        if var.ndim == 0:
            # Directly set scalar values
            assert len(filled_data[path]) == 1
            var[()] = filled_data[path][()].value

        else:
            # Tensorize in-memory
            # TODO: depending on the data, tmp_var may be HUGE, we may need a more
            # efficient assignment algorithm for large and/or irregular data
            var.set_auto_mask(False)
            tmp_var = var[()]
            for aos_coords, node in filled_data[path].items():
                coords = aos_coords if metadata.ndim == 0 else aos_coords + (...,)
                tmp_var[coords] = node.value

            # So the following assignment is more efficient
            var[()] = tmp_var
            del tmp_var
