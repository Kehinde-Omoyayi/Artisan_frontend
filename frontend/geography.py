"""Worldwide geography, served by the API.

The list itself lives in the API project (``catalogue/data``); this module only
caches it for the request that needs it. See ``catalogue_source``.
"""

from .catalogue_source import world_geography


def canonical_location(country, state, area):
    """Return catalogue spelling for a valid country/state/locality triple."""

    def find(value, candidates):
        key = str(value or "").strip().casefold()
        return next((name for name in candidates if name.casefold() == key), None)

    data = world_geography()
    country = find(country, data)
    if country is None:
        return None
    state = find(state, data[country])
    if state is None:
        return None
    area = find(area, data[country][state])
    if area is None:
        return None
    return {"country": country, "state": state, "area": area}
