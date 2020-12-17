import random
import numpy as np
import logging
import string

# TODO: import these from imaspy (i.e. expose them publicly?)
from imaspy.ids_struct_array import IDSStructArray
from imaspy.ids_structure import IDSStructure
from imaspy.ids_toplevel import IDSToplevel
from imaspy.ids_root import IDSRoot

root_logger = logging.getLogger("imaspy")
logger = root_logger
logger.setLevel(logging.DEBUG)


def randdims(n):
    """Return a list of n random numbers between 1 and 10 representing
    the shapes in n dimensions"""
    return random.sample(range(1, 10), n)


def random_string():
    return "".join(
        random.choice(string.ascii_uppercase + string.digits)
        for i in range(random.randint(0, 1024))
    )


def random_data(ids_type, ndims):
    if ndims < 0:
        raise NotImplementedError("Negative dimensions are not supported")

    if ids_type == "STR":
        if ndims == 0:
            return random_string()
        elif ndims == 1:
            return [random_string() for i in range(random.randint(0, 3))]
        else:
            raise NotImplementedError(
                "Strings of dimension 2 or higher " "are not supported"
            )
        return np.random.randint(0, 1000, size=randdims(ndims))
    elif ids_type == "INT":
        return np.random.randint(0, 1000, size=randdims(ndims))
    elif ids_type == "FLT":
        return np.random.random_sample(size=randdims(ndims))
    else:
        logger.warn("Unknown data type %s requested to fill, ignoring", ids_type)


def fill_with_random_data(structure):
    for child_name in structure._children:
        child = structure[child_name]

        if type(child) in [IDSStructure, IDSToplevel, IDSRoot]:
            fill_with_random_data(child)
        elif type(child) == IDSStructArray:
            if len(child.value) == 0:
                # make 3 copies of _element_structure and fill those
                child.append([child._element_structure] * 3)
                for a in child.values:
                    fill_with_random_data(a)
        else:  # leaf node
            child.value = random_data(child._ids_type, child._ndims)
