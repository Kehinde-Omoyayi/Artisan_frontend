"""One command that answers: can this frontend actually reach its API?

    python manage.py api_check

It prints the address being called, whether it answers, how long a call takes,
and the state of the two things pages need first (the geography index and the
institution register). Run it whenever a page shows an empty picker or the site
feels slow: the first line that says "FAILED" is the fault.
"""
import time

import requests
from django.conf import settings
from django.core.management.base import BaseCommand

#: Public reads that every page depends on, cheapest first. The label says what
#: an empty answer means on the page that uses it.
CHECKS = [
    ("categories", "/services/categories/"),
    ("services", "/services/service_cat/?limit=1"),
    ("locations", "/services/locations/?limit=1"),
    ("artisan directory", "/profile/artisan/details/?limit=1"),
    ("geography index", "/catalogue/geography/index/"),
    ("institution register", "/catalogue/institutions/?limit=1"),
]


class Command(BaseCommand):
    help = "Check that this frontend can reach the marketplace API, and time it."

    def add_arguments(self, parser):
        parser.add_argument(
            "--runs",
            type=int,
            default=3,
            help="How many times to time each call (default 3).",
        )

    def handle(self, *args, **options):
        base = str(settings.ARTISAN_API_BASE_URL).rstrip("/")
        runs = max(1, int(options["runs"]))
        self.stdout.write(f"Frontend -> API: {base}")
        self.stdout.write(f"Transport: {getattr(settings, 'ARTISAN_API_TRANSPORT', 'http')}")
        self.stdout.write(f"Timeout: {getattr(settings, 'ARTISAN_API_TIMEOUT', '-')} s")

        if "127.0.0.1" not in base and "localhost" not in base:
            self.stdout.write(
                self.style.WARNING(
                    "This is a public address. If the API is running on this machine, "
                    "set ARTISAN_API_BASE_URL=http://127.0.0.1:8000/api/v1 -- every API "
                    "call on every page is otherwise an internet round trip."
                )
            )

        failures = 0
        for label, path in CHECKS:
            timings = []
            last_error = ""
            size = 0
            last_payload = None
            for _ in range(runs):
                started = time.perf_counter()
                try:
                    response = requests.get(
                        f"{base}{path}",
                        timeout=(3.5, float(getattr(settings, "ARTISAN_API_TIMEOUT", 20))),
                        headers={"Accept": "application/json", "Connection": "close"},
                    )
                except requests.RequestException as exc:
                    last_error = f"{type(exc).__name__}: {exc}"
                    break
                timings.append((time.perf_counter() - started) * 1000)
                size = len(response.content)
                try:
                    last_payload = response.json()
                except ValueError:
                    last_payload = None
                if response.status_code >= 400:
                    last_error = f"HTTP {response.status_code}"
                    break

            if last_error or not timings:
                failures += 1
                self.stdout.write(self.style.ERROR(f"FAILED  {label:<22} {path}  {last_error}"))
                hint = _hint(last_error, base)
                if hint:
                    self.stdout.write(f"        {hint}")
                continue

            best = min(timings)
            worst = max(timings)
            self.stdout.write(
                f"ok      {label:<22} {path}  {best:6.0f} ms best, {worst:6.0f} ms worst, "
                f"{size:,} B{_tally(label, last_payload)}"
            )

        if failures:
            self.stdout.write(
                self.style.ERROR(
                    f"\n{failures} of {len(CHECKS)} checks failed. Start the API with:  "
                    "python manage.py runserver 127.0.0.1:8000  (in the API project)"
                )
            )
            raise SystemExit(1)

        self.stdout.write(self.style.SUCCESS("\nEvery check answered. The link is healthy."))
        self.stdout.write(
            "A page makes 3 to 6 of these calls, so a page should stay well under a "
            "second. If a page is slower than that, its log line names the page."
        )


#: What "empty" means for each catalogue read, said in the words the page uses.
EMPTY_MEANING = {
    "categories": "no category exists yet, so every category picker is empty",
    "services": "no service exists yet, so the category picker on My services has nothing to list",
    "locations": "no area exists yet, so area pickers are empty",
    "geography index": "the geographic catalogue is empty, so country/state/area pickers are empty",
    "institution register": "the institution register is empty; run seed_institutions in the API project",
}


def _tally(label, payload):
    """Item count for a catalogue read, plus a plain sentence when it is zero."""
    if isinstance(payload, list):
        total = len(payload)
    elif isinstance(payload, dict):
        if "count" in payload:
            total = payload.get("count")
        elif isinstance(payload.get("results"), list):
            total = len(payload["results"])
        else:
            return ""
    else:
        return ""
    if not isinstance(total, int):
        return ""
    note = ""
    if total == 0 and label in EMPTY_MEANING:
        note = f"  <-- EMPTY: {EMPTY_MEANING[label]}"
    return f"  ({total:,} rows){note}"


def _hint(error, base):
    """A sentence that turns a status code into the thing to change."""
    if "HTTP 400" in error:
        return (
            "The API refused the host name. Add this machine's name to ALLOWED_HOSTS "
            "in the API's .env (127.0.0.1 and localhost unless a tunnel is in front)."
        )
    if "HTTP 404" in error:
        return (
            f"Nothing is served at {base}. Check that ARTISAN_API_BASE_URL ends in "
            "/api/v1 and that the API project is the one running on port 8000."
        )
    if "HTTP 401" in error or "HTTP 403" in error:
        return "The API is up but refused this read; it is a permissions/configuration fault, not a connection one."
    if "HTTP 5" in error:
        return "The API answered with a server error; its own log holds the traceback."
    if "ConnectionError" in error or "Timeout" in error or "NewConnectionError" in error:
        return (
            "Nothing answered. Start the API (python manage.py runserver 127.0.0.1:8000) "
            "and check the address and port."
        )
    return ""
