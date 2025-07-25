from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.db import transaction
from django.utils import timezone
from django.db.models import Sum
from django.db.models.functions import TruncDay, TruncMonth, TruncWeek
from django.http import JsonResponse, HttpResponse
from django.template.loader import get_template
from django.contrib.auth import get_user_model
from xhtml2pdf import pisa
from django.contrib.auth.decorators import login_required, user_passes_test
from .models import Product, StockHistory, Sale, SaleItem, Supplier, CustomUser, Category
from .forms import ProductForm, StockTransactionForm, SaleItemFormSet, LoginForm, CategoryForm
from django.contrib.auth import authenticate, login, logout
from django.shortcuts import render, redirect
from .forms import LoginForm
from django.contrib.auth.forms import UserCreationForm
from django.views.decorators.csrf import csrf_exempt
from .forms import ReturnForm
from decimal import Decimal

# ✅ Role Checkers
def is_admin(user):
    return user.is_authenticated and user.role == 'admin'

def is_cashier(user):
    print("Checking user:", user, "role:", getattr(user, 'role', None))
    return user.is_authenticated and user.role == 'cashier'


# ✅ Product CRUD — Admin only
@login_required
@user_passes_test(lambda u: u.is_authenticated and (u.role == 'cashier' or u.role == 'admin'))
def product_list(request):
    suppliers = Supplier.objects.all()

    products = Product.objects.all()
    categories = Category.objects.all()
    return render(request, 'app1/product_list.html', {'products': products, 'categories': categories, 'suppliers': suppliers})

@login_required
@user_passes_test(lambda u: u.is_authenticated and (u.role == 'cashier' or u.role == 'admin'))
def product_create(request):
    form = ProductForm(request.POST or None)
    if form.is_valid():
        form.save()
        return redirect('product_list')
    return render(request, 'app1/product_form.html', {'form': form, 'title': 'Add Product'})

@login_required
@user_passes_test(lambda u: u.is_authenticated and (u.role == 'cashier' or u.role == 'admin'))
def product_update(request, pk):
    product = get_object_or_404(Product, pk=pk)
    form = ProductForm(request.POST or None, instance=product)
    if form.is_valid():
        form.save()
        return redirect('product_list')
    return render(request, 'app1/product_form.html', {'form': form, 'title': 'Edit Product'})

@login_required
@user_passes_test(lambda u: u.is_authenticated and (u.role == 'cashier' or u.role == 'admin'))
def product_delete(request, pk):
    product = get_object_or_404(Product, pk=pk)
    if request.method == 'POST':
        product.delete()
        return redirect('product_list')
    return render(request, 'app1/product_confirm_delete.html', {'product': product})


# ✅ Stock Transaction — Admin only
@login_required
@user_passes_test(lambda u: u.is_authenticated and (u.role == 'cashier' or u.role == 'admin'))
def stock_transaction_view(request):
    form = StockTransactionForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        sku = form.cleaned_data['sku']
        quantity = form.cleaned_data['quantity']
        reason = form.cleaned_data['reason']
        try:
            product = Product.objects.get(sku=sku)
        except Product.DoesNotExist:
            messages.error(request, "Product not found!")
            return redirect('stock_transaction')
        
        product.quantity += quantity
        product.save()

        StockHistory.objects.create(
            product=product,
            change=quantity,
            reason=reason,
            user=request.user
        )

        messages.success(request, f"{quantity} units {'added' if quantity > 0 else 'removed'} from {product.name}")
        return redirect('stock_transaction')

    return render(request, 'app1/stock_transaction.html', {'form': form})


