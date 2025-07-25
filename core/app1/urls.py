from django.urls import path
from . import views
from django.contrib.auth.views import LogoutView

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('products/', views.product_list, name='product_list'),
    path('products/create/', views.product_create, name='product_create'),
    path('products/edit/<int:pk>/', views.product_update, name='product_edit'),
    path('products/delete/<int:pk>/', views.product_delete, name='product_delete'),
    path('stock/', views.stock_transaction_view, name='stock_transaction'),
    path('sales/new/', views.create_sale, name='create_sale'),
    path('sales/success/', views.sale_success, name='sale_success'),
    path('stock/logs/', views.stock_logs, name='stock_logs'),
    path('restock/', views.restock_request, name='restock'),
    path('api/product-lookup/', views.product_lookup, name='product_lookup'),
    path('api/get-product-by-barcode/', views.get_product_by_barcode, name='get_product_by_barcode'),
    path('sales/', views.sales_list, name='sales_list'),
    path('sales/report/', views.sales_report, name='sales_report'),
    path('sale/invoice/<int:sale_id>/', views.sale_invoice, name='sale_invoice'),
    path('sale/invoice/<int:sale_id>/pdf/', views.sale_invoice_pdf, name='sale_invoice_pdf'),
    path('sale/<int:sale_id>/return/', views.return_view, name='sale_return'),
    path('sale/receipt/<int:sale_id>/', views.sale_receipt, name='sale_receipt'),
    path('users/', views.user_list, name='user_list'),
    path('users/add/', views.user_create, name='user_create'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('users/edit/<int:user_id>/', views.user_edit, name='user_edit'),
    path('users/delete/<int:user_id>/', views.user_delete, name='user_delete'),
    path('fast-checkout/', views.fast_checkout, name='fast_checkout'),
    path('categories/add/', views.category_create, name='category_create'),
    path('categories/edit/<int:category_id>/', views.category_edit, name='category_edit'),
    path('categories/delete/<int:category_id>/', views.category_delete, name='category_delete'),
    path('suppliers/', views.supplier_list, name='supplier_list'),
    path('suppliers/add/', views.supplier_create, name='supplier_create'),
    path('suppliers/<int:pk>/edit/', views.supplier_edit, name='supplier_edit'),
    path('suppliers/<int:pk>/delete/', views.supplier_delete, name='supplier_delete'),


]


