import django.core.validators
import django.utils.timezone
from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [('tracker', '0003_savingstransaction'), migrations.swappable_dependency(settings.AUTH_USER_MODEL)]
    operations = [
        migrations.CreateModel(name='Loan', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('provider', models.CharField(help_text='Example: TikTok PayLater', max_length=100)),
            ('item_name', models.CharField(max_length=200)),
            ('total_amount', models.DecimalField(decimal_places=2, max_digits=12, validators=[django.core.validators.MinValueValidator(0.01)])),
            ('purchase_date', models.DateField(default=django.utils.timezone.localdate)),
            ('due_date', models.DateField(blank=True, help_text='Next payment due date, if applicable', null=True)),
            ('installment_count', models.PositiveIntegerField(default=1, validators=[django.core.validators.MinValueValidator(1)])),
            ('notes', models.TextField(blank=True)),
            ('status', models.CharField(choices=[('active', 'Ongoing'), ('paid', 'Fully Paid'), ('paused', 'Paused')], default='active', max_length=10)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='loans', to=settings.AUTH_USER_MODEL)),
        ], options={'ordering': ['due_date', '-created_at']}),
        migrations.CreateModel(name='LoanPayment', fields=[
            ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
            ('amount', models.DecimalField(decimal_places=2, max_digits=12, validators=[django.core.validators.MinValueValidator(0.01)])),
            ('payment_date', models.DateField(default=django.utils.timezone.localdate)),
            ('notes', models.TextField(blank=True)),
            ('created_at', models.DateTimeField(auto_now_add=True)),
            ('loan', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='payments', to='tracker.loan')),
            ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='loan_payments', to=settings.AUTH_USER_MODEL)),
        ], options={'ordering': ['-payment_date', '-created_at']}),
    ]