@login_required
@user_passes_test(lambda u: u.is_authenticated and (u.role == 'cashier' or u.role == 'admin'))
@transaction.atomic
def create_sale(request):
    payment_choices = Sale.PAYMENT_METHOD_CHOICES
    if request.method == 'POST':
        formset = SaleItemFormSet(request.POST)
        payment_method = request.POST.get('payment_method', 'cash')
        # If cashier, force sale_discount to 0
        if request.user.role == 'cashier':
            sale_discount = 0
        else:
            sale_discount = request.POST.get('sale_discount', 0)
        if formset.is_valid():
            if not CustomUser.objects.filter(id=request.user.id).exists():
                messages.error(request, "Cashier user does not exist. Please log in again.")
                return redirect('login')
            sale = Sale.objects.create(
                total_amount=0,
                cashier=request.user,
                payment_method=payment_method,
                discount=sale_discount or 0
            )
            total = 0
            created_items = 0
            for form in formset:
                if not form.cleaned_data:
                    continue
                product = form.cleaned_data.get('product')
                quantity = form.cleaned_data.get('quantity')
                price = form.cleaned_data.get('price_per_item')
                # If cashier, force item_discount to 0
                if request.user.role == 'cashier':
                    item_discount = 0
                else:
                    item_discount = form.cleaned_data.get('discount') or 0
                if product and quantity and price:
                    try:
                        product = Product.objects.get(id=product.id)
                    except Product.DoesNotExist:
                        messages.error(request, "Product not found. Sale not completed.")
                        sale.delete()
                        return redirect('create_sale')
                    SaleItem.objects.create(
                        sale=sale,
                        product=product,
                        quantity=quantity,
                        price_per_item=price,
                        discount=item_discount
                    )
                    product.quantity -= quantity
                    product.save()
                    total += (price * quantity) - item_discount
                    created_items += 1
            if created_items == 0:
                sale.delete()
                messages.error(request, "No valid items in sale. Sale not completed.")
                return redirect('create_sale')
            total -= Decimal(sale_discount or 0)
            sale.total_amount = total
            sale.save()
            return render(request, 'app1/sale_success.html', {'sale': sale})
    else:
        formset = SaleItemFormSet()
    return render(request, 'app1/sale_create.html', {'formset': formset, 'payment_choices': payment_choices})

    
@csrf_exempt
@login_required
@user_passes_test(lambda u: u.is_authenticated and (u.role == 'cashier' or u.role == 'admin'))
def fast_checkout(request):
    payment_choices = Sale.PAYMENT_METHOD_CHOICES
    if 'cart' not in request.session:
        request.session['cart'] = []
    cart = request.session['cart']
    message = ''
    if request.method == 'POST':
        barcode = request.POST.get('barcode')
        payment_method = request.POST.get('payment_method', 'cash')
        # If cashier, force sale_discount to 0
        if request.user.role == 'cashier':
            sale_discount = 0.0
        else:
            sale_discount = float(request.POST.get('sale_discount', 0))
        if barcode:
            try:
                product = Product.objects.get(sku=barcode)
                found = False
                for item in cart:
                    if item['id'] == product.id:
                        item['quantity'] += 1
                        found = True
                        break
                if not found:
                    cart.append({'id': product.id, 'name': product.name, 'price': float(product.selling_price), 'quantity': 1, 'discount': 0})
                request.session['cart'] = cart
                message = f"Added {product.name}"
            except Product.DoesNotExist:
                message = "Product not found!"
        elif 'finalize' in request.POST:
            sale = Sale.objects.create(total_amount=0, cashier=request.user, payment_method=payment_method, discount=sale_discount)
            total = 0
            for item in cart:
                try:
                    product = Product.objects.get(id=item['id'])
                except Product.DoesNotExist:
                    messages.error(request, f"Product with ID {item['id']} not found. Sale not completed.")
                    sale.delete()
                    return redirect('fast_checkout')
                # If cashier, force item_discount to 0
                if request.user.role == 'cashier':
                    item_discount = 0
                else:
                    item_discount = item.get('discount', 0)
                SaleItem.objects.create(sale=sale, product=product, quantity=item['quantity'], price_per_item=product.selling_price, discount=item_discount)
                product.quantity -= item['quantity']
                product.save()
                total += (product.selling_price * item['quantity']) - float(item_discount)
            total -= Decimal(sale_discount)
            sale.total_amount = total
            sale.save()
            request.session['cart'] = []
            return render(request, 'app1/sale_success.html', {'sale': sale})
        elif 'clear' in request.POST:
            request.session['cart'] = []
            cart = []
    cart_details = []
    for item in cart:
        cart_details.append(item)
    total = sum((item['price'] * item['quantity']) - float(item.get('discount', 0)) for item in cart_details)
    # If cashier, do not subtract sale_discount
    if request.user.role == 'cashier':
        total -= 0
    else:
        total -= float(request.POST.get('sale_discount', 0)) if request.method == 'POST' else 0
    return render(request, 'app1/fast_checkout.html', {'cart': cart_details, 'total': total, 'message': message, 'payment_choices': payment_choices})

@login_required
@user_passes_test(lambda u: u.is_authenticated and (u.role == 'cashier' or u.role == 'admin'))
def sale_success(request):
    return render(request, 'app1/sale_success.html')


