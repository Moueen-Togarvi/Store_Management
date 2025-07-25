from django import forms
from .models import Product
from django.contrib.auth.forms import AuthenticationForm
from django.forms import ModelForm
from django.forms import inlineformset_factory
from .models import Sale, SaleItem
from .models import Return, SaleItem
from .models import Category



from .models import Supplier
from django import forms

class SupplierForm(forms.ModelForm):
    class Meta:
        model = Supplier
        fields = ['name', 'contact', 'producte']







class ProductForm(forms.ModelForm):
    class Meta:
        model = Product
        fields = '__all__'


class StockTransactionForm(forms.Form):
    sku = forms.CharField(label="Product SKU", max_length=50)
    quantity = forms.IntegerField()
    reason = forms.CharField(max_length=200)



class SaleItemForm(ModelForm):
    discount = forms.DecimalField(label='Discount', min_value=0, required=False, initial=0)
    class Meta:
        model = SaleItem
        fields = ['product', 'quantity', 'price_per_item', 'discount']

SaleItemFormSet = inlineformset_factory(
    Sale,
    SaleItem,
    form=SaleItemForm,
    extra=1,
    can_delete=True
)



class LoginForm(AuthenticationForm):
    username = forms.CharField(widget=forms.TextInput(attrs={
        'class': 'w-full p-2 border border-gray-300 rounded',
        'placeholder': 'Username'
    }))
    password = forms.CharField(widget=forms.PasswordInput(attrs={
        'class': 'w-full p-2 border border-gray-300 rounded',
        'placeholder': 'Password'
    }))



from django.contrib.auth.forms import UserCreationForm
from .models import CustomUser

class CustomUserCreationForm(UserCreationForm):
    class Meta:
        model = CustomUser
        fields = ('username', 'role', 'password1', 'password2')


class ReturnForm(forms.ModelForm):
    class Meta:
        model = Return
        fields = ['sale_item', 'quantity', 'amount', 'reason']
    sale_item = forms.ModelChoiceField(queryset=SaleItem.objects.none(), required=False, label='Sale Item (optional)')

    def __init__(self, *args, **kwargs):
        sale = kwargs.pop('sale', None)
        super().__init__(*args, **kwargs)
        if sale:
            self.fields['sale_item'].queryset = sale.items.all()
        else:
            self.fields['sale_item'].queryset = SaleItem.objects.all()


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ['name']
