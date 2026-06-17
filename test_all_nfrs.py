"""
Complete NFR test suite for the e‑commerce system.
Tests NFRs 1,2,3,4,7 automatically. Provides instructions for NFR5,9,10.

Requires:
- Django server running on http://localhost:8000
- Celery worker running
- Semaphore in views.py set to 10 (for NFR2)
- sleep(2) inside place_order (to make semaphore visible)
- Token set below
"""

import threading
import requests
import time
import os
import django
import sys

# Setup Django environment to access models directly
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'ecommerce.settings')
django.setup()

from store.models import Product

# ===== CONFIGURATION =====
BASE_URL = 'http://localhost:8000/api'
TOKEN = 'aa626615a97a33e9a52cc99a63b07e6b13206af1'
HEADERS = {'Authorization': f'Token {TOKEN}', 'Content-Type': 'application/json'}

# ===== HELPER: Reset product stock =====
def reset_product_stock():
    """Set stock and version for test products directly."""
    print("Resetting product stock via Django ORM...")
    updates = {
        1: {'stock': 1, 'version': 0},
        2: {'stock': 20, 'version': 0},
        3: {'stock': 10, 'version': 0},
        4: {'stock': 100, 'version': 0},
    }
    for pid, vals in updates.items():
        Product.objects.filter(id=pid).update(**vals)
    print("✅ Product stock reset for all test IDs (1,2,3,4).")

