"""Profile helpers backed by the API's catalogue.

The register itself (30k institutions, 8 MB of JSON) lives in the API project;
:mod:`frontend.catalogue_source` fetches and caches it. This module keeps only
the profile rules: the default location chain and what a saved institution must
resolve to.
"""

from .catalogue_source import catalogue_page, defaults, institution_record

DEFAULTS = defaults()


def initialize_profile_location(form):
    if form.is_bound:
        return
    if not any(
        str(form.initial.get(k) or "").strip()
        for k in ("state", "area", "nearest_institution")
    ) and str(form.initial.get("country") or "").strip() in ("", "Nigeria"):
        form.initial.update(DEFAULTS)


def _candidates(name: str):
    payload = catalogue_page({"q": name})
    wanted = name.casefold()
    return [
        row
        for row in payload.get("results") or []
        if str(row.get("name") or "").casefold() == wanted
    ]


def clean_profile_location(form, cleaned):
    from .geography import canonical_location

    selected = str(cleaned.get("nearest_institution") or "").strip()
    source_id = str(cleaned.get("nearest_institution_source_id") or "").strip()
    original = str(form.initial.get("nearest_institution") or "")
    if selected:
        match = institution_record(source_id) if source_id else None
        if source_id and (not match or match["name"].casefold() != selected.casefold()):
            form.add_error(
                "nearest_institution", "Choose an institution from the search results."
            )
            return cleaned
        if not match:
            candidates = _candidates(selected)
            # A unique typed name can resolve even when no location was chosen.
            if len(candidates) == 1:
                match = candidates[0]
            elif candidates:
                compatible = [
                    r
                    for r in candidates
                    if all(
                        not str(cleaned.get(k) or "").strip()
                        or r[k].casefold() == str(cleaned[k]).strip().casefold()
                        for k in ("country", "state", "area")
                    )
                ]
                if len(compatible) == 1:
                    match = compatible[0]
                else:
                    form.add_error(
                        "nearest_institution",
                        "Several institutions have this name. Choose a search result showing its location.",
                    )
                    return cleaned
        if match:
            # User chose to align geography, rather than prohibit an out-of-area choice.
            cleaned.update({k: match[k] for k in ("country", "state", "area")})
            cleaned["nearest_institution"] = match["name"]
            cleaned["nearest_institution_abbreviation"] = next(
                iter(match.get("abbreviations") or []), ""
            )
            cleaned["nearest_institution_source_id"] = match["source_id"]
            return cleaned
        changed = any(
            str(cleaned.get(k) or "").strip().casefold()
            != str(form.initial.get(k) or "").strip().casefold()
            for k in ("country", "state", "area")
        )
        if selected == original and not changed:
            cleaned["nearest_institution_abbreviation"] = str(
                form.initial.get("nearest_institution_abbreviation") or ""
            )
            return cleaned
        form.add_error(
            "nearest_institution",
            "Choose an institution from the catalogue, or clear it.",
        )
        return cleaned
    cleaned["nearest_institution"] = ""
    cleaned["nearest_institution_abbreviation"] = ""
    cleaned["nearest_institution_source_id"] = ""
    current = {
        k: str(cleaned.get(k) or "").strip() for k in ("country", "state", "area")
    }
    if all(current.values()):
        canonical = canonical_location(**current)
        if canonical:
            cleaned.update(canonical)
        elif any(
            current[k].casefold() != str(form.initial.get(k) or "").strip().casefold()
            for k in current
        ):
            form.add_error("area", "Choose an area matching your country and state.")
    return cleaned
