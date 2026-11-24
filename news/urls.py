from django.urls import path, re_path

from . import views

app_name = "news"

urlpatterns = [
    path("", views.home, name="home"),
    re_path(r"^article/(?P<slug>[-\w]+)/$", views.article_detail, name="article_detail"),
    re_path(r"^category/(?P<slug>[-\w]+)/$", views.category_detail, name="category"),
    path("search/", views.search, name="search"),
    path("register/", views.register, name="register"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("dashboard/articles/new/", views.article_create, name="article_create"),
    path("dashboard/articles/preview/", views.article_preview, name="article_preview"),
    path("dashboard/articles/<int:pk>/edit/", views.article_edit, name="article_edit"),
    path("dashboard/articles/<int:pk>/delete/", views.article_delete, name="article_delete"),
    path("dashboard/comments/<int:pk>/", views.comment_moderate, name="comment_moderate"),
    path("dashboard/users/", views.user_management, name="user_management"),
    path("dashboard/users/<int:user_id>/role/", views.user_role_update, name="user_role_update"),
]
