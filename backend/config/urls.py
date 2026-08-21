from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

api_v1 = [
    path("", include("apps.facilities.urls")),
    path("", include("apps.insurance.urls")),
    path("", include("apps.queueing.urls")),
    path("", include("apps.staff.urls")),
    path("", include("apps.patients.urls")),
    path("", include("apps.scheduling.urls")),
    path("", include("apps.gateway.urls")),
    path("", include("apps.triage.urls")),
    path("", include("apps.providers.urls")),
    path("", include("apps.search.urls")),
    path("", include("apps.notifications.urls")),
    # Staff sign-in. Patients use the OTP endpoints in apps.patients.urls.
    path("auth/token", TokenObtainPairView.as_view(), name="token-obtain"),
    path("auth/token/refresh", TokenRefreshView.as_view(), name="token-refresh"),
]

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/", include((api_v1, "v1"))),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path(
        "api/docs/",
        SpectacularSwaggerView.as_view(url_name="schema"),
        name="swagger-ui",
    ),
]

admin.site.site_header = "MediLink Rwanda"
admin.site.site_title = "MediLink Rwanda"
admin.site.index_title = "Facility directory administration"