# ✅ Sales Listing — Admin + Cashier
@login_required
def sales_list(request):
    sales = Sale.objects.prefetch_related('items__product').order_by('-date')
    return render(request, 'app1/sales_list.html', {'sales': sales})


# ✅ Dashboard — Admin Only
@login_required
@user_passes_test(lambda u: u.is_authenticated and (u.role == 'admin' or u.role == 'cashier'))
def dashboard(request):
    total_products = Product.objects.count()
    low_stock_products = Product.objects.filter(quantity__lt=10)

    today = timezone.now().date()
    today_sales = Sale.objects.filter(date__date=today)
    total_sales_today = today_sales.aggregate(total=Sum('total_amount'))['total'] or 0
    recent_sales = Sale.objects.select_related('cashier').order_by('-date')[:5]
    from app1.models import SaleItem
    top_selling = (
        SaleItem.objects
        .values('product__name')
        .annotate(total_sold=Sum('quantity'))
        .order_by('-total_sold')[:5]
    )
    return render(request, 'app1/dashboard.html', {
        'total_products': total_products,
        'low_stock_products': low_stock_products,
        'total_sales_today': total_sales_today,
        'recent_sales': recent_sales,
        'top_selling': top_selling,
    })


# ✅ Stock History — Admin only
@login_required
@user_passes_test(lambda u: u.is_authenticated and (u.role == 'admin' or u.role == 'cashier'))
def stock_logs(request):
    logs = StockHistory.objects.select_related('product', 'user').order_by('-created_at')
    products = Product.objects.all()
    users = CustomUser.objects.all()
    # Filtering
    product_id = request.GET.get('product')
    user_id = request.GET.get('user')
    date = request.GET.get('date')
    if product_id:
        logs = logs.filter(product_id=product_id)
    if user_id:
        logs = logs.filter(user_id=user_id)
    if date:
        logs = logs.filter(created_at__date=date)
    return render(request, 'app1/stock_logs.html', {'logs': logs, 'products': products, 'users': users})


# ✅ Restock — Admin only
@login_required
@user_passes_test(lambda u: u.is_authenticated and (u.role == 'admin' or u.role == 'cashier'))
def restock_request(request):
    suppliers = Supplier.objects.prefetch_related('product_set')
    return render(request, 'app1/restock.html', {'suppliers': suppliers})


# ✅ Sales Report — Admin only
@login_required
@user_passes_test(is_admin)
def sales_report(request):
    daily = Sale.objects.annotate(day=TruncDay('date')).values('day').annotate(total=Sum('total_amount')).order_by('-day')
    monthly = Sale.objects.annotate(month=TruncMonth('date')).values('month').annotate(total=Sum('total_amount')).order_by('-month')
    sales = Sale.objects.all().order_by('-date')
    payment_totals = {
        'cash': Sale.objects.filter(payment_method='cash').aggregate(total=Sum('total_amount'))['total'],
        'card': Sale.objects.filter(payment_method='card').aggregate(total=Sum('total_amount'))['total'],
        'wallet': Sale.objects.filter(payment_method='wallet').aggregate(total=Sum('total_amount'))['total'],
    }
    # Calculate total refunded per sale
    from app1.models import Return, SaleItem
    refunds = {}
    for sale in sales:
        refunds[sale.id] = sum(r.amount for r in Return.objects.filter(sale=sale))
    # Profit/Loss by day
    profit_loss_day = []
    for d in SaleItem.objects.annotate(day=TruncDay('sale__date')).values('day').distinct().order_by('-day'):
        day = d['day']
        items = SaleItem.objects.filter(sale__date__date=day)
        revenue = sum(i.price_per_item * i.quantity for i in items)
        cost = sum((i.product.cost_price if i.product else 0) * i.quantity for i in items)
        profit = revenue - cost
        profit_loss_day.append({'period': day, 'revenue': revenue, 'cost': cost, 'profit': profit})
    # Profit/Loss by week
    profit_loss_week = []
    for w in SaleItem.objects.annotate(week=TruncWeek('sale__date')).values('week').distinct().order_by('-week'):
        week = w['week']
        items = SaleItem.objects.filter(sale__date__week=week.isocalendar()[1], sale__date__year=week.year)
        revenue = sum(i.price_per_item * i.quantity for i in items)
        cost = sum((i.product.cost_price if i.product else 0) * i.quantity for i in items)
        profit = revenue - cost
        profit_loss_week.append({'period': week, 'revenue': revenue, 'cost': cost, 'profit': profit})
    # Profit/Loss by month
    profit_loss_month = []
    for m in SaleItem.objects.annotate(month=TruncMonth('sale__date')).values('month').distinct().order_by('-month'):
        month = m['month']
        items = SaleItem.objects.filter(sale__date__month=month.month, sale__date__year=month.year)
        revenue = sum(i.price_per_item * i.quantity for i in items)
        cost = sum((i.product.cost_price if i.product else 0) * i.quantity for i in items)
        profit = revenue - cost
        profit_loss_month.append({'period': month, 'revenue': revenue, 'cost': cost, 'profit': profit})
    return render(request, 'app1/sales_report.html', {
        'daily': daily,
        'monthly': monthly,
        'sales': sales,
        'payment_totals': payment_totals,
        'refunds': refunds,
        'profit_loss_day': profit_loss_day,
        'profit_loss_week': profit_loss_week,
        'profit_loss_month': profit_loss_month,
    })


