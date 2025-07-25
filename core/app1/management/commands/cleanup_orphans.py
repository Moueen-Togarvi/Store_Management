from django.core.management.base import BaseCommand
from app1.models import SaleItem, Sale, Product, CustomUser, StockHistory

class Command(BaseCommand):
    help = 'Delete orphaned SaleItems, Sales, and StockHistory with missing Product, Sale, or User references.'

    def handle(self, *args, **options):
        # Clean orphaned SaleItems (missing Sale or Product)
        saleitem_count = 0
        for si in SaleItem.objects.all():
            if not Sale.objects.filter(id=si.sale_id).exists() or not Product.objects.filter(id=si.product_id).exists():
                self.stdout.write(f'Deleting orphaned SaleItem {si.id} (sale_id={si.sale_id}, product_id={si.product_id})')
                si.delete()
                saleitem_count += 1
        # Clean orphaned Sales (missing cashier)
        sale_count = 0
        for s in Sale.objects.all():
            if s.cashier_id and not CustomUser.objects.filter(id=s.cashier_id).exists():
                self.stdout.write(f'Deleting orphaned Sale {s.id} (cashier_id={s.cashier_id})')
                s.delete()
                sale_count += 1
        # Clean orphaned StockHistory (missing user or product)
        stockhistory_count = 0
        for sh in StockHistory.objects.all():
            if (sh.user_id and not CustomUser.objects.filter(id=sh.user_id).exists()) or \
               (sh.product_id and not Product.objects.filter(id=sh.product_id).exists()):
                self.stdout.write(f'Deleting orphaned StockHistory {sh.id} (user_id={sh.user_id}, product_id={sh.product_id})')
                sh.delete()
                stockhistory_count += 1
        self.stdout.write(self.style.SUCCESS(f'Deleted {saleitem_count} orphaned SaleItems, {sale_count} orphaned Sales, and {stockhistory_count} orphaned StockHistory records.')) 