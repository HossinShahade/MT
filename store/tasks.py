import time
from celery import shared_task
from django.utils import timezone
from.models import Order

@shared_task
def generate_invoice(order_id):
    time.sleep(2)
    print(f"[CELERY] Invoice generated for order {order_id}")
    return f"Invoice done for {order_id}"

@shared_task
def send_notification(user_id, message):
    time.sleep(1)
    print(f"[CELERY] Notification sent to user {user_id}: {message}")
    return "Notification sent"


@shared_task
def process_daily_sales_batch():
    today = timezone.now().date()
    
    
    orders = list(
        Order.objects.filter(
            status ='completed',
            created_at__date= today,
        ).values('id','total_price','user_id')
    )
    total_orders = len(orders)
    chunk_size = 100
    
    report = []
    print("[BATCh]starting daily sales report for{today} . total order: {total_orders}")
    
    for i in range (0,total_orders,chunk_size):
        chunk = orders[i:i+ chunk_size]
        chunk_revenue = sum(float(o['total_price']) for o in chunk)
        chunk_num = i // chunk_size +1
        report.append({
            'chunk':chunk_num,
            'orders_count':len(chunk),
            'revenue': round(chunk_revenue,2)
        })
        
        
        print(f"[BATCH] Chunk {chunk_num}: {len(chunk)} orders, revenue = {chunk_revenue:.2f}")
        time.sleep(0.1)  # simulate processing time per chunk

    print(f"[BATCH] Complete. {total_orders} orders across {len(report)} chunks.")
    return {
        'date': str(today),
        'total_orders': total_orders,
        'chunks_processed': len(report),
        'chunks': report,
    }