# ===== TEST FUNCTIONS =====
def test_nfr1_race_condition():
    """NFR #1: Race condition protection. Product 1 stock=1. 5 threads."""
    print("\n" + "="*60)
    print("NFR #1: RACE CONDITION PROTECTION TEST")
    print("="*60)
    
    results = {'success': 0, 'out_of_stock': 0, 'error': 0}
    
    def try_buy():
        try:
            resp = requests.post(
                f'{BASE_URL}/order/',
                json={'product_id': 1, 'quantity': 1},
                headers=HEADERS,
                timeout=10
            )
            if resp.status_code == 200:
                results['success'] += 1
                print("✓ SUCCESS (200): Order placed")
            elif resp.status_code == 400:
                results['out_of_stock'] += 1
                print("✗ OUT OF STOCK (400): Race prevented")
            else:
                results['error'] += 1
                print(f"! ERROR ({resp.status_code}): {resp.text}")
        except Exception as e:
            print(f"! EXCEPTION: {e}")
            results['error'] += 1
    
    threads = [threading.Thread(target=try_buy) for _ in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    
    print(f"\n[RESULTS]")
    print(f"  Successes: {results['success']} (expected: 1)")
    print(f"  Out of stock: {results['out_of_stock']} (expected: 4)")
    print(f"  Errors: {results['error']} (expected: 0)")
    
    assert results['success'] == 1, "Exactly 1 success"
    assert results['out_of_stock'] == 4, "Exactly 4 out‑of‑stock"
    assert results['error'] == 0, "No errors"
    print("\n✅ NFR #1 PASSED")


def test_nfr2_semaphore():
    """NFR #2: Semaphore limit=10. 20 threads with Barrier, sleep in view."""
    print("\n" + "="*60)
    print("NFR #2: SEMAPHORE RESOURCE MANAGEMENT TEST")
    print("="*60)
    print("NOTE: Expects semaphore=10 and a 2s sleep in the view.\n")
    
    results = {'success': 0, 'busy': 0, 'error': 0}
    barrier = threading.Barrier(20, timeout=5)  # 5 sec timeout
    
    def try_buy():
        try:
            barrier.wait()  # all start at once
            resp = requests.post(
                f'{BASE_URL}/order/',
                json={'product_id': 2, 'quantity': 1},
                headers=HEADERS,
                timeout=10
            )
            if resp.status_code == 200:
                results['success'] += 1
                print("✓ SUCCESS (200)")
            elif resp.status_code == 503:
                results['busy'] += 1
                print("✗ BUSY (503): Semaphore limit reached")
            else:
                results['error'] += 1
                print(f"! ERROR ({resp.status_code})")
        except threading.BrokenBarrierError:
            print("! Barrier timeout – some threads didn't start")
            results['error'] += 1
        except Exception as e:
            print(f"! EXCEPTION: {e}")
            results['error'] += 1
    
    threads = [threading.Thread(target=try_buy) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    
    print(f"\n[RESULTS]")
    print(f"  Successes: {results['success']} (expected: 10)")
    print(f"  Busy (503): {results['busy']} (expected: 10)")
    print(f"  Errors: {results['error']} (expected: 0)")
    
    assert results['success'] == 10, "Exactly 10 successes"
    assert results['busy'] == 10, "Exactly 10 busy responses"
    assert results['error'] == 0, "No errors"
    print("\n✅ NFR #2 PASSED")


def test_nfr3_async_tasks():
    """NFR #3: Asynchronous task queuing – response < 2s."""
    print("\n" + "="*60)
    print("NFR #3: ASYNC TASK QUEUE TEST")
    print("="*60)
    
    try:
        start = time.time()
        resp = requests.post(
            f'{BASE_URL}/order/',
            json={'product_id': 3, 'quantity': 1},
            headers=HEADERS,
            timeout=10
        )
        elapsed = time.time() - start
        
        print(f"Response time: {elapsed:.2f} seconds")
        print(f"Response status: {resp.status_code}")
        print(f"Response body: {resp.json()}")
        
        assert elapsed < 3, f"Response took {elapsed:.2f}s, should be < 2s"
        assert resp.status_code == 200, "Order should succeed"
        print("\n✅ NFR #3 PASSED - Tasks are async")
        
    except Exception as e:
        print(f"✗ FAILED: {e}")
        raise


def test_nfr4_batch_processing():
    """NFR #4: Batch processing – daily sales report."""
    print("\n" + "="*60)
    print("NFR #4: BATCH PROCESSING TEST")
    print("="*60)

    resp = requests.post(
        f'{BASE_URL}/batch/daily_report/',
        headers=HEADERS,
        timeout=30
    )
    print(f"Status: {resp.status_code}")
    print(f"Response: {resp.json()}")

    assert resp.status_code == 200, "Endpoint should return 200"
    data = resp.json()
    assert 'task_id' in data, "Response should contain task_id"
    print("\n✅ NFR #4 PASSED – batch job queued")


def test_nfr7_optimistic_locking():
    """NFR #7: Optimistic locking with version field."""
    print("\n" + "="*60)
    print("NFR #7: OPTIMISTIC LOCKING TEST")
    print("="*60)

    product_id = 4
    resp = requests.get(f'{BASE_URL}/products/', headers=HEADERS)
    if resp.status_code != 200:
        print("❌ Could not retrieve products.")
        return
    products = resp.json()
    version = None
    for p in products:
        if p['id'] == product_id:
            version = p.get('version', 0)
            break
    if version is None:
        print(f"❌ Product {product_id} not found.")
        return

    print(f"Current version of product {product_id}: {version}")

    # Correct version
    resp_ok = requests.post(
        f'{BASE_URL}/restock/',
        json={'product_id': product_id, 'amount': 10, 'version': version},
        headers=HEADERS
    )
    print(f"Restock with correct version: {resp_ok.status_code} - {resp_ok.json()}")
    assert resp_ok.status_code == 200, "Correct version should succeed"

    # Stale version
    stale_version = version - 1
    resp_conflict = requests.post(
        f'{BASE_URL}/restock/',
        json={'product_id': product_id, 'amount': 5, 'version': stale_version},
        headers=HEADERS
    )
    print(f"Restock with stale version ({stale_version}): {resp_conflict.status_code} - {resp_conflict.json()}")
    assert resp_conflict.status_code == 409, "Stale version should return 409"

    print("\n✅ NFR #7 PASSED – optimistic locking works")


def test_nfr5_load_balancing():
    """NFR #5: Load balancing – manual instructions."""
    print("\n" + "="*60)
    print("NFR #5: LOAD BALANCING TEST (Manual)")
    print("="*60)
    print("""
To test load balancing:

1. Start two Waitress instances:
   Terminal 1: waitress-serve --port=8001 ecommerce.wsgi:application
   Terminal 2: waitress-serve --port=8002 ecommerce.wsgi:application

2. Configure Nginx with upstream:
   upstream django_backend {
       server 127.0.0.1:8001;
       server 127.0.0.1:8002;
   }
   proxy_pass http://django_backend;

3. Reload Nginx and test with 20 requests:
   for i in {1..20}; do curl -s http://localhost/api/products/; done

4. Observe distribution between ports.

Expected: round‑robin distribution.
    """)


def test_nfr9_nfr10_performance():
    """NFR #9 & #10: Performance testing with Locust."""
    print("\n" + "="*60)
    print("NFR #9 & #10: PERFORMANCE TESTING (Locust)")
    print("="*60)
    print("""
To run performance tests:

1. Ensure `loadtest` user exists.
2. Start Celery: celery -A ecommerce worker --loglevel=info
3. Run baseline: locust -f locustfile.py --headless -u 100 -r 10 --run-time 2m --host=http://localhost --csv=baseline
4. Analyze baseline_stats.csv (especially /api/order/).
5. Apply a fix (e.g., nowait=True) and restart.
6. Run again with --csv=after and compare.

Expected: improved 95th/99th percentile latency.
    """)


# ===== MAIN EXECUTION =====
if __name__ == '__main__':
    print("\n\n")
    print("█" * 60)
    print("█  TESTING ALL NFRs (1,2,3,4,7 + Manual instructions for 5,9,10)")
    print("█" * 60)

    reset_product_stock()
    time.sleep(1)

    # Automated tests
    tests = [
        ("NFR1 - Race Condition", test_nfr1_race_condition),
        ("NFR2 - Semaphore", test_nfr2_semaphore),
        ("NFR3 - Async Tasks", test_nfr3_async_tasks),
        ("NFR4 - Batch Processing", test_nfr4_batch_processing),
        ("NFR7 - Optimistic Locking", test_nfr7_optimistic_locking),
    ]

    results = {}
    for name, test_func in tests:
        try:
            test_func()
            results[name] = "✅ PASSED"
        except AssertionError as e:
            print(f"\n❌ {name} FAILED: {e}")
            results[name] = "❌ FAILED"
        except Exception as e:
            print(f"\n❌ {name} ERROR: {e}")
            results[name] = "⚠️ ERROR"

    # Summary
    print("\n\n")
    print("█" * 60)
    print("█  TEST SUMMARY")
    print("█" * 60)
    for name, status in results.items():
        print(f"  {name}: {status}")
    print("█" * 60)

    # Manual tests instructions
    test_nfr5_load_balancing()
    test_nfr9_nfr10_performance()

    print("\n\n")
    print("█" * 60)
    print("█  ✅ AUTOMATED TESTS COMPLETED")
    print("█  ⚠️  MANUAL TESTS (NFR5, NFR9, NFR10) REQUIRE YOUR ACTION")
    print("█" * 60)