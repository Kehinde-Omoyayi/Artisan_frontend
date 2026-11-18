#!/usr/bin/env python
"""Management entry point for the standalone Artisan Market frontend.

This project renders every page and calls the API over HTTP; it holds no
marketplace data of its own. The settings module is *forced* here rather than
merely defaulted, because a ``DJANGO_SETTINGS_MODULE`` left over in the shell
(or exported for the API project) would otherwise be honoured silently and this
app would boot with the API's settings and stop serving pages.
"""
import os
import sys

PROJECT_PREFIX = "frontend."
DEFAULT_SETTINGS = "frontend.settings"


def _warn_if_projects_were_merged():
    """Catch the API project being unpacked into this folder."""
    here = os.path.dirname(os.path.abspath(__file__))
    if os.path.isdir(os.path.join(here, "Artisan_platform")):
        sys.stderr.write(
            "\n"
            "  *** The API project appears to be unpacked INSIDE the frontend   ***\n"
            "  *** project (found an 'Artisan_platform/' package here).         ***\n"
            "  *** Unpack the two zips into two SEPARATE folders.               ***\n"
            "\n"
        )


if __name__ == "__main__":
    current = os.environ.get("DJANGO_SETTINGS_MODULE", "")
    if not current.startswith(PROJECT_PREFIX):
        if current:
            sys.stderr.write(
                "Ignoring DJANGO_SETTINGS_MODULE=%r for the frontend project; "
                "using %r.\n" % (current, DEFAULT_SETTINGS)
            )
        os.environ["DJANGO_SETTINGS_MODULE"] = DEFAULT_SETTINGS
    _warn_if_projects_were_merged()
    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)
