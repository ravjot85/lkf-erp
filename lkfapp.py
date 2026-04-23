import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore
from datetime import date

# ---------------- FIREBASE INIT ----------------
if not firebase_admin._apps:
    cred = credentials.Certificate("firebase-key.json")
    firebase_admin.initialize_app(cred)

db = firestore.client()

# ---------------- PAGE CONFIG ----------------
st.set_page_config(page_title="LKF ERP", layout="wide")

# ---------------- SIDEBAR ----------------
st.sidebar.title("🧶 LKF ERP")

menu = st.sidebar.radio(
    "Navigation",
    [
        "Dashboard",
        "Customer Master",
        "Item Master",
        "PO",
        "Shoot Order",
        "Process Out",
        "Process Inward",
        "Packing",
        "Cancel Order",
        "Reports",
    ],
)

st.title("LKF ERP System")

# ---------------- HELPERS ----------------
def get_next_order_id():
    docs = db.collection("po").stream()
    max_id = 1000
    for doc in docs:
        try:
            oid = int(doc.id)
            max_id = max(max_id, oid)
        except:
            continue
    return str(max_id + 1)


def get_customer_list():
    docs = db.collection("customer_master").stream()
    return sorted([doc.id for doc in docs])


def get_item_list():
    docs = db.collection("item_master").stream()
    return sorted([doc.id for doc in docs])


# ---------------- DASHBOARD ----------------
if menu == "Dashboard":
    st.subheader("📊 Dashboard")
    st.info("Dashboard will be added later")

# ---------------- CUSTOMER MASTER ----------------
elif menu == "Customer Master":
    st.subheader("👥 Customer Master")

    action = st.radio("Action", ["Add Customer", "View Customers"], horizontal=True)

    if action == "Add Customer":
        name = st.text_input("Customer Name")

        if st.button("Save Customer"):
            if name.strip():
                db.collection("customer_master").document(name.upper()).set({
                    "CustomerName": name.upper()
                })
                st.success("Customer saved")
            else:
                st.error("Enter customer name")

    else:
        st.write(get_customer_list())

# ---------------- ITEM MASTER ----------------
elif menu == "Item Master":
    st.subheader("🧵 Item Master")

    action = st.radio("Action", ["Add Item", "View Items"], horizontal=True)

    if action == "Add Item":
        item = st.text_input("Item Name")

        if st.button("Save Item"):
            if item.strip():
                db.collection("item_master").document(item.upper()).set({
                    "ItemName": item.upper()
                })
                st.success("Item saved")
            else:
                st.error("Enter item name")

    else:
        st.write(get_item_list())

# ---------------- PO MODULE ----------------
elif menu == "PO":
    st.subheader("📄 PO Module")

    if "new_order_id" not in st.session_state:
        st.session_state.new_order_id = get_next_order_id()

    order_id = st.session_state.new_order_id
    st.success(f"Generated OrderId: {order_id}")

    customers = get_customer_list()
    items = get_item_list()

    col1, col2 = st.columns(2)

    with col1:
        category = st.selectbox("Category", ["STRIPE", "PLAIN"])

        if customers:
            customer_name = st.selectbox("Customer", customers)
        else:
            st.warning("Add customer first")
            customer_name = ""

        if items:
            item = st.selectbox("Item", items)
        else:
            st.warning("Add item first")
            item = ""

        date_value = st.date_input("Date", value=date.today())
        date_str = date_value.strftime("%Y-%m-%d")

        gsm = st.number_input("GSM", min_value=0)
        fabric_qnty = st.number_input("Fabric Qty", min_value=0)
        accessory_qnty = st.number_input("Accessory Qty", min_value=0)

    with col2:
        fabric_price = st.number_input("Fabric Price", min_value=0)
        accessory_price = st.number_input("Accessory Price", min_value=0)
        colours_instructions = st.text_area("Colours Instructions")
        customer_po_no = st.text_input("Customer PO No")

        uploaded_image = st.file_uploader(
            "Upload Image",
            type=["jpg", "jpeg", "png", "webp"]
        )

    image_link = ""

    if uploaded_image is not None:
        st.image(uploaded_image, width=200)

    if st.button("Save PO"):

        if not customers or not items:
            st.error("Add customer and item first")
        else:
            db.collection("po").document(order_id).set({
                "Category": category,
                "Customer name": customer_name,
                "Item": item,
                "Date": date_str,
                "OrderId": order_id,
                "gsm": gsm,
                "facricqnty": fabric_qnty,
                "accessoryqnty": accessory_qnty,
                "fabricprice": fabric_price,
                "accessoryprice": accessory_price,
                "coloursinstructions": colours_instructions,
                "customerpono": customer_po_no,
                "image": image_link
            })

            st.success(f"PO {order_id} saved")
            st.session_state.new_order_id = str(int(order_id) + 1)

# ---------------- PLACEHOLDER MODULES ----------------
elif menu == "Shoot Order":
    st.subheader("🎯 Shoot Order")
    st.info("Next module")

elif menu == "Process Out":
    st.subheader("🚚 Process Out")
    st.info("Next module")

elif menu == "Process Inward":
    st.subheader("📥 Process Inward")
    st.info("Next module")

elif menu == "Packing":
    st.subheader("📦 Packing")
    st.info("Next module")

elif menu == "Cancel Order":
    st.subheader("❌ Cancel Order")
    st.info("Next module")

elif menu == "Reports":
    st.subheader("📈 Reports")
    st.info("Next module")