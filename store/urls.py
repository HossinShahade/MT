from django.urls import path
from . import views

urlpatterns = [
    path("products/", views.product_list, name="product_list"),
    path("order/", views.place_order, name="place_order"),
    path("batch/daily_report/",views.trigger_daily_batch,name="dailybatch"),
    path("restock/",views.restock_product,name="restock"),
]