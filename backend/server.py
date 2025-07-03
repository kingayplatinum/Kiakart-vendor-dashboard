import os
import uuid
from datetime import datetime, timedelta
from typing import Optional, List
import hashlib
import jwt
from fastapi import FastAPI, HTTPException, Depends, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.staticfiles import StaticFiles
from pymongo import MongoClient
from pydantic import BaseModel, EmailStr
import shutil
from pathlib import Path
import random

# Initialize FastAPI app
app = FastAPI(title="KiaKart Vendor Dashboard API")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# MongoDB connection
MONGO_URL = os.environ.get('MONGO_URL', 'mongodb://localhost:27017/')
client = MongoClient(MONGO_URL)
db = client.kiakart_vendor_db

# Collections
vendors_collection = db.vendors
products_collection = db.products
orders_collection = db.orders

# JWT settings
SECRET_KEY = "kiakart-vendor-secret-key-2025"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 1440  # 24 hours

# Security
security = HTTPBearer()

# Create uploads directory
UPLOAD_DIR = Path("/app/backend/uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

# Serve static files
app.mount("/uploads", StaticFiles(directory=str(UPLOAD_DIR)), name="uploads")

# Pydantic models
class VendorRegister(BaseModel):
    email: EmailStr
    password: str
    name: str
    business_name: str
    phone: str

class VendorLogin(BaseModel):
    email: EmailStr
    password: str

class ProductCreate(BaseModel):
    name: str
    price: float
    description: str
    quantity: int
    category: str

class ProductUpdate(BaseModel):
    name: Optional[str] = None
    price: Optional[float] = None
    description: Optional[str] = None
    quantity: Optional[int] = None
    category: Optional[str] = None

# Helper functions
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(password: str, hashed: str) -> bool:
    return hash_password(password) == hashed

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

def get_current_vendor(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        vendor_id: str = payload.get("sub")
        if vendor_id is None:
            raise HTTPException(status_code=401, detail="Invalid token")
        return vendor_id
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")

# API Routes
@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "service": "KiaKart Vendor Dashboard API"}

@app.post("/api/auth/register")
async def register_vendor(vendor: VendorRegister):
    # Check if vendor already exists
    existing_vendor = vendors_collection.find_one({"email": vendor.email})
    if existing_vendor:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Create new vendor
    vendor_id = str(uuid.uuid4())
    vendor_data = {
        "id": vendor_id,
        "email": vendor.email,
        "password_hash": hash_password(vendor.password),
        "name": vendor.name,
        "business_name": vendor.business_name,
        "phone": vendor.phone,
        "created_at": datetime.utcnow()
    }
    
    vendors_collection.insert_one(vendor_data)
    
    # Create access token
    access_token = create_access_token(data={"sub": vendor_id})
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "vendor": {
            "id": vendor_id,
            "email": vendor.email,
            "name": vendor.name,
            "business_name": vendor.business_name,
            "phone": vendor.phone
        }
    }