# ✅ Sale Invoice + PDF
@login_required
def sale_invoice(request, sale_id):
    sale = get_object_or_404(Sale, id=sale_id)
    sale_items = sale.items.select_related('product')
    total = sum(item.quantity * item.price_per_item - item.discount for item in sale_items) - sale.discount
    returns = sale.return_set.select_related('sale_item')
    return render(request, 'app1/invoice.html', {
        'sale': sale,
        'sale_items': sale_items,
        'total': total,
        'returns': returns,
    })


    
@login_required
def sale_invoice_pdf(request, sale_id):
    sale = get_object_or_404(Sale, id=sale_id)
    sale_items = sale.items.select_related('product')
    total = sum(item.quantity * item.price_per_item - item.discount for item in sale_items) - sale.discount
    returns = sale.return_set.select_related('sale_item')
    template_path = 'app1/invoice_pdf.html'
    context = {
        'sale': sale,
        'sale_items': sale_items,
        'total': total,
        'returns': returns,
    }
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'filename="invoice_{sale.id}.pdf"'
    template = get_template(template_path)
    html = template.render(context)
    pisa_status = pisa.CreatePDF(html, dest=response)
    if pisa_status.err:
        return HttpResponse('❌ Error generating PDF')
    return response

# ✅ Barcode Lookup APIs
def product_lookup(request):
    barcode = request.GET.get('barcode')
    try:
        product = Product.objects.get(sku=barcode)
        return JsonResponse({
            "success": True,
            "product": {
                "id": product.id,
                "name": product.name,
                "price": float(product.selling_price),
                "stock": product.quantity,
            }
        })
    except Product.DoesNotExist:
        return JsonResponse({"success": False})

def get_product_by_barcode(request):
    barcode = request.GET.get('barcode')
    try:
        product = Product.objects.get(barcode=barcode)
        return JsonResponse({
            'success': True,
            'name': product.name,
            'sku': product.sku,
            'price': product.selling_price,
            'quantity': product.quantity
        })
    except Product.DoesNotExist:
        return JsonResponse({'success': False})

def login_view(request): 
    if request.method == 'POST':
        form = LoginForm(request=request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            if hasattr(user, 'role'):
                if user.role == 'admin':
                    return redirect('dashboard')
                elif user.role == 'cashier':
                    return redirect('create_sale')
                else:
                    return redirect('dashboard')
            else:
                return redirect('dashboard')
    else:
        form = LoginForm()  # ✅ yeh block GET request ke liye hamesha chalega

    return render(request, 'app1/login.html', {'form': form})  # ✅ yahan pe 'form' hamesha defined hoga




def logout_view(request):
    logout(request)
    return redirect('login')




User = get_user_model()

def user_list(request):
    users = User.objects.all()
    return render(request, 'app1/user_list.html', {'users': users})




from .forms import CustomUserCreationForm


@login_required
@user_passes_test(is_admin)
def user_create(request):
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'User created successfully!')
        return redirect('user_list')
    else:
        form = CustomUserCreationForm()
    return render(request, 'app1/user_form.html', {'form': form})

@login_required
@user_passes_test(is_admin)
def user_edit(request, user_id):
    user = get_object_or_404(CustomUser, id=user_id)
    if request.method == 'POST':
        form = CustomUserCreationForm(request.POST, instance=user)
        if form.is_valid():
            form.save()
            messages.success(request, 'User updated successfully!')
            return redirect('user_list')
    else:
        form = CustomUserCreationForm(instance=user)
    return render(request, 'app1/user_form.html', {'form': form, 'edit': True, 'user_obj': user})

