import requests
import sys
import uuid
import time
from datetime import datetime

class KiaKartAPITester:
    def __init__(self, base_url):
        self.base_url = base_url
        self.token = None
        self.vendor_id = None
        self.tests_run = 0
        self.tests_passed = 0
        self.product_ids = []

    def run_test(self, name, method, endpoint, expected_status, data=None, files=None, form_data=False):
        """Run a single API test"""
        url = f"{self.base_url}/{endpoint}"
        headers = {}
        
        if self.token and not files:
            headers['Authorization'] = f'Bearer {self.token}'
        
        if data and not form_data and not files:
            headers['Content-Type'] = 'application/json'

        self.tests_run += 1
        print(f"\n🔍 Testing {name}...")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=headers)
            elif method == 'POST':
                if files:
                    if data:
                        response = requests.post(url, data=data, files=files, headers=headers)
                    else:
                        response = requests.post(url, files=files, headers=headers)
                else:
                    if form_data:
                        response = requests.post(url, data=data, headers=headers)
                    else:
                        response = requests.post(url, json=data, headers=headers)
            elif method == 'PUT':
                if files:
                    response = requests.put(url, data=data, files=files, headers=headers)
                else:
                    if form_data:
                        response = requests.put(url, data=data, headers=headers)
                    else:
                        response = requests.put(url, json=data, headers=headers)
            elif method == 'DELETE':
                response = requests.delete(url, headers=headers)

            success = response.status_code == expected_status
            if success:
                self.tests_passed += 1
                print(f"✅ Passed - Status: {response.status_code}")
                try:
                    return success, response.json()
                except:
                    return success, {}
            else:
                print(f"❌ Failed - Expected {expected_status}, got {response.status_code}")
                try:
                    error_detail = response.json().get('detail', 'No detail provided')
                    print(f"Error: {error_detail}")
                except:
                    print("Could not parse error response")
                return False, {}

        except Exception as e:
            print(f"❌ Failed - Error: {str(e)}")
            return False, {}

    def test_health_check(self):
        """Test the health check endpoint"""
        success, response = self.run_test(
            "Health Check",
            "GET",
            "api/health",
            200
        )
        if success:
            print(f"Health check response: {response}")
        return success

    def test_register_vendor(self):
        """Test vendor registration"""
        # Generate unique email to avoid conflicts
        timestamp = int(time.time())
        email = f"vendor_{timestamp}@test.com"
        
        data = {
            "email": email,
            "password": "Test123!",
            "name": "Test Vendor",
            "business_name": "Test Business",
            "phone": "+1234567890"
        }
        
        success, response = self.run_test(
            "Register Vendor",
            "POST",
            "api/auth/register",
            200,
            data=data
        )
        
        if success and 'access_token' in response:
            self.token = response['access_token']
            self.vendor_id = response['vendor']['id']
            print(f"Registered vendor with ID: {self.vendor_id}")
            return True
        return False

    def test_login_vendor(self, email, password):
        """Test vendor login"""
        data = {
            "email": email,
            "password": password
        }
        
        success, response = self.run_test(
            "Login Vendor",
            "POST",
            "api/auth/login",
            200,
            data=data
        )
        
        if success and 'access_token' in response:
            self.token = response['access_token']
            self.vendor_id = response['vendor']['id']
            print(f"Logged in vendor with ID: {self.vendor_id}")
            return True
        return False

    def test_get_vendor_profile(self):
        """Test getting vendor profile"""
        success, response = self.run_test(
            "Get Vendor Profile",
            "GET",
            "api/vendor/profile",
            200
        )
        return success

    def test_create_product(self):
        """Test creating a product"""
        # Create product without image first
        product_data = {
            "name": f"Test Product {uuid.uuid4().hex[:8]}",
            "price": 99.99,
            "description": "This is a test product description",
            "quantity": 10,
            "category": "Electronics"
        }
        
        # For multipart form data
        success, response = self.run_test(
            "Create Product",
            "POST",
            "api/products",
            200,
            data=product_data,
            form_data=True
        )
        
        if success and 'id' in response:
            product_id = response['id']
            self.product_ids.append(product_id)
            print(f"Created product with ID: {product_id}")
            return True
        return False

    def test_get_products(self):
        """Test getting all products"""
        success, response = self.run_test(
            "Get Products",
            "GET",
            "api/products",
            200
        )
        
        if success:
            print(f"Retrieved {len(response)} products")
        return success

    def test_get_product(self, product_id):
        """Test getting a specific product"""
        success, response = self.run_test(
            "Get Product",
            "GET",
            f"api/products/{product_id}",
            200
        )
        return success

    def test_update_product(self, product_id):
        """Test updating a product"""
        update_data = {
            "name": f"Updated Product {uuid.uuid4().hex[:8]}",
            "price": 129.99,
            "description": "This is an updated test product description",
            "quantity": 15,
            "category": "Electronics"
        }
        
        success, response = self.run_test(
            "Update Product",
            "PUT",
            f"api/products/{product_id}",
            200,
            data=update_data,
            form_data=True
        )
        return success

    def test_delete_product(self, product_id):
        """Test deleting a product"""
        success, _ = self.run_test(
            "Delete Product",
            "DELETE",
            f"api/products/{product_id}",
            200
        )
        
        if success:
            if product_id in self.product_ids:
                self.product_ids.remove(product_id)
        return success

    def test_generate_sample_orders(self):
        """Test generating sample orders"""
        success, response = self.run_test(
            "Generate Sample Orders",
            "POST",
            "api/generate-sample-orders",
            200
        )
        return success

    def test_get_orders(self):
        """Test getting all orders"""
        success, response = self.run_test(
            "Get Orders",
            "GET",
            "api/orders",
            200
        )
        
        if success:
            print(f"Retrieved {len(response)} orders")
        return success