@app.post("/api/auth/login")
async def login_vendor(vendor: VendorLogin):
    # Find vendor
    db_vendor = vendors_collection.find_one({"email": vendor.email})
    if not db_vendor or not verify_password(vendor.password, db_vendor["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Create access token
    access_token = create_access_token(data={"sub": db_vendor["id"]})
    
    return {
        "access_token": access_token,
        "token_type": "bearer",
        "vendor": {
            "id": db_vendor["id"],
            "email": db_vendor["email"],
            "name": db_vendor["name"],
            "business_name": db_vendor["business_name"],
            "phone": db_vendor["phone"]
        }
    }

@app.get("/api/vendor/profile")
async def get_vendor_profile(vendor_id: str = Depends(get_current_vendor)):
    vendor = vendors_collection.find_one({"id": vendor_id})
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    
    return {
        "id": vendor["id"],
        "email": vendor["email"],
        "name": vendor["name"],
        "business_name": vendor["business_name"],
        "phone": vendor["phone"]
    }

@app.post("/api/products")
async def create_product(
    name: str = Form(...),
    price: float = Form(...),
    description: str = Form(...),
    quantity: int = Form(...),
    category: str = Form(...),
    images: List[UploadFile] = File([]),
    vendor_id: str = Depends(get_current_vendor)
):
    # Handle image uploads
    image_paths = []
    for image in images:
        if image.filename:
            # Generate unique filename
            file_extension = image.filename.split('.')[-1]
            unique_filename = f"{uuid.uuid4()}.{file_extension}"
            file_path = UPLOAD_DIR / unique_filename
            
            # Save file
            with open(file_path, "wb") as buffer:
                shutil.copyfileobj(image.file, buffer)
            
            image_paths.append(f"/uploads/{unique_filename}")
    
    # Create product
    product_id = str(uuid.uuid4())
    product_data = {
        "id": product_id,
        "vendor_id": vendor_id,
        "name": name,
        "price": price,
        "description": description,
        "quantity": quantity,
        "category": category,
        "images": image_paths,
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }
    
    products_collection.insert_one(product_data)
    
    return {
        "id": product_id,
        "vendor_id": vendor_id,
        "name": name,
        "price": price,
        "description": description,
        "quantity": quantity,
        "category": category,
        "images": image_paths,
        "created_at": product_data["created_at"],
        "updated_at": product_data["updated_at"]
    }

@app.get("/api/products")
async def get_vendor_products(vendor_id: str = Depends(get_current_vendor)):
    products = list(products_collection.find({"vendor_id": vendor_id}))
    
    # Convert ObjectId to string and format dates
    for product in products:
        product.pop("_id", None)
    
    return products

@app.get("/api/products/{product_id}")
async def get_product(product_id: str, vendor_id: str = Depends(get_current_vendor)):
    product = products_collection.find_one({"id": product_id, "vendor_id": vendor_id})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    product.pop("_id", None)
    return product

@app.put("/api/products/{product_id}")
async def update_product(
    product_id: str,
    name: str = Form(None),
    price: float = Form(None),
    description: str = Form(None),
    quantity: int = Form(None),
    category: str = Form(None),
    images: List[UploadFile] = File([]),
    vendor_id: str = Depends(get_current_vendor)
):
    # Check if product exists
    product = products_collection.find_one({"id": product_id, "vendor_id": vendor_id})
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    # Prepare update data
    update_data = {"updated_at": datetime.utcnow()}
    if name is not None:
        update_data["name"] = name
    if price is not None:
        update_data["price"] = price
    if description is not None:
        update_data["description"] = description
    if quantity is not None:
        update_data["quantity"] = quantity
    if category is not None:
        update_data["category"] = category
    
    # Handle new images
    if images and images[0].filename:
        image_paths = []
        for image in images:
            if image.filename:
                file_extension = image.filename.split('.')[-1]
                unique_filename = f"{uuid.uuid4()}.{file_extension}"
                file_path = UPLOAD_DIR / unique_filename
                
                with open(file_path, "wb") as buffer:
                    shutil.copyfileobj(image.file, buffer)
                
                image_paths.append(f"/uploads/{unique_filename}")
        
        update_data["images"] = image_paths
    
    # Update product
    products_collection.update_one({"id": product_id}, {"$set": update_data})
    
    # Return updated product
    updated_product = products_collection.find_one({"id": product_id})
    updated_product.pop("_id", None)
    return updated_product

@app.delete("/api/products/{product_id}")
async def delete_product(product_id: str, vendor_id: str = Depends(get_current_vendor)):
    result = products_collection.delete_one({"id": product_id, "vendor_id": vendor_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Product not found")
    
    return {"message": "Product deleted successfully"}

@app.get("/api/orders")
async def get_vendor_orders(vendor_id: str = Depends(get_current_vendor)):
    # Get all vendor products to find orders
    vendor_products = list(products_collection.find({"vendor_id": vendor_id}))
    product_ids = [product["id"] for product in vendor_products]
    
    # Get orders for these products
    orders = list(orders_collection.find({"product_id": {"$in": product_ids}}))
    
    # Enrich orders with product information
    for order in orders:
        order.pop("_id", None)
        product = next((p for p in vendor_products if p["id"] == order["product_id"]), None)
        if product:
            order["product_name"] = product["name"]
            order["product_image"] = product["images"][0] if product["images"] else None
    
    return orders

@app.post("/api/generate-sample-orders")
async def generate_sample_orders(vendor_id: str = Depends(get_current_vendor)):
    # Get vendor products
    vendor_products = list(products_collection.find({"vendor_id": vendor_id}))
    
    if not vendor_products:
        raise HTTPException(status_code=400, detail="No products found. Add some products first.")
    
    # Sample customer names and emails
    customers = [
        {"name": "John Doe", "email": "john@example.com"},
        {"name": "Jane Smith", "email": "jane@example.com"},
        {"name": "Mike Johnson", "email": "mike@example.com"},
        {"name": "Sarah Wilson", "email": "sarah@example.com"},
        {"name": "David Brown", "email": "david@example.com"},
        {"name": "Emma Davis", "email": "emma@example.com"},
        {"name": "Chris Taylor", "email": "chris@example.com"},
        {"name": "Lisa Anderson", "email": "lisa@example.com"},
    ]
    
    statuses = ["pending", "confirmed", "shipped", "delivered", "cancelled"]
    
    # Generate 10-15 sample orders
    orders_to_create = []
    for _ in range(random.randint(10, 15)):
        product = random.choice(vendor_products)
        customer = random.choice(customers)
        quantity = random.randint(1, 5)
        
        order_data = {
            "id": str(uuid.uuid4()),
            "vendor_id": vendor_id,
            "product_id": product["id"],
            "quantity": quantity,
            "total_price": product["price"] * quantity,
            "customer_name": customer["name"],
            "customer_email": customer["email"],
            "status": random.choice(statuses),
            "created_at": datetime.utcnow() - timedelta(days=random.randint(0, 30))
        }
        orders_to_create.append(order_data)
    
    # Insert orders
    orders_collection.insert_many(orders_to_create)
    
    return {"message": f"Generated {len(orders_to_create)} sample orders successfully"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)