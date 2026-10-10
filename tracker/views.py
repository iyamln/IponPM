import calendar
from datetime import date, timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db import IntegrityError
from django.db.models import Sum
from django.db.models.deletion import ProtectedError
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import BudgetForm, CategoryForm, TransactionForm
from .models import Budget, Category, Transaction

from django.db import transaction as db_transaction
from django.db.models import F

from .forms import SavingsGoalForm, SavingsTransactionForm, RegistrationForm, LoanForm, LoanPaymentForm
from .models import SavingsGoal, SavingsTransaction, Loan, LoanPayment

def last_day_of_month(year, month):
    return calendar.monthrange(year, month)[1]


def get_month_start(today, offset=0):
    month_index = today.year * 12 + today.month - 1 + offset
    return date(month_index // 12, month_index % 12 + 1, 1)


def get_month_total(user, month_start, transaction_type):
    month_end = date(
        month_start.year, month_start.month,
        last_day_of_month(month_start.year, month_start.month)
    )
    total = Transaction.objects.filter(
        user=user, transaction_type=transaction_type,
        transaction_date__range=(month_start, month_end)
    ).aggregate(total=Sum('amount'))['total']
    return total or Decimal('0.00')


def transaction_total(queryset, transaction_type):
    total = queryset.filter(transaction_type=transaction_type).aggregate(
        total=Sum('amount')
    )['total']
    return total or Decimal('0.00')


def get_budget_data(budget, user):
    # Existing budgets created before custom end dates are migrated safely.
    # For those older records, preserve the previous salary-period behavior.
    if budget.end_date is None:
        if budget.month.day == 15:
            period_end = date(
                budget.month.year, budget.month.month,
                last_day_of_month(budget.month.year, budget.month.month)
            ) - timedelta(days=1)
        else:
            if budget.month.month == 12:
                next_payday = date(budget.month.year + 1, 1, 15)
            else:
                next_payday = date(budget.month.year, budget.month.month + 1, 15)
            period_end = next_payday - timedelta(days=1)
    else:
        period_end = budget.end_date
    spent = Transaction.objects.filter(
        user=user, category=budget.category, transaction_type='expense',
        transaction_date__range=(budget.month, period_end)
    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    percent = float(spent / budget.amount * 100) if budget.amount else 0
    return {
        'budget': budget,
        'period_start': budget.month,
        'period_end': period_end,
        'spent': spent,
        'remaining': budget.amount - spent,
        'percent': min(percent, 100),
        'over_budget': spent > budget.amount,
        'over_amount': max(spent - budget.amount, Decimal('0.00')),
        'name': budget.category.name,
        'amount': budget.amount,
    }


@login_required
def dashboard(request):
    today = timezone.localdate()
    user = request.user
    month_start = date(today.year, today.month, 1)
    month_end = date(today.year, today.month, last_day_of_month(today.year, today.month))

    # All dashboard overview values and category spending use the calendar month.
    current_transactions = Transaction.objects.filter(
        user=user, transaction_date__range=(month_start, month_end)
    ).select_related('category')
    total_income = transaction_total(current_transactions, 'income')
    total_expenses = transaction_total(current_transactions, 'expense')

    expense_by_category = list(
        current_transactions.filter(transaction_type='expense')
        .values('category__name')
        .annotate(total=Sum('amount'))
        .order_by('-total')
    )
    category_labels = [item['category__name'] for item in expense_by_category]
    category_values = [float(item['total']) for item in expense_by_category]

    month_labels, income_values, expense_values = [], [], []
    for offset in range(-5, 1):
        month = get_month_start(today, offset)
        month_labels.append(month.strftime('%b %Y'))
        income_values.append(float(get_month_total(user, month, 'income')))
        expense_values.append(float(get_month_total(user, month, 'expense')))

    # Budget cards are calculated using each budget's own custom dates.
    budgets = Budget.objects.filter(
        user=user, category__category_type='expense'
    ).select_related('category')
    budget_data = []
    for budget in budgets:
        budget_data.append(get_budget_data(budget, user))

    insights = []
    if expense_by_category:
        top_category = expense_by_category[0]
        insights.append(
            f"Your highest spending category for {today.strftime('%B %Y')} "
            f"is {top_category['category__name']} (₱{top_category['total']:,.2f})."
        )
    else:
        insights.append(
            f"No expenses recorded for {today.strftime('%B %Y')} yet. "
            "Add a transaction to begin your analysis."
        )
    for item in budget_data:
        if item['over_budget']:
            insights.append(
                f"You have exceeded your {item['name']} budget "
                f"({item['period_start']:%b %d}–{item['period_end']:%b %d})."
            )

    context = {
        'total_income': total_income,
        'total_expenses': total_expenses,
        'net_total': total_income - total_expenses,
        'current_month': f"{month_start.strftime('%b %d, %Y')} – {month_end.strftime('%b %d, %Y')}",
        'month_start': month_start,
        'month_end': month_end,
        'recent_transactions': Transaction.objects.filter(
            user=user
        ).select_related('category')[:5],
        'category_labels': category_labels,
        'category_values': category_values,
        'month_labels': month_labels,
        'income_values': income_values,
        'expense_values': expense_values,
        'budget_data': budget_data,
        'insights': insights,
    }
    return render(request, 'tracker/dashboard.html', context)


@login_required
def transaction_list(request):
    transactions = Transaction.objects.filter(user=request.user).select_related('category')
    search = request.GET.get('q', '').strip()
    transaction_type = request.GET.get('type', '')
    category_id = request.GET.get('category', '')
    payment_method = request.GET.get('payment_method', '')
    if search:
        transactions = transactions.filter(description__icontains=search)
    if transaction_type in ('income', 'expense'):
        transactions = transactions.filter(transaction_type=transaction_type)
    if category_id.isdigit():
        transactions = transactions.filter(category_id=int(category_id), category__user=request.user)
    valid_payment_methods = {choice[0] for choice in Transaction.PAYMENT_CHOICES}
    if payment_method in valid_payment_methods:
        transactions = transactions.filter(payment_method=payment_method)
    page_obj = Paginator(transactions, 10).get_page(request.GET.get('page'))
    context = {
        'page_obj': page_obj,
        'categories': Category.objects.filter(user=request.user),
        'payment_choices': Transaction.PAYMENT_CHOICES,
        'search': search,
        'selected_type': transaction_type,
        'selected_category': category_id,
        'selected_payment_method': payment_method,
    }
    return render(request, 'tracker/transaction_list.html', context)


@login_required
def transaction_create(request):
    form = TransactionForm(request.POST or None, user=request.user)
    if request.method == 'POST' and form.is_valid():
        transaction = form.save(commit=False)
        transaction.user = request.user
        transaction.save()
        messages.success(request, 'Transaction added successfully.')
        return redirect('transaction_list')
    return render(request, 'tracker/transaction_form.html', {
        'form': form, 'page_title': 'Add Transaction'
    })


@login_required
def transaction_update(request, pk):
    transaction = get_object_or_404(Transaction, pk=pk, user=request.user)
    form = TransactionForm(request.POST or None, instance=transaction, user=request.user)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Transaction updated successfully.')
        return redirect('transaction_list')
    return render(request, 'tracker/transaction_form.html', {
        'form': form, 'page_title': 'Edit Transaction'
    })


@login_required
def transaction_delete(request, pk):
    transaction = get_object_or_404(Transaction, pk=pk, user=request.user)
    if request.method == 'POST':
        transaction.delete()
        messages.success(request, 'Transaction deleted successfully.')
        return redirect('transaction_list')
    return render(request, 'tracker/transaction_confirm_delete.html', {'transaction': transaction})


@login_required
def category_list(request):
    categories = Category.objects.filter(user=request.user).order_by('category_type', 'name')
    return render(request, 'tracker/category_list.html', {'categories': categories})


@login_required
def category_create(request):
    form = CategoryForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        category = form.save(commit=False)
        category.user = request.user
        try:
            category.save()
            messages.success(request, 'Category created successfully.')
            return redirect('category_list')
        except IntegrityError:
            form.add_error('name', 'A category with this name and type already exists.')
    return render(request, 'tracker/category_form.html', {'form': form, 'title': 'Add Category'})


@login_required
def category_update(request, pk):
    category = get_object_or_404(Category, pk=pk, user=request.user)
    form = CategoryForm(request.POST or None, instance=category)
    if request.method == 'POST' and form.is_valid():
        try:
            form.save()
            messages.success(request, 'Category updated successfully.')
            return redirect('category_list')
        except IntegrityError:
            form.add_error('name', 'A category with this name and type already exists.')
    return render(request, 'tracker/category_form.html', {'form': form, 'title': 'Edit Category'})


@login_required
def category_delete(request, pk):
    category = get_object_or_404(Category, pk=pk, user=request.user)
    if request.method == 'POST':
        try:
            category.delete()
            messages.success(request, 'Category deleted successfully.')
        except ProtectedError:
            messages.error(request, 'This category cannot be deleted because it is used by a transaction or budget.')
        return redirect('category_list')
    return render(request, 'tracker/category_confirm_delete.html', {'category': category})


@login_required
def budget_list(request):
    budgets = Budget.objects.filter(user=request.user).select_related('category')
    budget_data = [get_budget_data(budget, request.user) for budget in budgets]
    return render(request, 'tracker/budget_list.html', {'budget_data': budget_data})


@login_required
def budget_create(request):
    form = BudgetForm(request.POST or None, user=request.user)
    if request.method == 'POST' and form.is_valid():
        budget = form.save(commit=False)
        budget.user = request.user
        duplicate = Budget.objects.filter(
            user=request.user, category=budget.category,
            month=budget.month, end_date=budget.end_date
        ).exists()
        if duplicate:
            form.add_error('category', 'A budget already exists for this category and exact date period.')
        else:
            budget.save()
            messages.success(request, 'Budget created successfully.')
            return redirect('budget_list')
    return render(request, 'tracker/budget_form.html', {'form': form, 'title': 'Create Budget'})


@login_required
def budget_update(request, pk):
    budget = get_object_or_404(Budget, pk=pk, user=request.user)
    form = BudgetForm(request.POST or None, instance=budget, user=request.user)
    if request.method == 'POST' and form.is_valid():
        updated_budget = form.save(commit=False)
        duplicate = Budget.objects.filter(
            user=request.user, category=updated_budget.category,
            month=updated_budget.month, end_date=updated_budget.end_date
        ).exclude(pk=budget.pk).exists()
        if duplicate:
            form.add_error('category', 'A budget already exists for this category and exact date period.')
        else:
            updated_budget.user = request.user
            updated_budget.save()
            messages.success(request, 'Budget updated successfully.')
            return redirect('budget_list')
    return render(request, 'tracker/budget_form.html', {'form': form, 'title': 'Edit Budget'})


@login_required
def budget_delete(request, pk):
    budget = get_object_or_404(Budget, pk=pk, user=request.user)
    if request.method == 'POST':
        try:
            budget.delete()
            messages.success(request, 'Budget deleted successfully.')
        except ProtectedError:
            messages.error(request, 'This budget cannot be deleted because another record uses it.')
        return redirect('budget_list')
    return render(request, 'tracker/budget_confirm_delete.html', {'budget': budget})


@login_required
def savings_list(request):
    goals = SavingsGoal.objects.filter(user=request.user).order_by('-created_at')

    for goal in goals:
        goal.progress = min(
            float(goal.current_amount / goal.target_amount * 100), 100
        ) if goal.target_amount else 0
        goal.remaining = max(
            goal.target_amount - goal.current_amount, Decimal('0.00')
        )

    return render(request, 'tracker/savings_list.html', {
        'goals': goals,
    })


@login_required
def savings_create(request):
    form = SavingsGoalForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        goal = form.save(commit=False)
        goal.user = request.user
        goal.save()
        messages.success(request, 'Savings goal created successfully.')
        return redirect('savings_list')

    return render(request, 'tracker/savings_form.html', {
        'form': form,
        'title': 'Create Savings Goal',
    })


@login_required
def savings_update(request, pk):
    goal = get_object_or_404(SavingsGoal, pk=pk, user=request.user)
    form = SavingsGoalForm(request.POST or None, instance=goal)

    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Savings goal updated successfully.')
        return redirect('savings_list')

    return render(request, 'tracker/savings_form.html', {
        'form': form,
        'title': 'Edit Savings Goal',
    })


@login_required
def savings_delete(request, pk):
    goal = get_object_or_404(SavingsGoal, pk=pk, user=request.user)

    if request.method == 'POST':
        goal.delete()
        messages.success(request, 'Savings goal deleted successfully.')
        return redirect('savings_list')

    return render(request, 'tracker/savings_confirm_delete.html', {
        'goal': goal,
    })


@login_required
def savings_deposit(request, pk):
    goal = get_object_or_404(SavingsGoal, pk=pk, user=request.user)
    form = SavingsTransactionForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        amount = form.cleaned_data['amount']

        with db_transaction.atomic():
            locked_goal = SavingsGoal.objects.select_for_update().get(
                pk=goal.pk, user=request.user
            )

            locked_goal.current_amount = F('current_amount') + amount
            locked_goal.save(update_fields=['current_amount'])
            locked_goal.refresh_from_db()

            if locked_goal.current_amount >= locked_goal.target_amount:
                locked_goal.status = 'completed'
                locked_goal.save(update_fields=['status'])
            elif locked_goal.status == 'completed':
                locked_goal.status = 'active'
                locked_goal.save(update_fields=['status'])

            activity = form.save(commit=False)
            activity.user = request.user
            activity.goal = locked_goal
            activity.transaction_type = 'deposit'
            activity.save()

        messages.success(request, 'Deposit recorded successfully.')
        return redirect('savings_history', pk=goal.pk)

    return render(request, 'tracker/savings_transaction_form.html', {
        'form': form,
        'goal': goal,
        'title': 'Add Savings',
        'action_label': 'Deposit',
    })


@login_required
def savings_withdraw(request, pk):
    goal = get_object_or_404(SavingsGoal, pk=pk, user=request.user)
    form = SavingsTransactionForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        amount = form.cleaned_data['amount']

        with db_transaction.atomic():
            locked_goal = SavingsGoal.objects.select_for_update().get(
                pk=goal.pk, user=request.user
            )
            locked_goal.refresh_from_db()

            if amount > locked_goal.current_amount:
                form.add_error(
                    'amount',
                    f'You only have ₱{locked_goal.current_amount:,.2f} available.'
                )
            else:
                locked_goal.current_amount = F('current_amount') - amount
                locked_goal.save(update_fields=['current_amount'])
                locked_goal.refresh_from_db()

                if locked_goal.current_amount < locked_goal.target_amount:
                    if locked_goal.status == 'completed':
                        locked_goal.status = 'active'
                        locked_goal.save(update_fields=['status'])

                activity = form.save(commit=False)
                activity.user = request.user
                activity.goal = locked_goal
                activity.transaction_type = 'withdrawal'
                activity.save()

                messages.success(request, 'Withdrawal recorded successfully.')
                return redirect('savings_history', pk=goal.pk)

    return render(request, 'tracker/savings_transaction_form.html', {
        'form': form,
        'goal': goal,
        'title': 'Withdraw Savings',
        'action_label': 'Withdraw',
    })


@login_required
def savings_history(request, pk):
    goal = get_object_or_404(SavingsGoal, pk=pk, user=request.user)
    activities = SavingsTransaction.objects.filter(
        goal=goal,
        user=request.user,
    ).order_by('-transaction_date', '-created_at')

    return render(request, 'tracker/savings_history.html', {
        'goal': goal,
        'activities': activities,
    })


from django.contrib.auth import login
from django.db.models import Sum as AggregateSum


def register(request):
    if request.user.is_authenticated:
        return redirect('dashboard')
    form = RegistrationForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, 'Your IponPM account has been created.')
        return redirect('dashboard')
    return render(request, 'registration/register.html', {'form': form})


@login_required
def loan_list(request):
    loans = list(Loan.objects.filter(user=request.user).prefetch_related('payments'))
    for loan in loans:
        loan.total_paid = loan.payments.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
        loan.remaining_balance = max(loan.total_amount - loan.total_paid, Decimal('0.00'))
        loan.progress = min(float(loan.total_paid / loan.total_amount * 100), 100) if loan.total_amount else 0
    total_outstanding = sum((loan.remaining_balance for loan in loans), Decimal('0.00'))
    return render(request, 'tracker/loan_list.html', {'loans': loans, 'total_outstanding': total_outstanding})


@login_required
def loan_create(request):
    form = LoanForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        loan = form.save(commit=False)
        loan.user = request.user
        loan.save()
        messages.success(request, 'Loan added successfully.')
        return redirect('loan_list')
    return render(request, 'tracker/loan_form.html', {'form': form, 'title': 'Add Loan'})


@login_required
def loan_update(request, pk):
    loan = get_object_or_404(Loan, pk=pk, user=request.user)
    form = LoanForm(request.POST or None, instance=loan)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Loan updated successfully.')
        return redirect('loan_list')
    return render(request, 'tracker/loan_form.html', {'form': form, 'title': 'Edit Loan'})


@login_required
def loan_delete(request, pk):
    loan = get_object_or_404(Loan, pk=pk, user=request.user)
    if request.method == 'POST':
        loan.delete()
        messages.success(request, 'Loan and its payment history deleted.')
        return redirect('loan_list')
    return render(request, 'tracker/loan_confirm_delete.html', {'loan': loan})


@login_required
def loan_payment_create(request, pk):
    loan = get_object_or_404(Loan, pk=pk, user=request.user)
    form = LoanPaymentForm(request.POST or None)
    already_paid = loan.payments.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    loan.total_paid = already_paid
    loan.remaining_balance = max(loan.total_amount - already_paid, Decimal('0.00'))
    if request.method == 'POST' and form.is_valid():
        amount = form.cleaned_data['amount']
        if amount > loan.remaining_balance:
            form.add_error('amount', f'Payment cannot exceed the remaining balance of ₱{loan.remaining_balance:,.2f}.')
        else:
            payment = form.save(commit=False)
            payment.user = request.user
            payment.loan = loan
            payment.save()
            loan.refresh_status()
            messages.success(request, 'Loan payment recorded.')
            return redirect('loan_history', pk=loan.pk)
    return render(request, 'tracker/loan_payment_form.html', {'form': form, 'loan': loan})


@login_required
def loan_history(request, pk):
    loan = get_object_or_404(Loan, pk=pk, user=request.user)
    payments = LoanPayment.objects.filter(loan=loan, user=request.user)
    total_paid = payments.aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
    return render(request, 'tracker/loan_history.html', {
        'loan': loan, 'payments': payments, 'total_paid': total_paid,
        'remaining_balance': max(loan.total_amount - total_paid, Decimal('0.00')),
    })