def main():
    # Get backend URL from frontend .env
    backend_url = "https://d0a4121e-d471-4270-a6f3-f6408f8919b6.preview.emergentagent.com"
    
    print(f"Testing KiaKart Africa Vendor Dashboard API at: {backend_url}")
    print("=" * 80)
    
    tester = KiaKartAPITester(backend_url)
    
    # Test health check
    if not tester.test_health_check():
        print("❌ Health check failed, stopping tests")
        return 1
    
    # Test vendor registration
    if not tester.test_register_vendor():
        print("❌ Vendor registration failed, stopping tests")
        return 1
    
    # Test vendor profile
    if not tester.test_get_vendor_profile():
        print("❌ Getting vendor profile failed")
    
    # Test product creation
    if not tester.test_create_product():
        print("❌ Product creation failed")
    
    # Test getting all products
    if not tester.test_get_products():
        print("❌ Getting products failed")
    
    # Test getting a specific product
    if tester.product_ids:
        if not tester.test_get_product(tester.product_ids[0]):
            print(f"❌ Getting product {tester.product_ids[0]} failed")
    
    # Test updating a product
    if tester.product_ids:
        if not tester.test_update_product(tester.product_ids[0]):
            print(f"❌ Updating product {tester.product_ids[0]} failed")
    
    # Test generating sample orders
    if not tester.test_generate_sample_orders():
        print("❌ Generating sample orders failed")
    
    # Test getting orders
    if not tester.test_get_orders():
        print("❌ Getting orders failed")
    
    # Test deleting a product
    if tester.product_ids:
        if not tester.test_delete_product(tester.product_ids[0]):
            print(f"❌ Deleting product {tester.product_ids[0]} failed")
    
    # Print results
    print("\n" + "=" * 80)
    print(f"📊 Tests passed: {tester.tests_passed}/{tester.tests_run}")
    print(f"Success rate: {(tester.tests_passed / tester.tests_run) * 100:.2f}%")
    
    return 0 if tester.tests_passed == tester.tests_run else 1

if __name__ == "__main__":
    sys.exit(main())