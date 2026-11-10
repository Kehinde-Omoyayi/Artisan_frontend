from django.urls import include, path
from frontend import views

urlpatterns = [
    path("catalogue/institutions/", views.institution_catalogue, name="institution-catalogue"),
    path("catalogue/geography.json", views.catalogue_geography_index, name="catalogue-geography-index"),
    path(
        "catalogue/geography/<slug:slug>.json",
        views.catalogue_geography_country,
        name="catalogue-geography-country",
    ),
    # Promotion form options, fetched once by the browser when a target group
    # opens instead of being inlined into the page (thousands of rows).
    path(
        "catalogue/promotion-picker.json",
        views.promotion_picker,
        name="promotion-picker",
    ),
    # Picker data, fetched by the browser once instead of being inlined into
    # every page (it used to add ~7 MB of JSON to the request pages).
    path("ui/request-catalogue.json", views.ui_request_catalogue, name="ui-request-catalogue"),
    path("service-worker.js", views.service_worker, name="service-worker"),
    path("", views.home, name="home"),
    path("dashboard/", views.home, name="dashboard"),
    path("acknowledge-payment-notice/", views.acknowledge_payment_notice, name="acknowledge-payment-notice"),
    path("auth/", include("frontend.auth_urls")),
    path("auth/social/", include("frontend.social_urls")),
    path("account/", include("frontend.account_urls")),
    path("discover/", include("frontend.discovery_urls")),
    path("requests/", include("frontend.request_urls")),
    path("bookings/", include("frontend.booking_urls")),
    path("payments/", include("frontend.payment_urls")),
    path("reviews/", include("frontend.review_urls")),
    path("notifications/", include("frontend.notification_urls")),
    path("support/", include("frontend.support_urls")),
    path("system/", include("frontend.system_urls")),
    path("console/", include("frontend.console_urls")),
]
