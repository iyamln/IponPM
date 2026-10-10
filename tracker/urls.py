
from django.urls import path
from . import views

urlpatterns = [
    path('', views.dashboard, name='dashboard'),
    path('register/', views.register, name='register'),

    # Transactions
    path('transactions/', views.transaction_list, name='transaction_list'),
    path('transactions/add/', views.transaction_create, name='transaction_create'),
    path('transactions/<int:pk>/edit/', views.transaction_update, name='transaction_update'),
    path('transactions/<int:pk>/delete/', views.transaction_delete, name='transaction_delete'),

    # Categories
    path('categories/', views.category_list, name='category_list'),
    path('categories/add/', views.category_create, name='category_create'),
    path('categories/<int:pk>/edit/', views.category_update, name='category_update'),
    path('categories/<int:pk>/delete/', views.category_delete, name='category_delete'),

    # Budgets
    path('budgets/', views.budget_list, name='budget_list'),
    path('budgets/add/', views.budget_create, name='budget_create'),
    path('budgets/<int:pk>/edit/', views.budget_update, name='budget_update'),
    path('budgets/<int:pk>/delete/', views.budget_delete, name='budget_delete'),

        # Savings
    path('savings/', views.savings_list, name='savings_list'),
    path('savings/add/', views.savings_create, name='savings_create'),
    path('savings/<int:pk>/edit/', views.savings_update, name='savings_update'),
    path('savings/<int:pk>/delete/', views.savings_delete, name='savings_delete'),
    path('savings/<int:pk>/deposit/', views.savings_deposit, name='savings_deposit'),
    path('savings/<int:pk>/withdraw/', views.savings_withdraw, name='savings_withdraw'),
    path('savings/<int:pk>/history/', views.savings_history, name='savings_history'),

    # Loans and repayments
    path('loans/', views.loan_list, name='loan_list'),
    path('loans/add/', views.loan_create, name='loan_create'),
    path('loans/<int:pk>/edit/', views.loan_update, name='loan_update'),
    path('loans/<int:pk>/delete/', views.loan_delete, name='loan_delete'),
    path('loans/<int:pk>/pay/', views.loan_payment_create, name='loan_payment_create'),
    path('loans/<int:pk>/history/', views.loan_history, name='loan_history'),
]
