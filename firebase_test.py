import firebase_admin
from firebase_admin import credentials, firestore

# Load key
cred = credentials.Certificate("firebase-key.json")

# Initialize Firebase
firebase_admin.initialize_app(cred)

# Connect Firestore
db = firestore.client()

# Test write
db.collection("test_connection").document("first_test").set({
    "message": "Firebase connected 🚀",
    "system": "LKF ERP"
})

print("✅ Firebase connected successfully")