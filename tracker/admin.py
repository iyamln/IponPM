
from django.contrib import admin
from .models import Category, Transaction, Budget, SavingsGoal


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'category_type', 'user')
    search_fields = ('name', 'user__username')
    list_filter = ('category_type',)


@admin.register(Transaction)
class TransactionAdmin(admin.ModelAdmin):
    list_display = (
        'description',
        'transaction_type',
        'amount',
        'category',
        'transaction_date',
        'user',
    )
    search_fields = ('description', 'user__username')
    list_filter = ('transaction_type', 'payment_method')


@admin.register(Budget)
class BudgetAdmin(admin.ModelAdmin):
    list_display = ('category', 'month', 'amount', 'user')
    list_filter = ('month',)


@admin.register(SavingsGoal)
class SavingsGoalAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'target_amount',
        'current_amount',
        'status',
        'user',
    )
    list_filter = ('status',)