@login_required
@user_passes_test(is_admin)
def user_delete(request, user_id):
    user = get_object_or_404(CustomUser, id=user_id)
    if request.method == 'POST':
        user.delete()
        messages.success(request, 'User deleted successfully!')
        return redirect('user_list')
    return render(request, 'app1/user_confirm_delete.html', {'user_obj': user})


@login_required
@user_passes_test(lambda u: u.is_authenticated and (u.role == 'cashier' or u.role == 'admin'))
def return_view(request, sale_id):
    sale = get_object_or_404(Sale, id=sale_id)
    if request.method == 'POST':
        form = ReturnForm(request.POST, sale=sale)
        if form.is_valid():
            ret = form.save(commit=False)
            ret.sale = sale
            ret.save()
            # Update product stock
            if ret.sale_item and ret.quantity:
                product = ret.sale_item.product
                product.quantity += ret.quantity
                product.save()
            messages.success(request, 'Return processed successfully!')
            return redirect('sale_invoice', sale_id=sale.id)
    else:
        form = ReturnForm(sale=sale)
    return render(request, 'app1/return_form.html', {'form': form, 'sale': sale})


@login_required
@user_passes_test(lambda u: u.is_authenticated and (u.role == 'cashier' or u.role == 'admin'))
def category_create(request):
    if request.method == 'POST':
        form = CategoryForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Category added successfully!')
            return redirect('product_list')
    else:
        form = CategoryForm()
    return render(request, 'app1/category_form.html', {'form': form})

@login_required
@user_passes_test(lambda u: u.is_authenticated and (u.role == 'cashier' or u.role == 'admin'))
def category_edit(request, category_id):
    category = get_object_or_404(Category, id=category_id)
    if request.method == 'POST':
        form = CategoryForm(request.POST, instance=category)
        if form.is_valid():
            form.save()
            messages.success(request, 'Category updated successfully!')
            return redirect('product_list')
    else:
        form = CategoryForm(instance=category)
    return render(request, 'app1/category_form.html', {'form': form, 'edit': True, 'category_obj': category})

@login_required
@user_passes_test(lambda u: u.is_authenticated and (u.role == 'cashier' or u.role == 'admin'))
def category_delete(request, category_id):
    category = get_object_or_404(Category, id=category_id)
    if request.method == 'POST':
        category.delete()
        messages.success(request, 'Category deleted successfully!')
        return redirect('product_list')
    return render(request, 'app1/category_confirm_delete.html', {'category_obj': category})





from .models import Supplier
from .forms import SupplierForm
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import user_passes_test

def is_admin(user):
    return user.is_authenticated and user.role == 'admin'

@user_passes_test(lambda u: u.is_authenticated and (u.role == 'cashier' or u.role == 'admin'))
def supplier_list(request):
    suppliers = Supplier.objects.all()
    return render(request, 'app1/supplier_list.html', {'suppliers': suppliers})

@user_passes_test(lambda u: u.is_authenticated and (u.role == 'cashier' or u.role == 'admin'))
def supplier_create(request):
    if request.method == 'POST':
        form = SupplierForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('supplier_list')
    else:
        form = SupplierForm()
    return render(request, 'app1/supplier_form.html', {'form': form})

@user_passes_test(lambda u: u.is_authenticated and (u.role == 'cashier' or u.role == 'admin'))
def supplier_edit(request, pk):
    supplier = get_object_or_404(Supplier, pk=pk)
    if request.method == 'POST':
        form = SupplierForm(request.POST, instance=supplier)
        if form.is_valid():
            form.save()
            return redirect('supplier_list')
    else:
        form = SupplierForm(instance=supplier)
    return render(request, 'app1/supplier_form.html', {'form': form})

@user_passes_test(lambda u: u.is_authenticated and (u.role == 'cashier' or u.role == 'admin'))
def supplier_delete(request, pk):
    supplier = get_object_or_404(Supplier, pk=pk)
    if request.method == 'POST':
        supplier.delete()
        return redirect('supplier_list')
    return render(request, 'app1/supplier_confirm_delete.html', {'supplier': supplier})

@login_required
@user_passes_test(lambda u: u.is_authenticated and (u.role == 'admin' or u.role == 'cashier'))
def sale_receipt(request, sale_id):
    sale = get_object_or_404(Sale, id=sale_id)
    return render(request, 'app1/receipt.html', {'sale': sale, 'store_name': 'Store Name'})