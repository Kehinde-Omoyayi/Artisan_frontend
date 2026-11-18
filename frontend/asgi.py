import os
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "frontend.settings")

#: Force this project's settings: a ``DJANGO_SETTINGS_MODULE`` left in the
#: environment by the API project must never be honoured here.
if not os.environ.get("DJANGO_SETTINGS_MODULE", "").startswith("frontend."):
    os.environ["DJANGO_SETTINGS_MODULE"] = "frontend.settings"

application = get_asgi_application()
