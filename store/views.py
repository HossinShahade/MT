from django.db import transaction
from django.db.models import F
from django.http import JsonResponse
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated,IsAdminUser
from .models import Product, Order, OrderItem
from .tasks import generate_invoice, send_notification
import threading
from django.core.cache import cache
from .tasks import generate_invoice,send_notification,process_daily_sales_batch
import logging
import time

logger =logging.getLogger(__name__)

order_semaphore = threading.Semaphore(10)

@api_view(['POST'])
@permission_classes([IsAdminUser])
def restock_product(request):
    product_id = request.data.get('product_id')
    amount = request.data.get('amount',1)
    expected_version = request.data.get('version')
    
    
    if not product_id or expected_version is None:
        return JsonResponse({'error':'missing product or version'},status =400)
    
    with transaction.atomic():
        updated = Product.objects.filter(
            id = product_id,
            version = expected_version
        ) .update(
            stock =F('stock')+ amount,
            version =F('version') +1,
        )
        
        if updated ==0:
            return JsonResponse({
                'error' : 'stale version or product was modified'
            },status = 409)
        return JsonResponse({
            'success':True,
            'message' :f"added{amount} to stock , new version is {expected_version +1}"
        })
    


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def product_list(request):
    """Retrieve all products"""
    CACHE_KEY = 'all_products'
    data = cache.get(CACHE_KEY)
    if data is None:
        data = list(Product.objects.all().values('id', 'name', 'price', 'stock'))
        cache.set(CACHE_KEY,data,timeout=60)
        print("[CACHE] cache miss_loading from db")
    else:
        print("[CACHE] cahe hit _serived from edis")
        
    return JsonResponse(list(data), safe=False)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def place_order(request):
    """Place an order with race condition protection and semaphore"""
    product_id = request.data.get('product_id')
    quantity = request.data.get('quantity', 1)

    if not product_id or not quantity:
        return JsonResponse({'error': 'Missing product_id or quantity'}, status=400)

    # Resource management: semaphore limiting concurrent orders
    acquired = order_semaphore.acquire(blocking=False)
    
    if not acquired:
        return JsonResponse({'error': 'Server busy, try again'}, status=503)

    try:
        time.sleep(0.7)
        with transaction.atomic():
            # Row-level locking to prevent race condition
            product = Product.objects.select_for_update().get(id=product_id)

            if product.stock < quantity:
                return JsonResponse({'error': 'Out of stock'}, status=400)

            # Decrement stock
            product.stock -= quantity
            product.save()
            cache.delete('all_products')

            # Create order with total price
            order = Order.objects.create(
                user=request.user,
                status='completed',
                total_price=product.price * quantity
            )

            # Create order item
            OrderItem.objects.create(
                order=order,
                product=product,
                quantity=quantity,
                price=product.price
            )

        # Queue async tasks
        generate_invoice.delay(order.id)
        send_notification.delay(request.user.id, f"Your order {order.id} was placed!")

        return JsonResponse({
            'success': True,
            'order_id': order.id,
            'total_price': str(order.total_price)
        })

    except Product.DoesNotExist:
        return JsonResponse({'error': 'Product not found'}, status=404)
    except Exception as e:
        logger.exception("failed")
        return JsonResponse({'error': str(e)}, status=500)
    finally:
        order_semaphore.release()
        
@api_view(['POST'])
@permission_classes([IsAuthenticated])
def trigger_daily_batch(request):
    """Manually trigger the daily sales batch job"""
    task = process_daily_sales_batch.delay()
    return JsonResponse({
        'message': 'Batch job queued',
        'task_id': task.id
    })