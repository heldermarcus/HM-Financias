import os
import django
import sys

# Setup Django
sys.path.append(os.getcwd())
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.contrib.auth import get_user_model
from abacatepay import AbacatePay
from abacatepay.products import Product
from abacatepay.customers import CustomerMetadata
import re

User = get_user_model()

def debug_checkout():
    api_key = os.environ.get('ABACATEPAY_API_KEY')
    if not api_key:
        print("ERROR: ABACATEPAY_API_KEY not found in environment.")
        return

    print(f"Using API Key: {api_key[:10]}...")
    abacate = AbacatePay(api_key)
    
    # Simulate user
    user = User.objects.first()
    if not user:
        print("ERROR: No user found in DB.")
        return

    print(f"User: {user.email}")
    
    customer_name = user.get_full_name() or user.username or user.email.split('@')[0]
    customer_email = user.email
    customer_phone = getattr(user, 'phone', '') or '71999999999'
    raw_cpf = getattr(user, 'cpf', '') or '07343375580'
    customer_taxid = re.sub(r'\D', '', raw_cpf)

    customer_data = CustomerMetadata(
        name=customer_name,
        email=customer_email,
        cellphone=customer_phone,
        tax_id=customer_taxid,
    )

    try:
        # Step 1: Create customer
        print("Creating/Getting customer...")
        created_customer = abacate.customers.create(customer_data)
        customer_id = created_customer.id
        print(f"Customer ID: {customer_id}")

        # Step 2: Create Billing
        product = Product(
            external_id=f"test-{int(re.sub(r'\D', '', str(os.urandom(4))))}",
            name="Assinatura Mensal HMF",
            description="Acesso completo ao HM de Finanças",
            quantity=1,
            price=4990
        )

        # URLs logic from updated views.py
        host = "localhost:8000"
        print(f"Original Host: {host}")
        
        # LOGICA APLICADA EM VIEWS.PY
        host = host.split(':')[0]
        if 'localhost' in host:
            host = host.replace('localhost', '127.0.0.1')
        if '.nip.io' not in host:
            host += '.nip.io'
                
        base_url = f"http://{host}"
        return_url = base_url + "/payment-failed/"
        completion_url = base_url + "/payment-success/"
        
        print(f"Final Host: {host}")
        print(f"URLs: Return={return_url}, Completion={completion_url}")

        print("Creating billing...")
        billing = abacate.billing.create(
            frequency="ONE_TIME",
            methods=["PIX"],
            products=[product],
            customer_id=customer_id,
            return_url=return_url,
            completion_url=completion_url,
        )
        print(f"Billing SUCCESS: {billing.url}")

    except Exception as e:
        print(f"EXCEPTION TYPE: {type(e).__name__}")
        print(f"EXCEPTION MESSAGE: {str(e)}")
        if hasattr(e, 'response'):
            print(f"RESPONSE STATUS: {e.response.status_code}")
            print(f"RESPONSE BODY: {e.response.text}")

if __name__ == "__main__":
    debug_checkout()
