class InvalidInputError(Exception):
    pass

class MissingInputError(Exception):
    pass

class TableNotEmptyError(Exception):
    pass

class SubprocessError(Exception):
    pass

class OverpassRequestError(Exception):
    """An Overpass API request failed. The message explains the cause; the original error is chained."""
    pass