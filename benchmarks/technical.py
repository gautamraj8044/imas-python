import imaspy
import imas


def timeraw_create_default_imaspy_factory():
    # timeraw to ensure that nothing is cached
    return """
    import imaspy
    imaspy.IDSFactory()
    """


def timeraw_import_imaspy():
    return """
    import imaspy
    """


def timeraw_import_imas():
    return """
    import imas
    """


# It would be nice if we could track these, but unfortunately it breaks things like
# `asv compare` :(
"""
def track_imas_versions():
    equilibrium = imas.equilibrium()
    equilibrium.ids_properties.homogeneous_time = imas.imasdef.IDS_TIME_MODE_INDEPENDENT
    dbentry = imas.DBEntry(imas.imasdef.MEMORY_BACKEND, "test", 1, 1)
    dbentry.create()
    dbentry.put(equilibrium)
    equilibrium = dbentry.get("equilibrium")
    return (
        equilibrium.ids_properties.version_put.data_dictionary,
        equilibrium.ids_properties.version_put.access_layer,
    )


def track_imaspy_dd_version():
    return imaspy.IDSFactory().version
"""
