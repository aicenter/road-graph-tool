class InvalidInputError(Exception):
    pass

class MissingInputError(Exception):
    pass

class TableNotEmptyError(Exception):
    pass

class SubprocessError(Exception):
    pass

class ImportConflictError(Exception):
    """Imported nodes or ways have the ids of nodes or ways already in the database, but they differ from them.

    *element* is the plural name of the element type, *conflicts* are the ids of the differing elements, and
    *differing* names the properties compared.
    """

    REPORTED_CONFLICTS = 10

    def __init__(self, element: str, conflicts: list[int], differing: str):
        reported = ", ".join(str(element_id) for element_id in conflicts[:self.REPORTED_CONFLICTS])
        more = len(conflicts) - self.REPORTED_CONFLICTS
        super().__init__(
            f"{len(conflicts)} imported {element} are already in the database with different {differing}: "
            f"{reported}{f' and {more} more' if more > 0 else ''}. The areas of one schema have to be imported from "
            f"the same OSM data and with the same network profile, see the README section "
            f"\"Multiple areas in one schema\"."
        )
        self.conflicts = conflicts

class OverpassRequestError(Exception):
    """An Overpass API request failed. The message explains the cause; the original error is chained."""
    pass