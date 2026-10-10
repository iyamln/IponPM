from django import forms
from django.utils import timezone

from .models import (
    Budget,
    Category,
    Transaction,
    SavingsGoal,
    SavingsTransaction,
)


class TransactionForm(forms.ModelForm):
    class Meta:
        model = Transaction
        fields = [
            'transaction_type', 'amount', 'category', 'description',
            'transaction_date', 'payment_method', 'notes',
        ]
        widgets = {
            'transaction_date': forms.DateInput(
                attrs={'type': 'date'}, format='%Y-%m-%d'
            ),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields['category'].queryset = Category.objects.filter(
            user=user
        ).order_by('name')
        if not self.instance.pk:
            self.fields['transaction_date'].initial = timezone.localdate()
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'form-control'})
        for name in ('transaction_type', 'category', 'payment_method'):
            self.fields[name].widget.attrs['class'] = 'form-select'

    def clean(self):
        cleaned_data = super().clean()
        category = cleaned_data.get('category')
        transaction_type = cleaned_data.get('transaction_type')
        if category and category.user_id != self.user.id:
            self.add_error('category', 'Please select a category belonging to your account.')
        if category and transaction_type and category.category_type != transaction_type:
            self.add_error('category', 'Choose a category matching the transaction type.')
        return cleaned_data


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name', 'category_type', 'color']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'form-control'})
        self.fields['category_type'].widget.attrs['class'] = 'form-select'
        self.fields['color'].widget.attrs.update({
            'type': 'color', 'class': 'form-control form-control-color'
        })


class BudgetForm(forms.ModelForm):
    class Meta:
        model = Budget
        fields = ['category', 'amount', 'month', 'end_date']
        labels = {
            'category': 'Expense Category',
            'amount': 'Budget Amount (₱)',
            'month': 'Budget Start Date',
            'end_date': 'Budget End Date',
        }
        widgets = {
            'month': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
            'end_date': forms.DateInput(attrs={'type': 'date'}, format='%Y-%m-%d'),
        }

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        self.user = user
        self.fields['category'].queryset = Category.objects.filter(
            user=user, category_type='expense'
        ).order_by('name')
        self.fields['end_date'].required = True
        if not self.instance.pk:
            self.fields['month'].initial = timezone.localdate()
            self.fields['end_date'].initial = timezone.localdate()
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'form-control'})
        self.fields['category'].widget.attrs['class'] = 'form-select'

    def clean(self):
        cleaned_data = super().clean()
        category = cleaned_data.get('category')
        start_date = cleaned_data.get('month')
        end_date = cleaned_data.get('end_date')

        if category and category.user_id != self.user.id:
            self.add_error('category', 'Please select a category belonging to your account.')
        if category and category.category_type != 'expense':
            self.add_error('category', 'Budgets can only be assigned to expense categories.')
        if start_date and end_date and end_date < start_date:
            self.add_error('end_date', 'The end date must be on or after the start date.')
        return cleaned_data


class SavingsGoalForm(forms.ModelForm):
    class Meta:
        model = SavingsGoal
        fields = ['name', 'target_amount', 'current_amount', 'target_date', 'status']
        labels = {
            'name': 'Savings Goal Name',
            'target_amount': 'Target Amount (₱)',
            'current_amount': 'Current Savings (₱)',
            'target_date': 'Target Date',
            'status': 'Status',
        }
        widgets = {
            'target_date': forms.DateInput(attrs={'type': 'date'}),
            'current_amount': forms.NumberInput(attrs={'min': '0', 'step': '0.01'}),
            'target_amount': forms.NumberInput(attrs={'min': '0.01', 'step': '0.01'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'form-control'})

        self.fields['status'].widget.attrs['class'] = 'form-select'

    def clean(self):
        cleaned_data = super().clean()
        target = cleaned_data.get('target_amount')
        current = cleaned_data.get('current_amount')

        if target is not None and current is not None and current < 0:
            self.add_error('current_amount', 'Savings cannot be negative.')

        return cleaned_data


class SavingsTransactionForm(forms.ModelForm):
    class Meta:
        model = SavingsTransaction
        fields = ['amount', 'transaction_date', 'notes']
        labels = {
            'amount': 'Amount (₱)',
            'transaction_date': 'Transaction Date',
            'notes': 'Notes (Optional)',
        }
        widgets = {
            'amount': forms.NumberInput(attrs={
                'min': '0.01',
                'step': '0.01',
            }),
            'transaction_date': forms.DateInput(attrs={
                'type': 'date',
            }),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        if not self.instance.pk:
            self.fields['transaction_date'].initial = timezone.localdate()

        for field in self.fields.values():
            field.widget.attrs.update({'class': 'form-control'})


from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import get_user_model
from .models import Loan, LoanPayment


class RegistrationForm(UserCreationForm):
    class Meta:
        model = get_user_model()
        fields = ('username', 'email')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['email'].required = True
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'form-control'})


class LoanForm(forms.ModelForm):
    class Meta:
        model = Loan
        fields = ['provider', 'item_name', 'total_amount', 'purchase_date', 'due_date', 'installment_count', 'notes']
        labels = {'total_amount': 'Original Loan Amount (₱)', 'due_date': 'Next Due Date', 'installment_count': 'Number of Installments'}
        widgets = {
            'purchase_date': forms.DateInput(attrs={'type': 'date'}),
            'due_date': forms.DateInput(attrs={'type': 'date'}),
            'total_amount': forms.NumberInput(attrs={'min': '0.01', 'step': '0.01'}),
            'installment_count': forms.NumberInput(attrs={'min': '1', 'step': '1'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'form-control'})


class LoanPaymentForm(forms.ModelForm):
    class Meta:
        model = LoanPayment
        fields = ['amount', 'payment_date', 'notes']
        labels = {'amount': 'Payment Amount (₱)', 'payment_date': 'Payment Date'}
        widgets = {'amount': forms.NumberInput(attrs={'min': '0.01', 'step': '0.01'}), 'payment_date': forms.DateInput(attrs={'type': 'date'}), 'notes': forms.Textarea(attrs={'rows': 3})}
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.instance.pk:
            self.fields['payment_date'].initial = timezone.localdate()
        for field in self.fields.values():
            field.widget.attrs.update({'class': 'form-control'})
