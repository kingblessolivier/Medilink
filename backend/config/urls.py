from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

api_v1 = [
    path("", include("apps.facilities.urls")),
    path("", include("apps.insurance.urls")),
    path("", include("apps.queueing.urls")),
    path("", include("apps.staff.urls")),
    # Staff sign-in. Patient OTP auth arrives in Phase 2.
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
