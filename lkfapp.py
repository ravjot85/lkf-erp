import socket as _socket, platform as _platform
if _platform.system() == "Windows":
    _orig_getaddrinfo = _socket.getaddrinfo
    def _ipv4_getaddrinfo(host, port, family=0, type=0, proto=0, flags=0):
        return _orig_getaddrinfo(host, port, _socket.AF_INET, type, proto, flags)
    _socket.getaddrinfo = _ipv4_getaddrinfo

import streamlit as st
import firebase_admin
from firebase_admin import credentials, firestore, storage as fb_storage
from datetime import date
import io
import json
import pandas as pd

from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle,
    Paragraph, Spacer, Image as RLImage,
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER

from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload
from google.oauth2 import service_account

# ─────────────────────────────────────────────────────────
#  CONFIG  ← paste your Google Drive folder ID here
# ─────────────────────────────────────────────────────────
DRIVE_FOLDER_ID      = "0AAXVNV0_tBbqUk9PVA"           # Shared Drive root
PO_IMAGES_FOLDER     = "1EsVdPRfOX6qW3EqkV9ohOc3z8yXCkazU"  # PO IMAGES
PO_PDF_FOLDER        = "1B5vthuV61a3h1F1nOg7v0x966uyGaiAX"   # PO PDF
SHOOT_PDF_FOLDER     = "1-6oYnJjFagl1Grvbx-Ji6rI0yD49mqgG"   # Shoot order pdf
PROC_OUT_PDF_FOLDER  = "1OWzxNkDhCEpoM_PUwQzJH-EePvP_SSt6"  # Process Out PDF
PROC_IN_PDF_FOLDER   = "1CFRfp8ctHKuawja-yxruaSTLV1wn7W3p"   # Process Inward PDF
PACKING_PDF_FOLDER   = "1Yk7mw4PYBviU9c8F5d6IzMTs21syQVrg"   # Packing List PDF
COMPANY_NAME         = "Lovely Knitfab"

# ─────────────────────────────────────────────────────────
#  FIREBASE
# ─────────────────────────────────────────────────────────
try:
    from google.api_core.exceptions import ResourceExhausted as _QuotaError
except ImportError:
    _QuotaError = Exception

def _sa_info() -> dict:
    """Return service account dict from Streamlit secrets (cloud) or local file."""
    if "firebase_key" in st.secrets:
        return dict(st.secrets["firebase_key"])
    with open("firebase-key.json") as f:
        return json.load(f)

if not firebase_admin._apps:
    cred = credentials.Certificate(_sa_info())
    firebase_admin.initialize_app(cred, {
        "storageBucket": "lkf-erp-12c7d.firebasestorage.app"
    })

db = firestore.client()

# ─────────────────────────────────────────────────────────
#  PAGE
# ─────────────────────────────────────────────────────────
st.set_page_config(page_title="LKF ERP — Lovely Knitfab", layout="wide", page_icon="🧶")

# ── Hide × clear buttons globally via JS ──
import streamlit.components.v1 as _gc
_gc.html("""
<script>
(function(){
    function removeClearBtns(){
        var doc = window.parent.document;
        doc.querySelectorAll('button').forEach(function(b){
            var lbl   = (b.getAttribute('aria-label')||'').toLowerCase();
            var title = (b.getAttribute('title')||'').toLowerCase();
            var txt   = b.innerText.trim();
            if(lbl.indexOf('clear')!==-1 || title.indexOf('clear')!==-1 ||
               txt===String.fromCharCode(215) || txt===String.fromCharCode(10005)){
                b.remove();
            }
        });
    }
    removeClearBtns();
    setInterval(removeClearBtns, 300);
    var obs = new MutationObserver(removeClearBtns);
    obs.observe(window.parent.document.body,{childList:true,subtree:true});
})();
</script>
""", height=0)

# ── Global CSS ──
st.markdown("""
<style>
/* ── App background ── */
.main .block-container { padding-top: 1.5rem; padding-bottom: 2rem; }

/* ── Sidebar — light warm cream ── */
[data-testid="stSidebar"] {
    background-color: #FBF6EF !important;
    border-right: 1px solid #E5D0B8;
}
[data-testid="stSidebar"] * { color: #4A3020 !important; }

/* Sidebar nav items */
[data-testid="stSidebar"] [data-testid="stRadio"] label {
    background: transparent;
    border-radius: 8px;
    padding: 7px 12px !important;
    margin: 1px 0;
    font-size: 14px;
    transition: background 0.15s;
    display: block;
    color: #5A3A20 !important;
}
[data-testid="stSidebar"] [data-testid="stRadio"] label:hover {
    background: #EDD8BC !important;
}
[data-testid="stSidebar"] [data-testid="stRadio"] > div { gap: 2px; }

/* Sidebar header */
.sidebar-header {
    background: #EDD8BC;
    padding: 16px 16px 12px;
    margin: -1rem -1rem 1rem;
    border-bottom: 2px solid #C4956A;
}
.sidebar-header h2 { color: #6B3F10 !important; margin:0; font-size:19px; }
.sidebar-header p  { color: #9A6A40 !important; margin:2px 0 0; font-size:11px; letter-spacing:1.5px; text-transform:uppercase; }

/* ── Page header — soft light beige ── */
.page-header {
    background: linear-gradient(135deg, #FAF0E2 0%, #F0DFC0 100%);
    border-left: 5px solid #C4956A;
    padding: 15px 22px;
    border-radius: 10px;
    margin-bottom: 18px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    box-shadow: 0 1px 5px rgba(180,130,80,0.10);
}
.page-header h1 { color: #6B3F10 !important; margin: 0; font-size: 21px; font-weight: 700; }
.page-header p  { color: #9A6A40; margin: 2px 0 0; font-size: 12px; }

/* ── KPI cards ── */
.kpi-card {
    background: #FFFFFF;
    border-radius: 12px;
    padding: 16px 18px;
    box-shadow: 0 1px 6px rgba(180,130,80,0.10);
    border-left: 4px solid #C4956A;
    height: 100%;
}
.kpi-card.pending  { border-left-color: #D4A020; background: #FFFDF5; }
.kpi-card.knitting { border-left-color: #5890D0; background: #F5F8FF; }
.kpi-card.dyeing   { border-left-color: #58A848; background: #F5FFF5; }
.kpi-card.inhouse  { border-left-color: #9068B0; background: #FAF5FF; }
.kpi-card.total    { border-left-color: #C4956A; background: #FFFAF5; }
.kpi-label { color: #A08060; font-size: 11px; text-transform: uppercase; letter-spacing: 1px; margin: 0 0 6px; }
.kpi-value { color: #3D2010; font-size: 30px; font-weight: 700; margin: 0 0 4px; line-height:1; }
.kpi-sub   { color: #C4956A; font-size: 13px; margin: 0; }

/* ── Section headers ── */
.section-header {
    color: #7A4A20;
    font-size: 15px;
    font-weight: 600;
    padding: 6px 0 4px;
    border-bottom: 2px solid #EAD0A8;
    margin-bottom: 10px;
}

/* ── Buttons ── */
.stButton > button {
    background-color: #C4956A !important;
    color: white !important;
    border: none !important;
    border-radius: 8px !important;
    font-weight: 500 !important;
    transition: background 0.2s !important;
}
.stButton > button:hover  { background-color: #A07848 !important; }
.stButton > button[kind="primary"] { background-color: #A07848 !important; }

/* ── Tabs ── */
[data-testid="stTabs"] [data-baseweb="tab"] {
    background: #F5EAD8;
    border-radius: 8px 8px 0 0;
    margin-right: 3px;
    padding: 6px 16px;
    color: #7A5030;
    font-size: 13px;
}
[data-testid="stTabs"] [aria-selected="true"] {
    background: #C4956A !important;
    color: white !important;
}

/* ── Dataframes ── */
[data-testid="stDataFrame"] { border-radius: 10px; overflow: hidden; }

/* ── Dividers ── */
hr { border-color: #E8D0B0 !important; }

/* ── Alerts ── */
[data-testid="stAlert"] { border-radius: 8px !important; }

/* ── Hide number input +/- step buttons ── */
[data-testid="stNumberInputStepUp"],
[data-testid="stNumberInputStepDown"] { display: none !important; }

/* ── Hide clear (×) button — all variations ── */
button[aria-label*="lear"],
button[title*="lear"],
button[data-testid*="lear"],
[data-testid="textInputClearButton"],
[data-testid="stNumberInput"] button[kind="icon"],
[data-testid="stTextInput"] button[kind="icon"] {
    display: none !important;
    visibility: hidden !important;
    pointer-events: none !important;
    width: 0 !important;
    padding: 0 !important;
    opacity: 0 !important;
}

/* ── Sidebar expanders (menu groups) ── */
[data-testid="stSidebar"] details {
    background: rgba(255,255,255,0.45) !important;
    border: 1px solid #E5D0B8 !important;
    border-radius: 8px !important;
    margin-bottom: 5px !important;
    padding: 0 4px !important;
}
[data-testid="stSidebar"] details summary {
    font-weight: 700 !important;
    color: #6B3F10 !important;
    font-size: 14px !important;
    padding: 8px 6px !important;
}
[data-testid="stSidebar"] details summary:hover { color: #C4956A !important; }

/* ── Sidebar nav buttons ── */
[data-testid="stSidebar"] .stButton button {
    text-align: left !important;
    justify-content: flex-start !important;
    font-size: 13px !important;
    padding: 5px 10px !important;
    border-radius: 6px !important;
    margin: 1px 0 !important;
    width: 100% !important;
}
[data-testid="stSidebar"] .stButton button[kind="secondary"] {
    background: transparent !important;
    border: none !important;
    color: #5A3A20 !important;
    font-weight: normal !important;
    box-shadow: none !important;
}
[data-testid="stSidebar"] .stButton button[kind="secondary"]:hover {
    background: #EDD8BC !important;
    border: none !important;
}
[data-testid="stSidebar"] .stButton button[kind="primary"] {
    background: #C4956A !important;
    color: white !important;
    border: none !important;
    font-weight: 600 !important;
}
</style>
""", unsafe_allow_html=True)

# ── Navigation state ──
if "page"    not in st.session_state: st.session_state.page    = "Dashboard"
if "rpt_sub" not in st.session_state: st.session_state.rpt_sub = "📋 All Orders"

_FORMS = [
    ("📄", "PO"),
    ("🎯", "Shoot Order"),
    ("🚚", "Process Out"),
    ("📥", "Process Inward"),
    ("📦", "Packing"),
    ("❌", "Cancel Order"),
]
_REPORTS = [
    "📋 All Orders",
    "🔵 Pending — STRIPE",
    "🟠 Pending — PLAIN",
    "⚙️ In Production",
    "❌ Cancelled",
    "👤 Customer Report",
    "👤 Customer Pending",
    "🔍 Pending Drill-Down",
    "📦 Pending by Item",
    "🔄 Processing Report",
    "📦 Part Dispatched",
    "🏠 In House Finishing",
]
_MASTERS = [
    ("👥", "Customer Master"),
    ("🧵", "Item Master"),
    ("🏭", "Processor Master"),
]

def _nav(icon, label, page, rpt=None):
    active = (st.session_state.page == page and
              (rpt is None or st.session_state.rpt_sub == rpt))
    if st.button(f"{icon}  {label}", key=f"_nav_{page}_{rpt or ''}",
                 use_container_width=True,
                 type="primary" if active else "secondary"):
        st.session_state.page = page
        if rpt: st.session_state.rpt_sub = rpt
        st.rerun()

# ── Sidebar ──
st.sidebar.markdown("""
<div class="sidebar-header">
    <h2>🧶 LKF ERP</h2>
    <p>Lovely Knitfab</p>
</div>
""", unsafe_allow_html=True)

# Dashboard
with st.sidebar:
    _nav("📊", "Dashboard", "Dashboard")

    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)

    with st.expander("📋  Forms",
                     expanded=st.session_state.page in [p for _,p in _FORMS]):
        for icon, page in _FORMS:
            _nav(icon, page, page)

    with st.expander("📈  Reports",
                     expanded=st.session_state.page == "Reports"):
        for rpt in _REPORTS:
            parts = rpt.split(" ", 1)
            icon, label = parts[0], parts[1] if len(parts) > 1 else ""
            _nav(icon, label, "Reports", rpt)

    with st.expander("🗂️  Masters",
                     expanded=st.session_state.page in [p for _,p in _MASTERS]):
        for icon, page in _MASTERS:
            _nav(icon, page, page)

    _EDITS = [
        ("✏️", "Edit PO"),
        ("✏️", "Edit Packing List"),
        ("🗑️", "Delete Packing List"),
        ("✏️", "Edit Process Out"),
        ("✏️", "Edit Process Inward"),
        ("🚫", "Cancel Shoot Order"),
    ]
    with st.expander("✏️  Edits",
                     expanded=st.session_state.page in [p for _,p in _EDITS]):
        for icon, page in _EDITS:
            _nav(icon, page, page)

    st.markdown("<div style='height:6px'></div>", unsafe_allow_html=True)
    _nav("📥", "Import Data", "Import Data")

menu = st.session_state.page

# ─────────────────────────────────────────────────────────
#  GOOGLE DRIVE HELPERS
# ─────────────────────────────────────────────────────────
def _drive_service():
    creds = service_account.Credentials.from_service_account_info(
        _sa_info(),
        scopes=["https://www.googleapis.com/auth/drive"],
    )
    return build("drive", "v3", credentials=creds)


def upload_to_drive(file_bytes: bytes, filename: str, mimetype: str,
                    folder_id: str = None) -> dict:
    """Upload bytes to Google Shared Drive. Returns {'id': ..., 'url': ...}."""
    svc = _drive_service()
    meta = {"name": filename}
    target_folder = folder_id or DRIVE_FOLDER_ID
    if target_folder:
        meta["parents"] = [target_folder]
    media = MediaIoBaseUpload(io.BytesIO(file_bytes), mimetype=mimetype)
    f = svc.files().create(
        body=meta, media_body=media,
        fields="id,webViewLink",
        supportsAllDrives=True,
    ).execute()
    svc.permissions().create(
        fileId=f["id"],
        body={"type": "anyone", "role": "reader"},
        supportsAllDrives=True,
    ).execute()
    return {"id": f["id"], "url": f.get("webViewLink", "")}


def upload_to_firebase_storage(file_bytes: bytes, dest_path: str, content_type: str) -> str:
    """Upload bytes to Firebase Storage. Returns public download URL."""
    bucket = fb_storage.bucket()
    blob   = bucket.blob(dest_path)
    blob.upload_from_string(file_bytes, content_type=content_type)
    blob.make_public()
    return blob.public_url


def download_from_drive(file_id: str) -> bytes:
    """Download a file from Google Drive by its file ID."""
    svc = _drive_service()
    req = svc.files().get_media(fileId=file_id)
    buf = io.BytesIO()
    dl = MediaIoBaseDownload(buf, req)
    done = False
    while not done:
        _, done = dl.next_chunk()
    return buf.getvalue()


@st.cache_data(ttl=600, show_spinner=False)
def _fetch_image_bytes(file_id: str):
    """Download and cache image bytes from Drive. Returns None on failure."""
    try:
        return download_from_drive(file_id)
    except Exception:
        return None


# ─────────────────────────────────────────────────────────
#  PDF HELPERS
# ─────────────────────────────────────────────────────────
_TABLE_COL_WIDTHS = [3.8*cm, 6.2*cm, 4*cm, 5*cm]

_LABEL_BG   = colors.HexColor("#dce6f7")
_HEADER_BG  = colors.HexColor("#1a3c6e")


def _base_table_style() -> TableStyle:
    return TableStyle([
        ("BACKGROUND",  (0, 0), (0, -1), _LABEL_BG),
        ("BACKGROUND",  (2, 0), (2, -1), _LABEL_BG),
        ("FONTNAME",    (0, 0), (-1, -1), "Helvetica-Bold"),
        ("FONTNAME",    (1, 0), (1, -1),  "Helvetica"),
        ("FONTNAME",    (3, 0), (3, -1),  "Helvetica"),
        ("FONTSIZE",    (0, 0), (-1, -1), 10),
        ("GRID",        (0, 0), (-1, -1), 0.5, colors.grey),
        ("VALIGN",      (0, 0), (-1, -1), "MIDDLE"),
        ("PADDING",     (0, 0), (-1, -1), 6),
    ])


def _pdf_header(elements, styles, subtitle: str):
    _navy   = colors.HexColor("#1a3c6e")
    _camel  = colors.HexColor("#C4956A")
    _white  = colors.white

    # Company name — white text on navy banner
    co_s = ParagraphStyle(
        "co", parent=styles["Normal"],
        fontName="Helvetica-Bold", fontSize=16,
        alignment=TA_CENTER, textColor=_white,
        spaceAfter=0, spaceBefore=0,
    )
    addr_s = ParagraphStyle(
        "addr", parent=styles["Normal"],
        fontName="Helvetica", fontSize=8,
        alignment=TA_CENTER, textColor=_white,
        spaceAfter=0, spaceBefore=0,
    )
    sub_s = ParagraphStyle(
        "sub", parent=styles["Normal"],
        fontName="Helvetica-Bold", fontSize=12,
        alignment=TA_CENTER, textColor=_white,
        spaceAfter=0, spaceBefore=0,
    )

    # Navy banner — company name + address
    banner = Table(
        [[Paragraph("LOVELY KNITFAB PVT. LTD.", co_s)],
         [Paragraph("HB No. 85, Vill. Kasabad, Ludhiana  |  GSTIN: 03AAECL9162H1Z1  |  Ph: 98766-82001", addr_s)]],
        colWidths=[19*cm],
    )
    banner.setStyle(TableStyle([
        ("BACKGROUND",  (0, 0), (-1, -1), _navy),
        ("TOPPADDING",  (0, 0), (-1, -1), 8),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 6),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING",(0, 0), (-1, -1), 0),
    ]))
    elements.append(banner)

    # Camel subtitle bar
    sub_bar = Table(
        [[Paragraph(subtitle, sub_s)]],
        colWidths=[19*cm],
    )
    sub_bar.setStyle(TableStyle([
        ("BACKGROUND",   (0, 0), (-1, -1), _camel),
        ("TOPPADDING",   (0, 0), (-1, -1), 5),
        ("BOTTOMPADDING",(0, 0), (-1, -1), 5),
        ("LEFTPADDING",  (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 0),
    ]))
    elements.append(sub_bar)
    elements.append(Spacer(1, 0.4*cm))


def _embed_image(elements, image_bytes: bytes, max_w=10, max_h=10):
    """Add a proportionally scaled image to the elements list."""
    try:
        from PIL import Image as PILImg
        pil = PILImg.open(io.BytesIO(image_bytes))
        w, h = pil.size
        scale = min((max_w * cm) / w, (max_h * cm) / h)
        img_w, img_h = w * scale, h * scale
    except Exception:
        img_w, img_h = max_w * cm, max_h * cm
    try:
        elements.append(RLImage(io.BytesIO(image_bytes), width=img_w, height=img_h))
    except Exception:
        pass


def build_po_pdf(d: dict, image_bytes: bytes = None) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        topMargin=1.5*cm, bottomMargin=1.5*cm,
        leftMargin=1.5*cm, rightMargin=1.5*cm,
    )
    styles = getSampleStyleSheet()
    elements = []
    _pdf_header(elements, styles, "PURCHASE ORDER")

    rows = [
        ["Order ID",       str(d.get("OrderId", "")),          "Date",             str(d.get("Date", ""))],
        ["Customer",       str(d.get("Customer name", "")),     "Customer PO No",   str(d.get("customerpono", ""))],
        ["Item",           str(d.get("Item", "")),              "Category",         str(d.get("Category", ""))],
        ["GSM",            str(d.get("gsm", "")),               "Fabric Qty",       str(d.get("facricqnty", ""))],
        ["Fabric Price",   str(d.get("fabricprice", "")),       "Accessory Qty",    str(d.get("accessoryqnty", ""))],
        ["Acc. Price",     str(d.get("accessoryprice", "")),    "",                 ""],
    ]
    t = Table(rows, colWidths=_TABLE_COL_WIDTHS)
    t.setStyle(_base_table_style())
    elements.append(t)
    elements.append(Spacer(1, 0.5*cm))

    if d.get("coloursinstructions"):
        elements.append(Paragraph("<b>Colours / Instructions:</b>", styles["Normal"]))
        elements.append(Paragraph(str(d["coloursinstructions"]), styles["Normal"]))
        elements.append(Spacer(1, 0.4*cm))

    if d.get("accessory"):
        elements.append(Paragraph("<b>Accessory Description:</b>", styles["Normal"]))
        elements.append(Paragraph(str(d["accessory"]), styles["Normal"]))
        elements.append(Spacer(1, 0.4*cm))

    if image_bytes:
        _embed_image(elements, image_bytes)

    doc.build(elements)
    return buf.getvalue()


def build_shoot_order_pdf(d: dict, image_bytes: bytes = None) -> bytes:
    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf, pagesize=A4,
        topMargin=1.5*cm, bottomMargin=1.5*cm,
        leftMargin=1.5*cm, rightMargin=1.5*cm,
    )
    styles = getSampleStyleSheet()
    elements = []
    _pdf_header(elements, styles, "SHOOT ORDER")

    rows = [
        ["Order ID",   str(d.get("OrderId", "")),       "Date",    str(d.get("Date", ""))],
        ["Customer",   str(d.get("Customer name", "")), "Item",    str(d.get("Item", ""))],
        ["Category",   str(d.get("Category", "")),      "GSM",     str(d.get("gsm", ""))],
    ]
    t = Table(rows, colWidths=_TABLE_COL_WIDTHS)
    t.setStyle(_base_table_style())
    elements.append(t)
    elements.append(Spacer(1, 0.5*cm))

    if d.get("coloursinstructions"):
        elements.append(Paragraph("<b>Colours / Instructions:</b>", styles["Normal"]))
        elements.append(Paragraph(str(d["coloursinstructions"]), styles["Normal"]))
        elements.append(Spacer(1, 0.4*cm))

    if (d.get("accessory") or "").strip():
        elements.append(Paragraph("<b>Accessory Description:</b>", styles["Normal"]))
        elements.append(Paragraph(str(d["accessory"]), styles["Normal"]))
        elements.append(Spacer(1, 0.4*cm))

    if image_bytes:
        _embed_image(elements, image_bytes)

    doc.build(elements)
    return buf.getvalue()


# ─────────────────────────────────────────────────────────
#  FIRESTORE HELPERS
# ─────────────────────────────────────────────────────────
def get_next_order_id() -> str:
    """Return next PO Order ID using an atomic Firestore counter."""
    counter_ref = db.collection("counters").document("po_order_id")

    # Initialise counter on first ever call
    if not counter_ref.get().exists:
        max_id = max(
            (int(d.id) for d in db.collection("po").stream() if d.id.isdigit()),
            default=1000,
        )
        counter_ref.set({"last_id": max_id})

    @firestore.transactional
    def _increment(transaction, ref):
        snap   = ref.get(transaction=transaction)
        nid    = (snap.to_dict().get("last_id") or 1000) + 1
        transaction.set(ref, {"last_id": nid})
        return str(nid)

    return _increment(db.transaction(), counter_ref)


def get_customer_list():
    return sorted({doc.id.upper().strip().replace(" ", "") for doc in db.collection("customer_master").stream()})


def _fmt_date(s: str) -> str:
    """Convert YYYY-MM-DD to DD/MM/YYYY for display. Returns original if conversion fails."""
    try:
        from datetime import datetime as _d
        return _d.strptime(str(s).strip(), "%Y-%m-%d").strftime("%d/%m/%Y")
    except Exception:
        return str(s)


def get_item_list():
    return sorted(doc.id for doc in db.collection("item_master").stream())


def get_processor_list():
    return sorted(doc.id for doc in db.collection("processor_master").stream())


# ═════════════════════════════════════════════════════════
#  SHARED: build status dataframe (used by Dashboard + Reports)
# ═════════════════════════════════════════════════════════
@st.cache_data(ttl=120, show_spinner=False)
def _load_status_df():
    po_docs       = [d.to_dict() for d in db.collection("po").stream()]
    shoot_raw     = [d.to_dict() for d in db.collection("shoot_order").stream()]
    shoot_dates   = {d.get("OrderId",""): d.get("Date","") for d in shoot_raw if d.get("OrderId","")}
    shoot_ids     = set(shoot_dates.keys())
    proc_out_raw  = [d.to_dict() for d in db.collection("process_out").stream()]
    proc_in_ids   = {d.to_dict().get("OrderId","") for d in db.collection("process_inward").stream()}
    cancel_ids    = {d.to_dict().get("OrderId","") for d in db.collection("cancel_orders").stream()
                     if d.to_dict().get("Status","VALID").upper().strip() != "INVALID"}

    # Load packing list data — group by BASE numeric OrderId
    # e.g. "1001A", "1001B", "1001" all map to base "1001"
    import re as _re_pack
    def _base_oid(raw):
        m = _re_pack.match(r'^(\d+)', str(raw).strip())
        return m.group(1) if m else str(raw).strip()

    pack_by_base = {}   # base_oid → list of pack dicts
    for d in db.collection("PackingListRaw").stream():
        row  = d.to_dict()
        base = _base_oid(row.get("OrderId",""))
        pack_by_base.setdefault(base, []).append(row)
    pack_ids = set(pack_by_base.keys())

    proc_out_party = {}
    for d in proc_out_raw:
        proc_out_party[d.get("OrderId","")] = d.get("PartyName","")
    proc_out_ids = set(proc_out_party.keys())

    def _parse_packed_qty(details_str):
        total = 0.0
        for line in (details_str or "").splitlines():
            if ":" in line:
                _, wstr = line.split(":", 1)
                for w in wstr.split(","):
                    try: total += float(w.strip())
                    except: pass
        return round(total, 2)

    rows = []
    for d in po_docs:
        oid        = str(d.get("OrderId",""))
        po_fabric  = float(d.get("facricqnty") or 0)
        po_acc     = float(d.get("accessoryqnty") or 0)

        packed_fabric = 0.0
        packed_acc    = 0.0

        # Base numeric OrderId for packing list lookup (e.g. "1001" matches "1001A","1001B")
        base_oid = _base_oid(oid)

        if oid in cancel_ids:
            status = "Cancelled"
        elif base_oid in pack_ids:
            # Any packing list entry = Dispatched (quantity not checked for status)
            pack_rows     = pack_by_base[base_oid]
            packed_fabric = sum(_parse_packed_qty(r.get("FabricDetails",""))   for r in pack_rows)
            packed_acc    = sum(_parse_packed_qty(r.get("AccessoryDetails","")) for r in pack_rows)
            status = "Dispatched"
        elif oid in proc_in_ids:
            status = "In House Finishing/Packing"
        elif oid in proc_out_ids:
            party  = proc_out_party.get(oid, "")
            status = f"On Dyeing/Washing ({party})" if party else "On Dyeing/Washing"
        elif oid in shoot_ids:
            status = "Knitting"
        else:
            status = "Pending"

        rows.append({
            "OrderId":        oid,
            "CustomerPoNo":   d.get("customerpono", ""),
            "Customer":       d.get("Customer name", "").upper().strip().replace(" ", ""),
            "Item":           d.get("Item", ""),
            "Category":       d.get("Category", ""),
            "Date":           _fmt_date(d.get("Date", "")),
            "ShootDate":      _fmt_date(shoot_dates.get(oid, "")),
            "GSM":            int(d.get("gsm") or 0),
            "FabricQty":      po_fabric,
            "FabricPrice":    float(d.get("fabricprice") or 0),
            "AccQty":         po_acc,
            "AccPrice":       float(d.get("accessoryprice") or 0),
            "PackedFabricQty":packed_fabric,
            "PackedAccQty":   packed_acc,
            "Status":         status,
            "pdf_url":        d.get("pdf_url", ""),
            "image_drive_id": d.get("image_drive_id", ""),
            "image_url":      d.get("image", ""),
            "Accessory":      d.get("accessory", ""),
        })
    return pd.DataFrame(rows) if rows else pd.DataFrame()


# ═════════════════════════════════════════════════════════
#  DASHBOARD
# ═════════════════════════════════════════════════════════
def _pending_report(data, label, color_scale, key_prefix):
    import plotly.express as _px2
    if data.empty:
        st.info(f"No pending {label} orders")
        return
    srch = st.text_input("🔍 Search Order ID", placeholder="e.g. 1001",
                          key=f"{key_prefix}_search")
    if srch.strip():
        data = data[data["OrderId"].astype(str).str.contains(srch.strip(), na=False)]
    cols = [c for c in ["OrderId","Customer","Item","Category","Date","FabricQty","Status"]
            if c in data.columns]
    st.markdown(f"**Pending — {label}  —  {len(data)} orders  |  "
                f"Total Qty: {int(data['FabricQty'].sum()):,}**")
    st.caption("Click a row to open the corresponding PO PDF.")
    sel = st.dataframe(
        data[cols].sort_values("OrderId", ascending=False),
        use_container_width=True, hide_index=True,
        on_select="rerun", selection_mode="single-row",
        key=f"{key_prefix}_table"
    )
    rows = sel.selection.rows if hasattr(sel, "selection") else []
    if rows:
        sel_oid = str(data.sort_values("OrderId", ascending=False).iloc[rows[0]]["OrderId"])
        po_doc  = db.collection("po").document(sel_oid).get()
        if po_doc.exists:
            pdf_url = po_doc.to_dict().get("pdf_url", "")
            if pdf_url:
                st.success(f"Order **{sel_oid}**")
                st.markdown(f"[📄 Open PO PDF]({pdf_url})")
            else:
                st.warning(f"PO {sel_oid} found but no PDF linked yet.")
        else:
            st.info(f"PO {sel_oid} not found.")
    if not srch.strip():
        grp = data.groupby("Customer")["FabricQty"].sum().sort_values(ascending=False).reset_index()
        grp.columns = ["Customer","Qty"]
        fig = _px2.bar(grp, x="Customer", y="Qty", title=f"Pending {label} by Customer",
                       color="Qty", color_continuous_scale=color_scale)
        fig.update_layout(height=280, margin=dict(t=40,b=60))
        fig.update_xaxes(tickangle=45)
        st.plotly_chart(fig, use_container_width=True)


if menu == "Dashboard":
    import plotly.express as px
    from datetime import datetime as _dt

    # ── Page header ──
    st.markdown(f"""
    <div class="page-header">
        <div>
            <h1>📊 Production Dashboard</h1>
            <p>Lovely Knitfab &nbsp;·&nbsp; {_dt.today().strftime("%d %B %Y")}</p>
        </div>
        <div style="text-align:right; color:rgba(255,255,255,0.75); font-size:13px;">
            Live data from Firebase
        </div>
    </div>
    """, unsafe_allow_html=True)

    rc1, rc2 = st.columns([6,1])
    with rc2:
        if st.button("🔄 Refresh"):
            st.rerun()

    try:
        with st.spinner("Loading..."):
            df = _load_status_df()
    except Exception as _qe:
        if "429" in str(_qe) or "Quota" in str(_qe) or "RESOURCE_EXHAUSTED" in str(_qe):
            st.error("⚠️ Firebase quota exceeded. Wait a few minutes then refresh, or upgrade to Firebase Blaze plan.")
            st.stop()
        raise _qe

    if df.empty:
        st.info("No PO data yet")
        st.stop()

    # ── Search bar ──
    st.markdown("---")

    if "dash_search" not in st.session_state:
        st.session_state.dash_search = ""

    search_q = st.text_input(
        "🔍  Search by Order ID or Customer Name",
        placeholder="Type Order ID (e.g. 1001) or Customer Name (e.g. ATAM ROOP)",
        key="dash_search"
    )

    # ── Auto-suggestions while typing ──
    q_typed = (st.session_state.get("dash_search") or "").strip().upper()
    if q_typed and len(q_typed) >= 2:
        all_customers = sorted(df["Customer"].dropna().unique().tolist())
        suggestions   = [c for c in all_customers if q_typed in c.upper()]
        # Only show suggestions if the typed value isn't already an exact match
        if suggestions and q_typed not in [s.upper() for s in suggestions] or (
                suggestions and not any(q_typed == s.upper() for s in suggestions)):
            if suggestions:
                st.markdown(
                    '<p style="font-size:12px;color:#9A6A40;margin:2px 0 4px;">Suggestions — click to select:</p>',
                    unsafe_allow_html=True)
                sug_cols = st.columns(min(len(suggestions), 5))
                for i, cust in enumerate(suggestions[:10]):
                    if sug_cols[i % 5].button(
                        cust, key=f"sug_{cust}",
                        use_container_width=True
                    ):
                        st.session_state.dash_search = cust
                        st.rerun()

    if search_q.strip():
        q = search_q.strip().upper()
        # Match Order ID (exact) or Customer name (contains)
        mask = (
            df["OrderId"].astype(str).str.upper().str.contains(q, na=False) |
            df["Customer"].str.upper().str.contains(q, na=False)
        )
        results = df[mask].sort_values("OrderId", ascending=False)

        if results.empty:
            st.warning("No orders found matching your search.")
        else:
            # Dropdown of matching order IDs
            options = [
                f"{row['OrderId']}  —  {row['Customer']}  |  {row['Item']}  |  {row['Status']}"
                for _, row in results.iterrows()
            ]
            selected_opt = st.selectbox(
                f"{len(results)} order(s) found — select to view details:",
                options, key="dash_search_sel"
            )
            sel_oid = selected_opt.split("—")[0].strip()
            sel_row = results[results["OrderId"].astype(str) == sel_oid].iloc[0]

            # Fetch full PO from Firebase for complete details
            po_full = db.collection("po").document(str(sel_oid)).get()
            po_d    = po_full.to_dict() if po_full.exists else {}

            st.markdown("---")
            st.markdown(
                f'<div style="background:#FFF8F0;border:1px solid #E8D0A8;border-radius:10px;'
                f'padding:14px 20px;margin-bottom:10px;">'
                f'<span style="font-size:18px;font-weight:700;color:#6B3F10;">Order #{sel_oid}</span>'
                f'&nbsp;&nbsp;<span style="background:#C4956A;color:white;border-radius:20px;'
                f'padding:3px 12px;font-size:12px;">{sel_row["Status"]}</span>'
                f'</div>', unsafe_allow_html=True)

            img_col, det_col = st.columns([1, 2])

            with img_col:
                drive_id  = po_d.get("image_drive_id","")
                image_url = po_d.get("image","")
                if drive_id:
                    img_bytes = _fetch_image_bytes(drive_id)
                    if img_bytes:
                        st.image(img_bytes, width=220)
                    else:
                        st.markdown('<div style="width:220px;height:160px;background:#F5EAD8;border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:32px;">📷</div>', unsafe_allow_html=True)
                elif image_url:
                    st.image(image_url, width=220)
                else:
                    st.markdown('<div style="width:220px;height:160px;background:#F5EAD8;border-radius:8px;display:flex;flex-direction:column;align-items:center;justify-content:center;color:#B09070;font-size:28px;">📷<br><span style="font-size:11px;margin-top:6px;">No image</span></div>', unsafe_allow_html=True)

            with det_col:
                st.markdown(f"""
                <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px 24px;font-size:14px;">
                    <div><b>Customer:</b> {po_d.get('Customer name', sel_row['Customer'])}</div>
                    <div><b>Category:</b> {po_d.get('Category', sel_row['Category'])}</div>
                    <div><b>Item:</b> {po_d.get('Item', sel_row['Item'])}</div>
                    <div><b>Date:</b> {po_d.get('Date', sel_row['Date'])}</div>
                    <div><b>GSM:</b> {int(po_d.get('gsm') or 0)}</div>
                    <div><b>Customer PO No:</b> {po_d.get('customerpono','—')}</div>
                    <div><b>Fabric Qty:</b> {int(po_d.get('facricqnty') or 0):,}</div>
                    <div><b>Fabric Price:</b> ₹{int(po_d.get('fabricprice') or 0)}</div>
                    <div><b>Accessory Qty:</b> {int(po_d.get('accessoryqnty') or 0):,}</div>
                    <div><b>Accessory Price:</b> ₹{int(po_d.get('accessoryprice') or 0)}</div>
                    <div style="grid-column:span 2"><b>Colours/Instructions:</b> {po_d.get('coloursinstructions','—')}</div>
                    {f'<div style="grid-column:span 2"><b>Accessory Details:</b> {po_d.get("accessory","")}</div>' if po_d.get('accessory') else ''}
                </div>
                """, unsafe_allow_html=True)
                pdf_col1, pdf_col2 = st.columns([2, 2])
                if po_d.get("pdf_url"):
                    pdf_col1.markdown(f"[📄 View PO PDF]({po_d['pdf_url']})")
                if pdf_col2.button("🔄 Regenerate PDF", key=f"regen_pdf_{sel_oid}"):
                    with st.spinner("Regenerating PDF…"):
                        try:
                            # Get image bytes from Firebase URL or Drive
                            _img_bytes = None
                            _img_url   = po_d.get("image", "")
                            _drive_id  = po_d.get("image_drive_id", "")
                            if _img_url:
                                import urllib.request as _ur2
                                try:
                                    with _ur2.urlopen(_img_url, timeout=10) as _r:
                                        _img_bytes = _r.read()
                                except Exception:
                                    _img_bytes = None
                            elif _drive_id:
                                _img_bytes = _fetch_image_bytes(_drive_id)
                            # Rebuild and upload PDF
                            _pdf_bytes = build_po_pdf(po_d, _img_bytes)
                            _new_url   = upload_to_firebase_storage(
                                _pdf_bytes,
                                f"po_pdfs/PO_{sel_oid}.pdf",
                                "application/pdf",
                            )
                            db.collection("po").document(str(sel_oid)).update({"pdf_url": _new_url})
                            st.success(f"PDF regenerated! [📄 Open PDF]({_new_url})")
                        except Exception as _e:
                            st.error(f"Error: {_e}")

    st.markdown("---")

    # Active = exclude Cancelled + Dispatched + Part Dispatched
    df_active   = df[~df["Status"].isin(["Cancelled","Dispatched","Part Dispatched"])]
    pending_df  = df_active[df_active["Status"] == "Pending"]
    knit_df     = df_active[df_active["Status"] == "Knitting"]
    dye_df      = df_active[df_active["Status"].str.startswith("On Dyeing", na=False)]
    inhouse_df  = df_active[df_active["Status"] == "In House Finishing/Packing"]
    disp_df     = df[df["Status"] == "Dispatched"]
    partdisp_df = df[df["Status"] == "Part Dispatched"]
    prod_df     = df_active[
        (df_active["Status"] == "Knitting") |
        df_active["Status"].str.startswith("On Dyeing", na=False) |
        (df_active["Status"] == "In House Finishing/Packing")
    ]

    # ── KPI cards ──
    def kpi(label, count, qty, css_class="total"):
        return f"""
        <div class="kpi-card {css_class}">
            <p class="kpi-label">{label}</p>
            <p class="kpi-value">{count}</p>
            <p class="kpi-sub">{int(qty):,} qty</p>
        </div>"""

    k1, k2, k3 = st.columns(3)
    k1.markdown(kpi("Total Active POs", len(df_active),  df_active["FabricQty"].sum(),  "total"),    unsafe_allow_html=True)
    k2.markdown(kpi("⏳ Pending",        len(pending_df), pending_df["FabricQty"].sum(), "pending"),  unsafe_allow_html=True)
    k3.markdown(kpi("⚙️ In Production", len(prod_df),    prod_df["FabricQty"].sum(),    "knitting"), unsafe_allow_html=True)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Charts ──
    CAMEL_PALETTE = ["#C4956A","#8B6535","#E8C99A","#6B4C2A","#F2DFC0",
                     "#D4A96A","#A07040","#EBB87A","#5C3D11","#F5E6CC"]

    def pie_chart(df_in, col, title):
        if df_in.empty:
            return None
        grp = df_in.groupby(col)["FabricQty"].sum().reset_index()
        grp.columns = [col, "Qty"]
        grp = grp[grp["Qty"] > 0].sort_values("Qty", ascending=False)
        fig = px.pie(grp, names=col, values="Qty", hole=0.38,
                     color_discrete_sequence=CAMEL_PALETTE)
        fig.update_traces(textposition="inside", textinfo="percent+label",
                          textfont_size=11)
        fig.update_layout(
            title=dict(text=title, font=dict(size=14, color="#6B4C2A"), x=0.02),
            showlegend=False,
            margin=dict(t=40, b=10, l=10, r=10),
            height=300,
            paper_bgcolor="white",
            plot_bgcolor="white",
        )
        return fig

    ch1, ch2, ch3 = st.columns(3)
    with ch1:
        st.markdown('<p class="section-header">Pending — Customer Wise</p>', unsafe_allow_html=True)
        fig = pie_chart(pending_df, "Customer", "")
        if fig: st.plotly_chart(fig, use_container_width=True)
        else:   st.info("No pending orders")

    with ch2:
        st.markdown('<p class="section-header">Pending — Category Wise</p>', unsafe_allow_html=True)
        fig = pie_chart(pending_df, "Category", "")
        if fig: st.plotly_chart(fig, use_container_width=True)
        else:   st.info("No pending orders")

    with ch3:
        st.markdown('<p class="section-header">In Production — Customer Wise</p>', unsafe_allow_html=True)
        fig = pie_chart(prod_df, "Customer", "")
        if fig: st.plotly_chart(fig, use_container_width=True)
        else:   st.info("No orders in production")

    # ── Summary tables in expanders ──
    st.markdown("<br>", unsafe_allow_html=True)
    e1, e2, e3 = st.columns(3)

    with e1:
        with st.expander(f"📋 Pending by Customer ({len(pending_df)} orders)", expanded=True):
            if not pending_df.empty:
                tbl = (pending_df.groupby("Customer")
                       .agg(Orders=("OrderId","count"), Qty=("FabricQty","sum"))
                       .sort_values("Qty", ascending=False).reset_index())
                st.caption(f"Total Qty: **{int(tbl['Qty'].sum()):,}**")
                st.dataframe(tbl, use_container_width=True, hide_index=True)

    with e2:
        with st.expander("📋 Pending by Category", expanded=True):
            if not pending_df.empty:
                if "dash_cat" not in st.session_state:
                    st.session_state.dash_cat = None

                stripe_df = pending_df[pending_df["Category"] == "STRIPE"]
                plain_df  = pending_df[pending_df["Category"] == "PLAIN"]

                cb1, cb2 = st.columns(2)
                with cb1:
                    s_active = st.session_state.dash_cat == "STRIPE"
                    if st.button(
                        f"🔵 STRIPE\n{len(stripe_df)} orders · {int(stripe_df['FabricQty'].sum()):,} KG",
                        use_container_width=True, key="dash_stripe_btn",
                        type="primary" if s_active else "secondary"
                    ):
                        st.session_state.dash_cat = None if s_active else "STRIPE"
                        st.rerun()
                with cb2:
                    p_active = st.session_state.dash_cat == "PLAIN"
                    if st.button(
                        f"🟠 PLAIN\n{len(plain_df)} orders · {int(plain_df['FabricQty'].sum()):,} KG",
                        use_container_width=True, key="dash_plain_btn",
                        type="primary" if p_active else "secondary"
                    ):
                        st.session_state.dash_cat = None if p_active else "PLAIN"
                        st.rerun()

                if st.session_state.dash_cat:
                    sel_df = pending_df[pending_df["Category"] == st.session_state.dash_cat]
                    items_grp = (
                        sel_df.groupby("Item")
                        .agg(Orders=("OrderId","count"), TotalQty=("FabricQty","sum"))
                        .sort_values("TotalQty", ascending=False)
                        .reset_index()
                    )
                    st.markdown(f"**{st.session_state.dash_cat}** — {int(sel_df['FabricQty'].sum()):,} KG total across {len(sel_df)} orders")
                    st.markdown("")
                    for _, row in items_grp.iterrows():
                        with st.expander(f"📦 {row['Item']}  —  {int(row['TotalQty']):,} KG  ({int(row['Orders'])} orders)"):
                            item_orders = sel_df[sel_df["Item"] == row["Item"]].sort_values("OrderId", ascending=False)
                            for _, o in item_orders.iterrows():
                                cols = st.columns([1.5, 2.5, 1.2, 1.2])
                                cols[0].markdown(f"**{o['OrderId']}**")
                                cols[1].markdown(o['Customer'])
                                cols[2].markdown(o['Date'])
                                cols[3].markdown(f"**{int(o['FabricQty'])} KG**")
                                if o.get('pdf_url'):
                                    st.markdown(f"&nbsp;&nbsp;&nbsp;[📄 View PDF]({o['pdf_url']})")

    with e3:
        with st.expander(f"⚙️ In Production by Customer ({len(prod_df)} orders)", expanded=True):
            if not prod_df.empty:
                tbl3 = (prod_df.groupby("Customer")
                        .agg(Orders=("OrderId","count"), Qty=("FabricQty","sum"))
                        .sort_values("Qty", ascending=False).reset_index())
                st.caption(f"Total Qty: **{int(tbl3['Qty'].sum()):,}**")
                st.dataframe(tbl3, use_container_width=True, hide_index=True)

    # ── Today's Dispatches Summary ──────────────────────────
    st.markdown("<br>", unsafe_allow_html=True)
    today_str = date.today().strftime("%Y-%m-%d")
    today_packs = [d.to_dict() for d in
                   db.collection("PackingListRaw").where("Date", "==", today_str).stream()]

    with st.expander(f"🚚 Today's Dispatches  ({len(today_packs)} packing slips)", expanded=True):
        if not today_packs:
            st.info("No dispatches recorded today.")
        else:
            # Group by OrderId — collect unique orders dispatched today
            seen_orders = {}
            for pk in today_packs:
                oid = str(pk.get("OrderId", ""))
                if oid and oid not in seen_orders:
                    seen_orders[oid] = {
                        "OrderId":   oid,
                        "Customer":  pk.get("Customer name", "—"),
                        "Item":      pk.get("Item", "—"),
                        "Slips":     0,
                    }
                if oid:
                    seen_orders[oid]["Slips"] += 1

            disp_rows = sorted(seen_orders.values(), key=lambda r: r["OrderId"])
            st.caption(f"**{len(disp_rows)} orders** dispatched today  •  **{len(today_packs)} packing slips**")

            dc1, dc2, dc3, dc4 = st.columns([2, 3, 3, 1])
            dc1.markdown("**Order ID**")
            dc2.markdown("**Customer**")
            dc3.markdown("**Item**")
            dc4.markdown("**Slips**")
            st.markdown('<hr style="margin:3px 0 8px">', unsafe_allow_html=True)

            for row in disp_rows:
                r1, r2, r3, r4 = st.columns([2, 3, 3, 1])
                r1.markdown(f"**{row['OrderId']}**")
                r2.markdown(row["Customer"])
                r3.markdown(row["Item"])
                r4.markdown(str(row["Slips"]))


# ═════════════════════════════════════════════════════════
#  CUSTOMER MASTER
# ═════════════════════════════════════════════════════════
elif menu == "Customer Master":
    st.markdown('<div class="page-header"><h1>👥 Customer Master</h1></div>', unsafe_allow_html=True)
    action = st.radio("Action", ["Add Customer", "View / Edit / Delete"], horizontal=True)

    if action == "Add Customer":
        name = st.text_input("Customer Name")
        if st.button("Save Customer"):
            if name.strip():
                db.collection("customer_master").document(name.upper()).set({"CustomerName": name.upper()})
                st.success("Customer saved")
            else:
                st.error("Enter a customer name")
    else:
        docs = list(db.collection("customer_master").stream())
        if not docs:
            st.info("No customers yet")
        else:
            cm_search = st.text_input("🔍 Search", placeholder="Type to filter...", key="cm_search")
            filtered  = [d for d in sorted(docs, key=lambda d: d.id)
                         if cm_search.strip().upper() in d.id.upper()] if cm_search.strip() else sorted(docs, key=lambda d: d.id)
            st.caption(f"Showing {len(filtered)} of {len(docs)} customers")
            for doc in filtered:
                with st.expander(doc.id):
                    ec1, ec2, ec3 = st.columns([3, 1, 1])
                    new_name = ec1.text_input("Name", value=doc.id, key=f"cm_edit_{doc.id}", label_visibility="collapsed")
                    if ec2.button("💾 Save", key=f"cm_save_{doc.id}"):
                        new = new_name.strip().upper()
                        if new and new != doc.id:
                            db.collection("customer_master").document(doc.id).delete()
                            db.collection("customer_master").document(new).set({"CustomerName": new})
                            st.success(f"Renamed to {new}")
                            st.rerun()
                    if ec3.button("🗑️ Delete", key=f"cm_del_{doc.id}", type="secondary"):
                        db.collection("customer_master").document(doc.id).delete()
                        st.success(f"{doc.id} deleted")
                        st.rerun()


# ═════════════════════════════════════════════════════════
#  ITEM MASTER
# ═════════════════════════════════════════════════════════
elif menu == "Item Master":
    st.markdown('<div class="page-header"><h1>🧵 Item Master</h1></div>', unsafe_allow_html=True)
    action = st.radio("Action", ["Add Item", "View / Edit / Delete"], horizontal=True)

    if action == "Add Item":
        item_name = st.text_input("Item Name")
        if st.button("Save Item"):
            if item_name.strip():
                db.collection("item_master").document(item_name.upper()).set({"ItemName": item_name.upper()})
                st.success("Item saved")
            else:
                st.error("Enter an item name")
    else:
        docs = list(db.collection("item_master").stream())
        if not docs:
            st.info("No items yet")
        else:
            im_search = st.text_input("🔍 Search", placeholder="Type to filter...", key="im_search")
            filtered  = [d for d in sorted(docs, key=lambda d: d.id)
                         if im_search.strip().upper() in d.id.upper()] if im_search.strip() else sorted(docs, key=lambda d: d.id)
            st.caption(f"Showing {len(filtered)} of {len(docs)} items")
            for doc in filtered:
                with st.expander(doc.id):
                    ic1, ic2, ic3 = st.columns([3, 1, 1])
                    new_item = ic1.text_input("Item", value=doc.id, key=f"im_edit_{doc.id}", label_visibility="collapsed")
                    if ic2.button("💾 Save", key=f"im_save_{doc.id}"):
                        new = new_item.strip().upper()
                        if new and new != doc.id:
                            db.collection("item_master").document(doc.id).delete()
                            db.collection("item_master").document(new).set({"ItemName": new})
                            st.success(f"Renamed to {new}")
                            st.rerun()
                    if ic3.button("🗑️ Delete", key=f"im_del_{doc.id}", type="secondary"):
                        db.collection("item_master").document(doc.id).delete()
                        st.success(f"{doc.id} deleted")
                        st.rerun()


# ═════════════════════════════════════════════════════════
#  PROCESSOR MASTER
# ═════════════════════════════════════════════════════════
elif menu == "Processor Master":
    st.markdown('<div class="page-header"><h1>🏭 Processor Master</h1></div>', unsafe_allow_html=True)
    action = st.radio("Action", ["Add Processor", "View / Edit / Delete"], horizontal=True)

    if action == "Add Processor":
        pc1, pc2 = st.columns(2)
        with pc1:
            processor_name = st.text_input("Processor Name *")
        with pc2:
            processor_gst  = st.text_input("GST No.")
        if st.button("Save Processor"):
            if processor_name.strip():
                db.collection("processor_master").document(processor_name.upper()).set({
                    "ProcessorName": processor_name.upper(),
                    "GstNo":         processor_gst.strip().upper(),
                })
                st.success("Processor saved")
            else:
                st.error("Enter a processor name")
    else:
        docs = list(db.collection("processor_master").stream())
        if not docs:
            st.info("No processors yet")
        else:
            pm_search = st.text_input("🔍 Search", placeholder="Type to filter...", key="pm_search")
            filtered  = [d for d in sorted(docs, key=lambda d: d.id)
                         if pm_search.strip().upper() in d.id.upper()] if pm_search.strip() else sorted(docs, key=lambda d: d.id)
            st.caption(f"Showing {len(filtered)} of {len(docs)} processors")
            for doc in filtered:
                d = doc.to_dict()
                with st.expander(f"{doc.id}  |  GST: {d.get('GstNo','')}"):
                    pr1, pr2, pr3, pr4 = st.columns([2, 2, 1, 1])
                    new_proc = pr1.text_input("Name", value=doc.id,            key=f"pm_name_{doc.id}", label_visibility="collapsed")
                    new_gst  = pr2.text_input("GST",  value=d.get("GstNo",""), key=f"pm_gst_{doc.id}",  label_visibility="collapsed")
                    if pr3.button("💾 Save", key=f"pm_save_{doc.id}"):
                        new = new_proc.strip().upper()
                        gst = new_gst.strip().upper()
                        if new != doc.id:
                            db.collection("processor_master").document(doc.id).delete()
                            db.collection("processor_master").document(new).set({"ProcessorName": new, "GstNo": gst})
                        else:
                            db.collection("processor_master").document(doc.id).update({"GstNo": gst})
                        st.success("Updated")
                        st.rerun()
                    if pr4.button("🗑️ Delete", key=f"pm_del_{doc.id}", type="secondary"):
                        db.collection("processor_master").document(doc.id).delete()
                        st.success(f"{doc.id} deleted")
                        st.rerun()


# ═════════════════════════════════════════════════════════
#  PO MODULE
# ═════════════════════════════════════════════════════════
elif menu == "PO":
    st.markdown('<div class="page-header"><h1>📄 PO Module</h1></div>', unsafe_allow_html=True)

    import streamlit.components.v1 as _po_cv1
    _po_cv1.html("""
    <script>
    (function() {
        function getInputs() {
            return Array.from(window.parent.document.querySelectorAll(
                'input[type="text"]:not([disabled]), input[type="number"]:not([disabled])'
            ));
        }
        function setupEnterNav() {
            getInputs().forEach(function(inp) {
                if (inp._enterBound) return;
                inp._enterBound = true;
                inp.addEventListener('keydown', function(e) {
                    if (e.key !== 'Enter') return;
                    e.preventDefault();
                    var inputs = getInputs();
                    var idx = inputs.indexOf(inp);
                    if (idx >= 0 && idx < inputs.length - 1) {
                        inputs[idx + 1].focus();
                        inputs[idx + 1].select();
                    }
                });
            });
        }
        var obs = new MutationObserver(setupEnterNav);
        obs.observe(window.parent.document.body, { childList: true, subtree: true });
        setupEnterNav();
    })();
    </script>
    """, height=0)

    if "po_result"       not in st.session_state: st.session_state.po_result       = None
    if "po_form_version" not in st.session_state: st.session_state.po_form_version = 0

    fv = st.session_state.po_form_version   # bump after save to clear all fields
    st.info("Order ID will be assigned automatically when you click **Save PO**.")

    customers = get_customer_list()
    items     = get_item_list()

    col1, col2 = st.columns(2)

    with col1:
        category = st.selectbox("Category", ["STRIPE", "PLAIN"],
                                 index=None, placeholder="Select category...", key=f"po_cat_{fv}")

        if customers:
            customer_name = st.selectbox("Customer", customers,
                                          index=None, placeholder="Select customer...", key=f"po_cust_{fv}")
        else:
            st.warning("Add a customer first")
            customer_name = None

        if items:
            item = st.selectbox("Item", items,
                                index=None, placeholder="Select item...", key=f"po_item_{fv}")
        else:
            st.warning("Add an item first")
            item = None

        date_value     = st.date_input("Date", value=date.today(), format="DD/MM/YYYY", key=f"po_date_{fv}")
        date_str       = date_value.strftime("%Y-%m-%d")
        gsm            = st.number_input("GSM",          min_value=0, value=None, placeholder="0", key=f"po_gsm_{fv}")
        fabric_qnty    = st.number_input("Fabric Qty",   min_value=0, value=None, placeholder="0", key=f"po_fqty_{fv}")
        accessory_qnty = st.number_input("Accessory Qty",min_value=0, value=None, placeholder="0", key=f"po_aqty_{fv}")

    with col2:
        fabric_price          = st.number_input("Fabric Price",    min_value=0, value=None, placeholder="0",                          key=f"po_fprice_{fv}")
        accessory_price       = st.number_input("Accessory Price", min_value=0, value=None, placeholder="0",                          key=f"po_aprice_{fv}")
        colours_instructions  = st.text_area("Colours Instructions",                                                                   key=f"po_colours_{fv}")
        accessory_desc        = st.text_area("Accessory Description", placeholder="e.g. 500 buttons, 200 labels...",                  key=f"po_acc_{fv}")
        customer_po_no        = st.text_input("Customer PO No",                                                                        key=f"po_custpo_{fv}")
        uploaded_image        = st.file_uploader(
            "Product Image", type=["jpg", "jpeg", "png", "webp"],                                                                      key=f"po_img_{fv}"
        )

    image_bytes = None
    if uploaded_image:
        image_bytes = uploaded_image.read()
        st.image(io.BytesIO(image_bytes), width=200)

    if st.button("Save PO", type="primary"):
        if not category or not customer_name or not item:
            st.error("Please select Category, Customer and Item")
        else:
            # Assign OrderId atomically at submit — never pre-assigned
            order_id       = get_next_order_id()
            image_drive_id = ""
            image_url      = ""
            pdf_url        = ""
            pdf_bytes      = None

            po_dict = {
                "OrderId":              order_id,
                "Date":                 date_str,
                "Customer name":        customer_name,
                "customerpono":         customer_po_no,
                "Item":                 item,
                "Category":             category,
                "gsm":                  gsm or 0,
                "facricqnty":           fabric_qnty or 0,
                "fabricprice":          fabric_price or 0,
                "accessoryqnty":        accessory_qnty or 0,
                "accessoryprice":       accessory_price or 0,
                "coloursinstructions":  colours_instructions,
                "accessory":            accessory_desc,
            }

            with st.spinner("Uploading to Firebase Storage & generating PDF..."):
                try:
                    if image_bytes:
                        ext       = uploaded_image.name.rsplit(".", 1)[-1]
                        image_url = upload_to_firebase_storage(
                            image_bytes,
                            f"po_images/PO_{order_id}_image.{ext}",
                            uploaded_image.type,
                        )

                    pdf_bytes = build_po_pdf(po_dict, image_bytes)
                    pdf_url   = upload_to_firebase_storage(
                        pdf_bytes,
                        f"po_pdfs/PO_{order_id}.pdf",
                        "application/pdf",
                    )

                except Exception as e:
                    st.warning(f"Firebase Storage error: {e}. PO saved without file links.")
                    if pdf_bytes is None:
                        pdf_bytes = build_po_pdf(po_dict, image_bytes)

            db.collection("po").document(order_id).set({
                **po_dict,
                "image":          image_url,
                "image_drive_id": image_drive_id,
                "pdf_url":        pdf_url,
            })

            st.session_state.po_result = {
                "order_id":  order_id,
                "pdf_bytes": pdf_bytes,
                "pdf_url":   pdf_url,
                "image_url": image_url,
            }
            st.session_state.po_form_version += 1
            st.rerun()

    # Show result card (persists across re-runs)
    if st.session_state.po_result:
        res = st.session_state.po_result
        st.success(f"✅ PO **{res['order_id']}** saved successfully!")
        link_col1, link_col2, link_col3 = st.columns(3)
        if res.get("pdf_url"):
            link_col1.markdown(f"[📄 Open PO PDF in Drive]({res['pdf_url']})")
        if res.get("image_url"):
            link_col2.markdown(f"[🖼️ View Image in Drive]({res['image_url']})")
        if res.get("pdf_bytes"):
            link_col3.download_button(
                "⬇️ Download PO PDF",
                res["pdf_bytes"],
                f"PO_{res['order_id']}.pdf",
                "application/pdf",
                key="po_download",
            )


# ═════════════════════════════════════════════════════════
#  SHOOT ORDER
# ═════════════════════════════════════════════════════════
elif menu == "Shoot Order":
    st.markdown('<div class="page-header"><h1>🎯 Shoot Order</h1></div>', unsafe_allow_html=True)

    if "shoot_result" not in st.session_state:
        st.session_state.shoot_result = None

    c1, c2 = st.columns([1, 1])
    with c1:
        order_id_input = st.text_input("Order ID")
    with c2:
        shoot_date     = st.date_input("Shoot Date", value=date.today(), format="DD/MM/YYYY")

    shoot_date_str = shoot_date.strftime("%Y-%m-%d")
    po_data        = None

    if order_id_input.strip():
        po_doc = db.collection("po").document(order_id_input.strip()).get()
        if po_doc.exists:
            po_data = po_doc.to_dict()
            st.success("✅ PO found")
            st.divider()

            fc1, fc2 = st.columns(2)
            with fc1:
                st.text_input("Customer",       value=po_data.get("Customer name", ""),     disabled=True)
                st.text_input("Item",           value=po_data.get("Item", ""),               disabled=True)
                st.text_input("Category",       value=po_data.get("Category", ""),           disabled=True)
                st.text_input("Fabric Qty",     value=str(po_data.get("facricqnty", "")),    disabled=True)
            with fc2:
                st.text_input("GSM",                   value=str(po_data.get("gsm", "")),            disabled=True)
                st.text_input("Accessory Qty",         value=str(po_data.get("accessoryqnty", "")),  disabled=True)
                st.text_area("Colours",                value=po_data.get("coloursinstructions", ""),  disabled=True)
                st.text_area("Accessory Description",  value=po_data.get("accessory", ""),            disabled=True)
        else:
            st.error("PO not found")

    if po_data and st.button("Save Shoot Order & Generate PDF", type="primary"):
        shoot_data = {
            "OrderId":             order_id_input.strip(),
            "Date":                shoot_date_str,
            "Category":            po_data.get("Category", ""),
            "Customer name":       po_data.get("Customer name", ""),
            "Item":                po_data.get("Item", ""),
            "gsm":                 po_data.get("gsm", ""),
            "coloursinstructions": po_data.get("coloursinstructions", ""),
            "facricqnty":          po_data.get("facricqnty", ""),
            "accessoryqnty":       po_data.get("accessoryqnty", ""),
            "accessory":           po_data.get("accessory") or "",
            "image":               po_data.get("image", ""),
            "image_drive_id":      po_data.get("image_drive_id", ""),
        }

        pdf_url   = ""
        pdf_bytes = None
        pdf_name  = f"ShootOrder_{order_id_input.strip()}.pdf"

        with st.spinner("Generating Shoot Order PDF..."):
            # Step 1: fetch image — Drive ID takes priority, then Firebase Storage URL
            img_bytes = None
            image_url = po_data.get("image", "")
            drive_id  = po_data.get("image_drive_id", "")
            if drive_id:
                # Old POs: image in Google Drive — must use service account download
                try:
                    img_bytes = download_from_drive(drive_id)
                except Exception as e:
                    st.warning(f"Could not fetch image from Drive: {e}")
            elif image_url and ("storage.googleapis.com" in image_url or
                                "firebasestorage.googleapis.com" in image_url):
                # New POs: image in Firebase Storage — direct download
                try:
                    import urllib.request as _ur
                    with _ur.urlopen(image_url) as _resp:
                        img_bytes = _resp.read()
                except Exception as e:
                    st.warning(f"Could not fetch image from Firebase Storage: {e}")
            else:
                st.info("No image on record for this PO — PDF will be generated without image.")

            # Step 2: generate PDF
            pdf_bytes = build_shoot_order_pdf(shoot_data, img_bytes)

            # Step 3: upload PDF to Firebase Storage
            try:
                pdf_url = upload_to_firebase_storage(
                    pdf_bytes,
                    f"shoot_pdfs/{pdf_name}",
                    "application/pdf",
                )
                shoot_data["pdf_url"] = pdf_url
            except Exception as e:
                st.warning(f"Firebase Storage upload failed: {e}. Use the download button below.")

        db.collection("shoot_order").add(shoot_data)

        st.session_state.shoot_result = {
            "order_id":  order_id_input.strip(),
            "date":      shoot_date_str,
            "pdf_bytes": pdf_bytes,
            "pdf_url":   pdf_url,
            "pdf_name":  pdf_name,
        }
        st.rerun()

    # Show result card
    if st.session_state.shoot_result:
        res = st.session_state.shoot_result
        st.success(f"✅ Shoot Order for PO **{res['order_id']}** saved!")
        sc1, sc2 = st.columns(2)
        if res.get("pdf_url"):
            sc1.markdown(f"[📄 Open Shoot Order PDF in Drive]({res['pdf_url']})")
        if res.get("pdf_bytes"):
            sc2.download_button(
                "⬇️ Download Shoot Order PDF",
                res["pdf_bytes"],
                res["pdf_name"],
                "application/pdf",
                key="shoot_download",
            )


# ═════════════════════════════════════════════════════════
#  PLACEHOLDERS
# ═════════════════════════════════════════════════════════
elif menu == "Process Out":
    st.markdown('<div class="page-header"><h1>🚚 Process Out</h1></div>', unsafe_allow_html=True)

    import re
    import streamlit.components.v1 as components

    components.html("""
    <script>
    (function() {
        function getInputs() {
            return Array.from(window.parent.document.querySelectorAll(
                'input[type="text"]:not([disabled]), input[type="number"]:not([disabled])'
            ));
        }

        function setupEnterNav() {
            getInputs().forEach(function(inp) {
                if (inp._enterBound) return;
                inp._enterBound = true;
                inp.addEventListener('keydown', function(e) {
                    if (e.key !== 'Enter') return;
                    e.preventDefault();
                    // Re-query live DOM so index is always current
                    var inputs = getInputs();
                    var idx = inputs.indexOf(inp);
                    if (idx >= 0 && idx < inputs.length - 1) {
                        inputs[idx + 1].focus();
                        inputs[idx + 1].select();
                    }
                });
            });
        }

        var observer = new MutationObserver(setupEnterNav);
        observer.observe(window.parent.document.body, { childList: true, subtree: true });
        setupEnterNav();
    })();
    </script>
    """, height=0)

    def get_next_proc_out_challan_no() -> str:
        max_no = 100
        for doc in db.collection("process_out").stream():
            val = str(doc.to_dict().get("ChallanNo", "")).strip()
            if val.isdigit():
                max_no = max(max_no, int(val))
        return str(max_no + 1)

    def extract_order_id(lot_no: str) -> str:
        m = re.match(r"^(\d+)", lot_no.strip().upper())
        return m.group(1) if m else ""

    def build_challan_html(header: dict, lots: list) -> str:
        """Build a printable HTML challan — no PDF needed."""
        from datetime import datetime as _dt
        raw_date = header.get("Date", "")
        try:
            disp_date = _dt.strptime(raw_date, "%Y-%m-%d").strftime("%d/%m/%Y")
        except Exception:
            disp_date = raw_date

        lot_rows_html = ""
        total_rolls = 0
        total_qty   = 0.0
        for i, lot in enumerate(lots, 1):
            bg = "" if i % 2 == 0 else "background:#f9f9f9;"
            try: total_rolls += int(lot.get("Roll", 0) or 0)
            except Exception: pass
            try: total_qty += float(lot.get("Qnty", 0) or 0)
            except Exception: pass
            lot_rows_html += f"""
            <tr style="{bg}">
              <td>{i}</td>
              <td>{lot.get("LotNo","")}</td>
              <td>{lot.get("OrderId","")}</td>
              <td>{lot.get("Item","")}</td>
              <td>{lot.get("Colour","")}</td>
              <td style="text-align:center">{lot.get("Roll","")}</td>
              <td style="text-align:center">{lot.get("Qnty","")}</td>
              <td>{lot.get("Process","")}</td>
              <td style="text-align:center">{lot.get("DiaGsm","")}</td>
            </tr>"""

        total_qty_str = str(round(total_qty, 2))
        grand_total_row = f"""
            <tr style="background:#dce6f7;font-weight:bold;border-top:2px solid #1a3c6e;">
              <td colspan="5" style="text-align:right;padding:5px 6px;">GRAND TOTAL</td>
              <td style="text-align:center;padding:5px 4px;">{total_rolls}</td>
              <td style="text-align:center;padding:5px 4px;">{total_qty_str}</td>
              <td colspan="2"></td>
            </tr>"""

        return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: Arial, sans-serif; font-size: 10pt; padding: 10mm; color: #111; }}
  .print-btn {{
    background: #1a3c6e; color: white; border: none; padding: 8px 24px;
    font-size: 11pt; cursor: pointer; border-radius: 4px; margin-bottom: 12px;
    display: block;
  }}
  @media print {{
    .print-btn {{ display: none; }}
    body {{ padding: 5mm; }}
  }}
  .lh-box {{ border: 1px solid #333; padding: 5px 10px; display: flex;
             justify-content: space-between; align-items: flex-start; margin-bottom: 4px; }}
  .co-name {{ text-align: center; font-size: 14pt; font-weight: bold; margin: 6px 0 2px; }}
  .co-addr {{ text-align: center; font-size: 10pt; }}
  .ch-title {{ text-align: center; font-size: 12pt; font-weight: bold;
               text-decoration: underline; margin: 8px 0 10px; }}
  .hdr-table {{ width: 100%; border-collapse: collapse; margin-bottom: 10px; }}
  .hdr-table td {{ border: 0.5px solid #999; padding: 4px 6px; font-size: 9.5pt; }}
  .hdr-table td.lbl {{ background: #dce6f7; font-weight: bold; width: 15%; }}
  .lots-table {{ width: 100%; border-collapse: collapse; font-size: 8.5pt; }}
  .lots-table th {{ background: #1a3c6e; color: white; padding: 5px 4px;
                    text-align: left; border: 0.5px solid #666; }}
  .lots-table td {{ border: 0.5px solid #bbb; padding: 4px; vertical-align: top; }}
</style>
</head>
<body>
<button class="print-btn" onclick="window.print()">🖨️ Print Challan</button>

<div class="lh-box">
  <div>
    <div>GSTIN No : &nbsp;03AAECL9162H1Z1</div>
    <div>PAN No &nbsp;&nbsp;&nbsp;: &nbsp;AAECL9162H</div>
  </div>
  <div>Phone : 98766-82001</div>
</div>

<div class="co-name">LOVELY KNITFAB PVT LTD</div>
<div class="co-addr">HB NO.85, VILL. KASABAD</div>
<div class="co-addr">LUDHIANA</div>

<div class="ch-title">JOB WORK CHALLAN (OUTWARD)</div>

<table class="hdr-table">
  <tr>
    <td class="lbl">Challan No</td><td>{header.get("ChallanNo","")}</td>
    <td class="lbl">Date</td><td>{disp_date}</td>
  </tr>
  <tr>
    <td class="lbl">Party</td><td>{header.get("PartyName","")}</td>
    <td class="lbl">GST No</td><td>{header.get("GstNo","—")}</td>
  </tr>
  <tr>
    <td class="lbl">Vehicle No</td><td>{header.get("VehicleNo","")}</td>
    <td class="lbl"></td><td></td>
  </tr>
</table>

<table class="lots-table">
  <thead>
    <tr>
      <th>#</th><th>Lot No</th><th>Order ID</th><th>Item</th><th>Colour</th>
      <th>Roll</th><th>Qty</th><th>Process</th><th>Dia/GSM</th>
    </tr>
  </thead>
  <tbody>
    {lot_rows_html}
    {grand_total_row}
  </tbody>
</table>
</body>
</html>"""

    # ── Session state init ──
    if "proc_out_result"   not in st.session_state: st.session_state.proc_out_result   = None
    if "proc_out_challan_no" not in st.session_state: st.session_state.proc_out_challan_no = get_next_proc_out_challan_no()
    if "proc_out_lots"     not in st.session_state: st.session_state.proc_out_lots     = []
    if "proc_out_item_val" not in st.session_state: st.session_state.proc_out_item_val = ""
    if "proc_out_cust_val" not in st.session_state: st.session_state.proc_out_cust_val = ""
    if "proc_out_last_lot" not in st.session_state: st.session_state.proc_out_last_lot = ""

    tab_add, tab_view, tab_print = st.tabs(["Add Challan", "View Records", "🖨️ Print Challan"])

    with tab_add:
        st.success(f"Challan No: **{st.session_state.proc_out_challan_no}**")

        # ── Challan header ──
        st.markdown("#### Challan Details")
        hc1, hc2, hc3 = st.columns(3)
        with hc1:
            po_date     = st.date_input("Date", value=date.today(), format="DD/MM/YYYY", key="po_date_out")
            po_date_str = po_date.strftime("%Y-%m-%d")
        with hc2:
            processors = get_processor_list()
            if processors:
                party = st.selectbox("Processor / Party", processors)
            else:
                st.warning("Add a processor in Processor Master first")
                party = ""
        with hc3:
            vehicle = st.text_input("Vehicle No")

        st.divider()

        # ── Add lot form ──
        st.markdown("#### Add Lot")
        lc1, lc2 = st.columns(2)

        with lc1:
            lot_no_input = st.text_input("Lot No (e.g. 1001A or 1122-D)", key="lot_no_input")

            po_lot_data      = None
            derived_order_id = ""
            if lot_no_input.strip():
                derived_order_id = extract_order_id(lot_no_input)
                if derived_order_id:
                    po_doc = db.collection("po").document(derived_order_id).get()
                    if po_doc.exists:
                        po_lot_data = po_doc.to_dict()
                    else:
                        st.warning(f"No PO found for Order ID {derived_order_id}")
                else:
                    st.error("Cannot derive Order ID from Lot No")

            st.text_input("Order ID", value=derived_order_id, disabled=True, key="oid_derived")

            # Auto-fill Customer & Item when Lot No changes, both stay editable
            if lot_no_input.strip() != st.session_state.proc_out_last_lot:
                st.session_state.proc_out_last_lot = lot_no_input.strip()
                st.session_state.proc_out_cust_val = po_lot_data.get("Customer name", "") if po_lot_data else ""
                st.session_state.proc_out_item_val = po_lot_data.get("Item", "")          if po_lot_data else ""
            st.text_input("Customer", key="proc_out_cust_val")
            st.text_input("Item",     key="proc_out_item_val")

        with lc2:
            colour  = st.text_input("Colour",                key="lot_colour")
            roll    = st.number_input("Roll", min_value=0,   value=None, placeholder="0",    key="lot_roll")
            qty     = st.number_input("Qty",  min_value=0.0, value=None, placeholder="0.00", step=0.5, key="lot_qty")
            process = st.text_input("Process",               key="lot_process")
            dia_gsm = st.text_input("Dia / GSM (optional)",  key="lot_diagsm")

        if st.button("➕ Add Lot to Challan"):
            if not lot_no_input.strip() or not derived_order_id:
                st.error("Enter a valid Lot No")
            else:
                st.session_state.proc_out_lots.append({
                    "LotNo":         lot_no_input.strip().upper(),
                    "OrderId":       derived_order_id,
                    "Customer name": st.session_state.proc_out_cust_val.strip(),
                    "Item":          st.session_state.proc_out_item_val.strip(),
                    "Colour":        colour.strip(),
                    "Roll":          int(roll or 0),
                    "Qnty":          float(qty or 0),
                    "Process":       process.strip(),
                    "DiaGsm":        dia_gsm.strip(),
                })
                st.rerun()

        # ── Lots added so far ──
        if st.session_state.proc_out_lots:
            st.markdown("#### Lots in this Challan")
            lots_df = pd.DataFrame(st.session_state.proc_out_lots)
            st.dataframe(lots_df, use_container_width=True)

            # Remove lot buttons
            remove_cols = st.columns(len(st.session_state.proc_out_lots))
            for i, lot in enumerate(st.session_state.proc_out_lots):
                if remove_cols[i].button(f"Remove {lot['LotNo']}", key=f"rm_{i}"):
                    st.session_state.proc_out_lots.pop(i)
                    st.rerun()

            st.divider()

            # ── Save Challan ──
            if st.button("💾 Save Challan & Generate PDF", type="primary"):
                if not party:
                    st.error("Select a processor")
                else:
                    challan_no = st.session_state.proc_out_challan_no
                    # Fetch GST No from processor master
                    proc_doc = db.collection("processor_master").document(party).get()
                    gst_no   = proc_doc.to_dict().get("GstNo", "") if proc_doc.exists else ""
                    header = {
                        "ChallanNo": challan_no,
                        "Date":      po_date_str,
                        "PartyName": party,
                        "GstNo":     gst_no,
                        "VehicleNo": vehicle.strip(),
                    }
                    with st.spinner("Saving..."):
                        # Save lots to Firestore
                        for lot in st.session_state.proc_out_lots:
                            doc_id = f"{challan_no}_{lot['LotNo']}"
                            db.collection("process_out").document(doc_id).set({
                                **header,
                                **lot,
                            })
                        # Build HTML challan for on-screen display
                        challan_html = build_challan_html(header, st.session_state.proc_out_lots)

                    st.session_state.proc_out_result = {
                        "challan_no":  challan_no,
                        "challan_html": challan_html,
                    }
                    st.session_state.proc_out_challan_no = str(int(challan_no) + 1)
                    st.session_state.proc_out_lots     = []
                    st.session_state.proc_out_cust_val = ""
                    st.session_state.proc_out_last_lot = ""
                    st.rerun()
        else:
            st.info("No lots added yet — use the form above to add lots to this challan.")

        # ── Result card ──
        if st.session_state.proc_out_result:
            res = st.session_state.proc_out_result
            st.success(f"✅ Challan **{res['challan_no']}** saved — click Print inside the challan below")
            if res.get("challan_html"):
                n_lots   = len(st.session_state.get("proc_out_lots", [])) or 10
                ch_height = max(650, 480 + n_lots * 28)
                import streamlit.components.v1 as _cv1
                _cv1.html(res["challan_html"], height=ch_height, scrolling=True)

    with tab_view:
        rows = [{**doc.to_dict(), "Date": _fmt_date(doc.to_dict().get("Date",""))} for doc in db.collection("process_out").stream()]
        if rows:
            want = ["ChallanNo", "Date", "PartyName", "LotNo", "OrderId", "Item", "Colour", "Roll", "Qnty", "Process"]
            df = pd.DataFrame(rows)
            cols = [c for c in want if c in df.columns]
            st.dataframe(df[cols].sort_values("ChallanNo", ascending=False), use_container_width=True)
        else:
            st.info("No Process Out records yet")

    with tab_print:
        st.markdown("#### 🖨️ Print / Reprint Challan")
        st.caption("Enter a challan number to regenerate and download its PDF from saved records.")
        pr_col1, pr_col2 = st.columns([2, 1])
        with pr_col1:
            print_challan_no = st.text_input("Challan Number", placeholder="e.g. 1001", key="print_ch_no")
        with pr_col2:
            st.markdown("<br>", unsafe_allow_html=True)
            print_btn = st.button("Generate PDF", type="primary", key="print_ch_btn")

        if print_btn and print_challan_no.strip():
            ch = print_challan_no.strip()
            with st.spinner(f"Fetching challan {ch}..."):
                ch_docs = [d.to_dict() for d in db.collection("process_out")
                           .where("ChallanNo", "==", ch).stream()]
            if not ch_docs:
                st.error(f"No records found for Challan No **{ch}**")
            else:
                # Rebuild header from first doc
                first = ch_docs[0]
                party_name = first.get("PartyName", "")
                # Refresh GST No from master
                p_doc  = db.collection("processor_master").document(party_name).get()
                gst_no = p_doc.to_dict().get("GstNo", "") if p_doc.exists else first.get("GstNo", "")
                reprint_header = {
                    "ChallanNo": first.get("ChallanNo", ch),
                    "Date":      first.get("Date", ""),
                    "PartyName": party_name,
                    "GstNo":     gst_no,
                    "VehicleNo": first.get("VehicleNo", ""),
                }
                # Collect lots sorted by LotNo
                lots_sorted = sorted(ch_docs, key=lambda d: str(d.get("LotNo", "")))
                lot_keys    = ["LotNo","OrderId","Item","Colour","Roll","Qnty","Process","DiaGsm"]
                reprint_lots = [{k: d.get(k, "") for k in lot_keys} for d in lots_sorted]

                challan_html = build_challan_html(reprint_header, reprint_lots)
                st.success(f"Challan **{ch}** — {len(reprint_lots)} lot(s)  |  Party: **{party_name}**")
                import streamlit.components.v1 as _cv1r
                ch_height = max(650, 480 + len(reprint_lots) * 28)
                _cv1r.html(challan_html, height=ch_height, scrolling=True)

elif menu == "Process Inward":
    st.markdown('<div class="page-header"><h1>📥 Process Inward</h1></div>', unsafe_allow_html=True)

    import streamlit.components.v1 as components

    components.html("""
    <script>
    (function() {
        function getInputs() {
            return Array.from(window.parent.document.querySelectorAll(
                'input[type="text"]:not([disabled]), input[type="number"]:not([disabled])'
            ));
        }
        var nextFocusIdx = -1;
        function setupEnterNav() {
            getInputs().forEach(function(inp, i) {
                if (inp._enterBound) return;
                inp._enterBound = true;
                inp.addEventListener('keydown', function(e) {
                    if (e.key === 'Enter') { nextFocusIdx = i + 1; }
                });
            });
        }
        var observer = new MutationObserver(function() {
            setupEnterNav();
            if (nextFocusIdx >= 0) {
                var inputs = getInputs();
                if (inputs[nextFocusIdx]) inputs[nextFocusIdx].focus();
                nextFocusIdx = -1;
            }
        });
        observer.observe(window.parent.document.body, { childList: true, subtree: true });
        setupEnterNav();
    })();
    </script>
    """, height=0)

    def get_next_inward_challan_no() -> str:
        max_no = 100
        for doc in db.collection("process_inward").stream():
            val = str(doc.to_dict().get("ChallanNo", "")).strip()
            if val.isdigit():
                max_no = max(max_no, int(val))
        return str(max_no + 1)

    def build_process_inward_pdf(header: dict, lots: list) -> bytes:
        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf, pagesize=A4,
            topMargin=1.5*cm, bottomMargin=1.5*cm,
            leftMargin=1.5*cm, rightMargin=1.5*cm,
        )
        styles = getSampleStyleSheet()
        elements = []
        _pdf_header(elements, styles, "PROCESS INWARD CHALLAN")

        h_rows = [
            ["Challan No", str(header.get("ChallanNo", "")), "Date",       str(header.get("Date", ""))],
            ["Party",      str(header.get("PartyName", "")), "Vehicle No", str(header.get("VehicleNo", ""))],
        ]
        ht = Table(h_rows, colWidths=_TABLE_COL_WIDTHS)
        ht.setStyle(_base_table_style())
        elements.append(ht)
        elements.append(Spacer(1, 0.4*cm))

        lot_header = ["#", "Lot No", "Colour", "Process", "Sent\nRoll", "Rcvd\nRoll", "Sent\nQty", "Rcvd\nQty", "Short\nQty", "Short\n%", "Rate", "Amount", "Remarks"]
        lot_rows   = [lot_header]
        for i, lot in enumerate(lots, 1):
            lot_rows.append([
                str(i),
                str(lot.get("LotNo", "")),
                str(lot.get("Colour", "")),
                str(lot.get("Process", "")),
                str(lot.get("SentRoll", "")),
                str(lot.get("ReceivedRoll", "")),
                str(lot.get("SentQty", "")),
                str(lot.get("ReceivedQty", "")),
                str(lot.get("ShortQty", "")),
                str(lot.get("ShortPct", "")) + ("%" if lot.get("ShortPct", "") != "" else ""),
                str(lot.get("Rate", "")),
                str(lot.get("Amount", "")),
                str(lot.get("Remarks", "")),
            ])

        col_w = [0.7*cm, 1.8*cm, 1.8*cm, 1.8*cm, 1.3*cm, 1.3*cm, 1.3*cm, 1.3*cm, 1.3*cm, 1.3*cm, 1.3*cm, 1.8*cm, 2.5*cm]
        lt = Table(lot_rows, colWidths=col_w, repeatRows=1)
        lt.setStyle(TableStyle([
            ("BACKGROUND",     (0, 0), (-1, 0),  colors.HexColor("#1a3c6e")),
            ("TEXTCOLOR",      (0, 0), (-1, 0),  colors.white),
            ("FONTNAME",       (0, 0), (-1, 0),  "Helvetica-Bold"),
            ("FONTNAME",       (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE",       (0, 0), (-1, -1), 8),
            ("GRID",           (0, 0), (-1, -1), 0.5, colors.grey),
            ("VALIGN",         (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN",          (4, 0), (-1, -1), "CENTER"),
            ("PADDING",        (0, 0), (-1, -1), 4),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f5f5f5")]),
        ]))
        elements.append(lt)
        doc.build(elements)
        return buf.getvalue()

    # ── Session state ──
    if "proc_in_result"     not in st.session_state: st.session_state.proc_in_result     = None
    if "proc_in_challan_no" not in st.session_state: st.session_state.proc_in_challan_no = get_next_inward_challan_no()
    if "proc_in_lots"       not in st.session_state: st.session_state.proc_in_lots       = []

    tab_add, tab_view = st.tabs(["Add Challan", "View Records"])

    with tab_add:
        st.success(f"Challan No: **{st.session_state.proc_in_challan_no}**")

        # ── Challan header ──
        st.markdown("#### Challan Details")
        hc1, hc2, hc3 = st.columns(3)
        with hc1:
            in_date     = st.date_input("Date", value=date.today(), format="DD/MM/YYYY", key="in_date")
            in_date_str = in_date.strftime("%Y-%m-%d")
        with hc2:
            processors = get_processor_list()
            if processors:
                in_party = st.selectbox("Processor / Party", processors, key="in_party")
            else:
                st.warning("Add a processor in Processor Master first")
                in_party = ""
        with hc3:
            in_vehicle = st.text_input("Vehicle No", key="in_vehicle")

        st.divider()

        # ── Add lot form ──
        st.markdown("#### Add Lot")

        # Fetch process_out lots for selected party
        available_lots = []
        if in_party:
            out_docs = db.collection("process_out").where("PartyName", "==", in_party).stream()
            available_lots = [doc.to_dict() for doc in out_docs]

        if not available_lots:
            st.info("No Process Out lots found for this processor.")
        else:
            lot_options = [f"{l['LotNo']}  |  Order: {l['OrderId']}  |  {l.get('Colour','')}  |  Sent Qty: {l.get('Qnty','')}" for l in available_lots]
            selected_idx = st.selectbox("Select Lot (from Process Out)", range(len(lot_options)), format_func=lambda i: lot_options[i], key="in_lot_select")
            selected_lot = available_lots[selected_idx]

            st.divider()

            # Auto-filled sent details (no key= so value= always reflects selected lot)
            ac1, ac2 = st.columns(2)
            with ac1:
                st.text_input("Lot No",    value=selected_lot.get("LotNo", ""),          disabled=True)
                st.text_input("Order ID",  value=selected_lot.get("OrderId", ""),         disabled=True)
                st.text_input("Customer",  value=selected_lot.get("Customer name", ""),   disabled=True)
                st.text_input("Colour",    value=selected_lot.get("Colour", ""),          disabled=True)
                st.text_input("Process",   value=selected_lot.get("Process", ""),         disabled=True)
            with ac2:
                st.text_input("Sent Roll", value=str(selected_lot.get("Roll", "")),       disabled=True)
                st.text_input("Sent Qty",  value=str(selected_lot.get("Qnty", "")),       disabled=True)

                recv_roll = st.number_input("Received Roll", min_value=0,   value=None, placeholder="0",    key="in_recv_roll")
                recv_qty  = st.number_input("Received Qty",  min_value=0.0, value=None, placeholder="0.00", step=0.5, key="in_recv_qty")
                rate      = st.number_input("Rate (optional)", min_value=0.0, value=None, placeholder="0.00", step=0.5, key="in_rate")
                remarks   = st.text_input("Remarks (optional)", key="in_remarks")

                # Auto-calculated
                sent_qty_val = float(selected_lot.get("Qnty", 0) or 0)
                recv_qty_val = float(recv_qty or 0)
                rate_val     = float(rate or 0)
                short_qty    = round(sent_qty_val - recv_qty_val, 3)
                short_pct    = round((short_qty / sent_qty_val) * 100, 2) if sent_qty_val > 0 else 0.0
                amount       = round(recv_qty_val * rate_val, 2)

                # Alert: received > sent
                if recv_qty_val > sent_qty_val:
                    st.error(f"⚠️ Received Qty ({recv_qty_val}) is MORE than Sent Qty ({sent_qty_val}). Please recheck.")

                # Shortage display
                if recv_qty_val > 0 and short_qty > 0:
                    st.warning(f"📉 Shortage: **{short_qty} kg** &nbsp;|&nbsp; **{short_pct}%** of sent quantity")
                elif recv_qty_val > 0 and short_qty == 0:
                    st.success("✅ Full quantity received — no shortage")

                sc1, sc2 = st.columns(2)
                sc1.text_input("Short Qty", value=str(short_qty),  disabled=True)
                sc2.text_input("Short %",   value=f"{short_pct}%", disabled=True)
                st.text_input("Amount",     value=str(amount),     disabled=True)

            if st.button("➕ Add Lot to Challan", key="in_add_lot"):
                existing = [l["LotNo"] for l in st.session_state.proc_in_lots]
                if selected_lot["LotNo"] in existing:
                    st.error("This lot is already added to this challan")
                elif recv_qty_val > sent_qty_val:
                    st.error(f"⚠️ Cannot add — Received Qty ({recv_qty_val}) exceeds Sent Qty ({sent_qty_val}). Please correct before adding.")
                else:
                    st.session_state.proc_in_lots.append({
                        "LotNo":         selected_lot.get("LotNo", ""),
                        "OrderId":       selected_lot.get("OrderId", ""),
                        "Customer name": selected_lot.get("Customer name", ""),
                        "Item":          selected_lot.get("Item", ""),
                        "Colour":        selected_lot.get("Colour", ""),
                        "Process":       selected_lot.get("Process", ""),
                        "SentRoll":      int(selected_lot.get("Roll", 0) or 0),
                        "SentQty":       float(selected_lot.get("Qnty", 0) or 0),
                        "ReceivedRoll":  int(recv_roll or 0),
                        "ReceivedQty":   float(recv_qty or 0),
                        "ShortQty":      short_qty,
                        "ShortPct":      short_pct,
                        "Rate":          rate_val,
                        "Amount":        amount,
                        "Remarks":       remarks.strip(),
                    })
                    st.rerun()

        # ── Lots added so far ──
        if st.session_state.proc_in_lots:
            st.markdown("#### Lots in this Challan")
            lots_df = pd.DataFrame(st.session_state.proc_in_lots)[
                ["LotNo", "OrderId", "Colour", "Process", "SentRoll", "ReceivedRoll", "SentQty", "ReceivedQty", "ShortQty", "Rate", "Amount", "Remarks"]
            ]
            st.dataframe(lots_df, use_container_width=True)

            rem_cols = st.columns(len(st.session_state.proc_in_lots))
            for i, lot in enumerate(st.session_state.proc_in_lots):
                if rem_cols[i].button(f"Remove {lot['LotNo']}", key=f"in_rm_{i}"):
                    st.session_state.proc_in_lots.pop(i)
                    st.rerun()

            st.divider()

            if st.button("💾 Save Challan & Generate PDF", type="primary", key="in_save"):
                if not in_party:
                    st.error("Select a processor")
                else:
                    challan_no = st.session_state.proc_in_challan_no
                    header = {
                        "ChallanNo": challan_no,
                        "Date":      in_date_str,
                        "PartyName": in_party,
                        "VehicleNo": in_vehicle.strip(),
                    }
                    pdf_url   = ""
                    pdf_bytes = None
                    pdf_name  = f"ProcessInward_{challan_no}.pdf"

                    with st.spinner("Saving..."):
                        try:
                            pdf_bytes = build_process_inward_pdf(header, st.session_state.proc_in_lots)
                            pdf_res   = upload_to_drive(pdf_bytes, pdf_name, "application/pdf",
                                                        folder_id=PROC_IN_PDF_FOLDER)
                            pdf_url   = pdf_res["url"]
                        except Exception as e:
                            st.warning(f"Drive error: {e}")
                            pdf_bytes = build_process_inward_pdf(header, st.session_state.proc_in_lots)

                        for lot in st.session_state.proc_in_lots:
                            doc_id = f"{challan_no}_{lot['LotNo']}"
                            db.collection("process_inward").document(doc_id).set({
                                **header,
                                **lot,
                                "pdf_url": pdf_url,
                            })

                    st.session_state.proc_in_result     = {"challan_no": challan_no, "pdf_bytes": pdf_bytes, "pdf_url": pdf_url, "pdf_name": pdf_name}
                    st.session_state.proc_in_challan_no = str(int(challan_no) + 1)
                    st.session_state.proc_in_lots       = []
                    st.rerun()
        else:
            if available_lots:
                st.info("No lots added yet — select a lot above and click ➕ Add Lot.")

        if st.session_state.proc_in_result:
            res = st.session_state.proc_in_result
            st.success(f"✅ Process Inward Challan **{res['challan_no']}** saved!")
            ic1, ic2 = st.columns(2)
            if res.get("pdf_url"):
                ic1.markdown(f"[📄 Open Challan in Drive]({res['pdf_url']})")
            if res.get("pdf_bytes"):
                ic2.download_button("⬇️ Download Challan PDF", res["pdf_bytes"], res["pdf_name"], "application/pdf", key="proc_in_dl")

    with tab_view:
        rows = [{**doc.to_dict(), "Date": _fmt_date(doc.to_dict().get("Date",""))} for doc in db.collection("process_inward").stream()]
        if rows:
            want = ["ChallanNo", "Date", "PartyName", "LotNo", "OrderId", "Colour", "Process", "SentQty", "ReceivedQty", "ShortQty", "ShortPct", "Rate", "Amount"]
            df   = pd.DataFrame(rows)
            cols = [c for c in want if c in df.columns]
            st.dataframe(df[cols].sort_values("ChallanNo", ascending=False), use_container_width=True)
        else:
            st.info("No Process Inward records yet")

elif menu == "Packing":
    st.markdown('<div class="page-header"><h1>📦 Packing List</h1></div>', unsafe_allow_html=True)

    import streamlit.components.v1 as components
    components.html("""
    <script>
    (function() {
        var pendingFocus = false;

        function allWtInputs() {
            return Array.from(window.parent.document.querySelectorAll('input')).filter(function(i) {
                return (i.getAttribute('placeholder') || '') === 'Wt';
            });
        }

        function setupWeightEnter() {
            var doc = window.parent.document;
            doc.querySelectorAll('input').forEach(function(inp) {
                if (inp._wEnterBound) return;
                if ((inp.getAttribute('placeholder') || '') !== 'Wt') return;
                inp._wEnterBound = true;
                inp.addEventListener('keydown', function(e) {
                    if (e.key !== 'Enter') return;
                    e.preventDefault();

                    // Find the next available Wt input after the current one
                    var inputs = allWtInputs();
                    var idx    = inputs.indexOf(inp);
                    if (idx >= 0 && idx < inputs.length - 1) {
                        // Move focus to next existing weight box
                        inputs[idx + 1].focus();
                        inputs[idx + 1].select();
                    } else {
                        // At last box — add a new one via ＋ Weight button
                        var allBtns  = Array.from(doc.querySelectorAll('button'));
                        var plusBtns = allBtns.filter(function(b) {
                            return b.textContent.trim().indexOf('＋') !== -1 &&
                                   b.textContent.trim().indexOf('Weight') !== -1;
                        });
                        for (var i = 0; i < plusBtns.length; i++) {
                            if (inp.compareDocumentPosition(plusBtns[i]) & Node.DOCUMENT_POSITION_FOLLOWING) {
                                pendingFocus = true;
                                plusBtns[i].click();
                                break;
                            }
                        }
                    }
                });
            });
        }

        var obs = new MutationObserver(function() {
            if (pendingFocus) {
                var inputs = allWtInputs();
                var newInp = inputs.find(function(i) { return !i._wEnterBound; });
                if (newInp) {
                    newInp.focus();
                    newInp.select();
                    pendingFocus = false;
                }
            }
            setupWeightEnter();
        });

        obs.observe(window.parent.document.body, { childList: true, subtree: true });
        setupWeightEnter();
    })();
    </script>
    """, height=0)

    # ── Auto-ID helper ──
    def get_next_pack_id() -> str:
        max_no = 0
        for doc in db.collection("PackingListRaw").stream():
            v = str(doc.to_dict().get("RawId", "")).strip()
            if v.isdigit():
                max_no = max(max_no, int(v))
        return str(max_no + 1)

    # ── PDF builder ──
    def build_packing_pdf(d: dict, f_lines: list, a_lines: list) -> bytes:
        buf = io.BytesIO()
        doc = SimpleDocTemplate(buf, pagesize=A4,
                                topMargin=1.5*cm, bottomMargin=1.5*cm,
                                leftMargin=1.5*cm, rightMargin=1.5*cm)
        styles  = getSampleStyleSheet()
        normal  = styles["Normal"]
        bold_s  = ParagraphStyle("b", parent=normal, fontName="Helvetica-Bold", fontSize=10)
        small_s = ParagraphStyle("sm", parent=normal, fontSize=9)
        elements = []

        # ── Header: company left, order details right ──
        raw_date = d.get("Date", "")
        try:
            from datetime import datetime as _dt
            disp_date = _dt.strptime(raw_date, "%Y-%m-%d").strftime("%d/%m/%Y")
        except Exception:
            disp_date = raw_date

        title_s = ParagraphStyle("tit", parent=normal, fontName="Helvetica-Bold", fontSize=16)
        co_s    = ParagraphStyle("co",  parent=normal, fontName="Helvetica",      fontSize=11)
        lbl_s   = ParagraphStyle("lbl", parent=normal, fontName="Helvetica",      fontSize=10)
        val_s   = ParagraphStyle("val", parent=normal, fontName="Helvetica-Bold", fontSize=10)

        hdr = Table(
            [[
                Table([[Paragraph("Packing List", title_s)],
                       [Paragraph(COMPANY_NAME,   co_s)]],
                      colWidths=[9*cm]),
                Table([
                    [Paragraph("OrderID:", lbl_s),   Paragraph(str(d.get("OrderId", "")),          val_s)],
                    [Paragraph("Date:",    lbl_s),   Paragraph(disp_date,                          val_s)],
                    [Paragraph("Customer:",lbl_s),   Paragraph(str(d.get("Customer name", "")),    val_s)],
                    [Paragraph("Item:",    lbl_s),   Paragraph(str(d.get("Item", "")),             val_s)],
                ], colWidths=[2.2*cm, 6.8*cm]),
            ]],
            colWidths=[9*cm, 9*cm]
        )
        hdr.setStyle(TableStyle([("VALIGN", (0,0), (-1,-1), "TOP")]))
        elements.append(hdr)
        elements.append(Spacer(1, 0.5*cm))

        # ── Parse a colour line ──
        def parse_line(line):
            if ":" not in line:
                return None
            colour, wstr = line.split(":", 1)
            weights = [w.strip() for w in wstr.strip().split(",") if w.strip()]
            try:
                total = round(sum(float(w) for w in weights), 2)
            except Exception:
                total = 0.0
            rolls  = len(weights)
            chunks = [weights[i:i+10] for i in range(0, len(weights), 10)]
            return {"colour": colour.strip(), "weights": weights,
                    "rolls": rolls, "total": total, "chunks": chunks}

        # ── Section table ──
        def section_table(lines, title):
            parsed = [parse_line(l) for l in lines if l.strip()]
            parsed = [p for p in parsed if p]
            if not parsed:
                return 0, 0   # total_wt, total_rolls

            elements.append(Paragraph(f"<b>{title}</b>", bold_s))
            elements.append(Spacer(1, 0.15*cm))

            hdr_row  = [
                Paragraph("<b>Colour</b>",      bold_s),
                Paragraph("<b>Rolls</b>",        bold_s),
                Paragraph("<b>Total Wt</b>",     bold_s),
                Paragraph("<b>Roll Weights (max 10 per row)</b>", bold_s),
            ]
            tbl_data = [hdr_row]
            for p in parsed:
                for j, chunk in enumerate(p["chunks"]):
                    wt_row = ", ".join(w + " Kg" for w in chunk)
                    if j == 0:
                        tbl_data.append([
                            Paragraph(p["colour"],          normal),
                            Paragraph(str(p["rolls"]),      normal),
                            Paragraph(str(p["total"]) + " Kg", normal),
                            Paragraph(wt_row,               small_s),
                        ])
                    else:
                        tbl_data.append([
                            Paragraph("",    normal),
                            Paragraph("",    normal),
                            Paragraph("",    normal),
                            Paragraph(wt_row, small_s),
                        ])

            ct = Table(tbl_data, colWidths=[5*cm, 1.5*cm, 2.5*cm, 9*cm], repeatRows=1)
            ct.setStyle(TableStyle([
                ("BACKGROUND",     (0, 0), (-1, 0),  colors.HexColor("#f0f0f0")),
                ("FONTNAME",       (0, 0), (-1, 0),  "Helvetica-Bold"),
                ("FONTNAME",       (0, 1), (-1, -1), "Helvetica"),
                ("FONTSIZE",       (0, 0), (-1, -1), 9),
                ("GRID",           (0, 0), (-1, -1), 0.5, colors.grey),
                ("VALIGN",         (0, 0), (-1, -1), "MIDDLE"),
                ("PADDING",        (0, 0), (-1, -1), 5),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#fafafa")]),
            ]))
            elements.append(ct)
            elements.append(Spacer(1, 0.4*cm))

            total_wt    = round(sum(p["total"] for p in parsed), 2)
            total_rolls = sum(p["rolls"] for p in parsed)
            return total_wt, total_rolls

        f_wt,  f_rolls  = section_table(f_lines, "Fabric")
        a_wt,  a_rolls  = section_table(a_lines, "Accessory")
        grand_wt    = round(f_wt + a_wt, 2)
        grand_rolls = f_rolls + a_rolls

        # ── Summary boxes ──
        sum_s    = ParagraphStyle("sl", parent=normal, fontSize=9,  fontName="Helvetica")
        sum_big  = ParagraphStyle("sb", parent=normal, fontSize=13, fontName="Helvetica-Bold")

        def summary_cell(label, wt, rolls):
            return [
                Paragraph(label,            sum_s),
                Paragraph(f"{wt} kg",       sum_big),
                Paragraph(f"Rolls: {rolls}", sum_s),
            ]

        sum_tbl = Table(
            [[
                summary_cell("Fabric Total",                  f_wt,     f_rolls),
                summary_cell("Accessory Total",               a_wt,     a_rolls),
                summary_cell("Grand Total (Fabric + Accessory)", grand_wt, grand_rolls),
            ]],
            colWidths=[6*cm, 6*cm, 6*cm]
        )
        sum_tbl.setStyle(TableStyle([
            ("BOX",     (0, 0), (0, 0), 0.5, colors.grey),
            ("BOX",     (1, 0), (1, 0), 0.5, colors.grey),
            ("BOX",     (2, 0), (2, 0), 0.5, colors.grey),
            ("VALIGN",  (0, 0), (-1, -1), "TOP"),
            ("PADDING", (0, 0), (-1, -1), 8),
        ]))
        elements.append(sum_tbl)

        doc.build(elements)
        return buf.getvalue()

    tab_form, tab_print = st.tabs(["📝 New Packing List", "🖨️ Print Packing List"])

    # ── Session state (shared across both tabs) ──
    if "pack_fabric_rows"    not in st.session_state: st.session_state.pack_fabric_rows    = [{"id": 0, "wc": 12}]
    if "pack_fabric_nid"     not in st.session_state: st.session_state.pack_fabric_nid     = 1
    if "pack_acc_rows"       not in st.session_state: st.session_state.pack_acc_rows       = [{"id": 0, "wc": 12}]
    if "pack_acc_nid"        not in st.session_state: st.session_state.pack_acc_nid        = 1
    if "pack_result"         not in st.session_state: st.session_state.pack_result         = None
    if "pack_last_oid"       not in st.session_state: st.session_state.pack_last_oid       = ""

    # ── Clear callback ──
    def _clear_packing():
        for k in [k for k in st.session_state if k.startswith(("fc_", "ac_", "pack_oid", "pack_item"))]:
            del st.session_state[k]
        st.session_state.pack_fabric_rows = [{"id": 0, "wc": 12}]
        st.session_state.pack_fabric_nid  = 1
        st.session_state.pack_acc_rows    = [{"id": 0, "wc": 12}]
        st.session_state.pack_acc_nid     = 1
        st.session_state.pack_result      = None
        st.session_state.pack_last_oid    = ""

    with tab_form:
        # ── Order ID + auto-fetch ──
        oc1, oc2, oc3 = st.columns([1.5, 2, 2])
        with oc1:
            order_id_in = st.text_input("Order ID", key="pack_oid")

        pack_po = None
        if order_id_in.strip():
            import re as _re_pack_oid
            oid_clean = order_id_in.strip()
            po_doc = db.collection("po").document(oid_clean).get()
            if po_doc.exists:
                pack_po = po_doc.to_dict()
            else:
                # For suffixed IDs like "1750A", fall back to base numeric "1750"
                _m = _re_pack_oid.match(r'^(\d+)', oid_clean)
                _base = _m.group(1) if _m else None
                if _base and _base != oid_clean:
                    po_doc2 = db.collection("po").document(_base).get()
                    if po_doc2.exists:
                        pack_po = po_doc2.to_dict()
            if not pack_po:
                st.warning("PO not found — Customer Name and Item can be entered manually.")

        # Reset fields when order changes
        if order_id_in.strip() != st.session_state.pack_last_oid:
            st.session_state.pack_last_oid    = order_id_in.strip()
            st.session_state.pack_item_edit   = pack_po.get("Item", "")         if pack_po else ""
            st.session_state.pack_cust_manual = pack_po.get("Customer name", "") if pack_po else ""
        if "pack_item_edit"   not in st.session_state: st.session_state.pack_item_edit   = ""
        if "pack_cust_manual" not in st.session_state: st.session_state.pack_cust_manual = ""

        with oc2:
            # Editable if PO not found, auto-filled + locked if PO exists
            if pack_po:
                st.text_input("Customer Name",
                              value=pack_po.get("Customer name", ""),
                              disabled=True)
                pack_customer = pack_po.get("Customer name", "")
            else:
                pack_customer = st.text_input("Customer Name (manual)", key="pack_cust_manual")
        with oc3:
            pack_item = st.text_input("Item (editable)", key="pack_item_edit")

        st.caption("Customer and item auto-fetch if Order ID exists in PO. If not, enter manually.")
        st.divider()

        # ── Colour section renderer ──
        def render_section(rows_key, nid_key, prefix, section_label):
            st.markdown(f"**{section_label}**")
            st.caption("One colour row can have unlimited weights. Click ＋ to add more weight boxes.")

            WROW = 4   # max weight inputs per row
            rows = st.session_state[rows_key]
            for row in list(rows):
                rid      = row["id"]
                wc       = row["wc"]
                indices  = list(range(wc))
                sub_rows = [indices[i:i+WROW] for i in range(0, max(len(indices),1), WROW)]
                if not sub_rows:
                    sub_rows = [[]]

                for sr_idx, sr in enumerate(sub_rows):
                    n = len(sr)
                    if sr_idx == 0:
                        # First sub-row: Colour | weights | Delete
                        cols = st.columns([2.5] + [1]*n + [0.5])
                        with cols[0]:
                            st.text_input("Colour", placeholder="e.g. RED",
                                          key=f"{prefix}_colour_{rid}", label_visibility="collapsed")
                        for k, j in enumerate(sr):
                            with cols[k+1]:
                                st.text_input(f"w{j}", placeholder="Wt",
                                              key=f"{prefix}_w_{rid}_{j}", label_visibility="collapsed")
                        with cols[-1]:
                            if st.button("🗑", key=f"{prefix}_rm_{rid}", help="Remove colour row"):
                                st.session_state[rows_key] = [r for r in rows if r["id"] != rid]
                                st.rerun()
                    else:
                        # Continuation sub-rows: blank | weights | blank
                        cols = st.columns([2.5] + [1]*n + [0.5])
                        for k, j in enumerate(sr):
                            with cols[k+1]:
                                st.text_input(f"w{j}", placeholder="Wt",
                                              key=f"{prefix}_w_{rid}_{j}", label_visibility="collapsed")

                # Add weight button below colour block
                if st.button("＋ Weight", key=f"{prefix}_aw_{rid}", help="Add weight box"):
                    row["wc"] += 1
                    st.rerun()

                st.markdown("---")

            if st.button(f"＋ Add {section_label.split()[0]} Row", key=f"{prefix}_addrow"):
                nid = st.session_state[nid_key]
                st.session_state[nid_key] += 1
                st.session_state[rows_key].append({"id": nid, "wc": 12})
                st.rerun()

            # Live output preview
            lines = []
            for row in st.session_state[rows_key]:
                rid    = row["id"]
                colour = st.session_state.get(f"{prefix}_colour_{rid}", "").strip().upper()
                ws     = [st.session_state.get(f"{prefix}_w_{rid}_{j}", "").strip()
                          for j in range(row["wc"])]
                ws = [w for w in ws if w]
                if colour and ws:
                    lines.append(f"{colour}: {','.join(ws)}")

            st.markdown(f"**{section_label.split()[0]} Output Preview**")
            st.text_area(f"{prefix}_output_preview", value="\n".join(lines), disabled=True,
                         height=90, label_visibility="collapsed")
            return lines

        fc, ac = st.columns(2)
        with fc:
            f_lines = render_section("pack_fabric_rows", "pack_fabric_nid", "fc", "Fabric Colour Weights")
        with ac:
            a_lines = render_section("pack_acc_rows",    "pack_acc_nid",    "ac", "Accessory Colour Weights")

        st.divider()

        # ── Submit / Clear ──
        sb1, sb2, _ = st.columns([1, 1, 5])
        with sb1:
            submit = st.button("Submit", type="primary")
        with sb2:
            st.button("Clear", on_click=_clear_packing)

        if submit:
            if not order_id_in.strip():
                st.error("Enter an Order ID")
            elif not f_lines and not a_lines:
                st.error("Enter at least one colour with weights")
            else:
                raw_id        = get_next_pack_id()
                pack_date_str = date.today().strftime("%Y-%m-%d")
                data = {
                    "RawId":            raw_id,
                    "Date":             pack_date_str,
                    "OrderId":          order_id_in.strip(),
                    "Customer name":    pack_customer.strip().upper(),
                    "Item":             pack_item,
                    "FabricDetails":    "\n".join(f_lines),
                    "AccessoryDetails": "\n".join(a_lines),
                }
                pdf_url   = ""
                pdf_bytes = None
                pdf_name  = f"PackingList_{order_id_in.strip()}_{raw_id}.pdf"

                with st.spinner("Saving..."):
                    # Save new entry first
                    db.collection("PackingListRaw").document(raw_id).set(data)

                    # Fetch ALL entries for this OrderId (including the one just saved)
                    # and merge FabricDetails + AccessoryDetails by colour
                    all_slips = [
                        d.to_dict() for d in
                        db.collection("PackingListRaw")
                        .where("OrderId", "==", order_id_in.strip())
                        .stream()
                    ]

                    def _merge_lines(slips, field):
                        colour_weights = {}
                        for slip in slips:
                            for line in slip.get(field, "").splitlines():
                                if ":" not in line:
                                    continue
                                colour, wstr = line.split(":", 1)
                                colour = colour.strip().upper()
                                weights = [w.strip() for w in wstr.split(",") if w.strip()]
                                if colour not in colour_weights:
                                    colour_weights[colour] = []
                                colour_weights[colour].extend(weights)
                        return [f"{c}: {','.join(ws)}" for c, ws in colour_weights.items()]

                    merged_f = _merge_lines(all_slips, "FabricDetails")
                    merged_a = _merge_lines(all_slips, "AccessoryDetails")
                    slip_count = len(all_slips)

                    try:
                        pdf_bytes = build_packing_pdf(data, merged_f, merged_a)
                        pdf_name  = f"PackingList_{order_id_in.strip()}.pdf"
                        pdf_res   = upload_to_firebase_storage(
                            pdf_bytes,
                            f"packing_pdfs/PackingList_{order_id_in.strip()}.pdf",
                            "application/pdf",
                        )
                        pdf_url = pdf_res
                        # Update all slips for this OrderId with the merged pdf_url
                        for slip in all_slips:
                            db.collection("PackingListRaw").document(slip["RawId"]).update({"pdf_url": pdf_url})
                    except Exception as e:
                        st.warning(f"PDF error: {e}")
                        if pdf_bytes is None:
                            pdf_bytes = build_packing_pdf(data, merged_f, merged_a)

                    if slip_count > 1:
                        st.info(f"ℹ️ PDF merged across {slip_count} packing slips for Order {order_id_in.strip()}")

                st.session_state.pack_result = {
                    "raw_id": raw_id, "pdf_bytes": pdf_bytes,
                    "pdf_url": pdf_url, "pdf_name": pdf_name,
                }
                st.rerun()

        if st.session_state.pack_result:
            res = st.session_state.pack_result
            st.success(f"✅ Packing List **{res['raw_id']}** saved!")
            pc1, pc2 = st.columns(2)
            if res.get("pdf_url"):
                pc1.markdown(f"[📄 Open Packing List in Drive]({res['pdf_url']})")
            if res.get("pdf_bytes"):
                pc2.download_button("⬇️ Download Packing List PDF",
                                    res["pdf_bytes"], res["pdf_name"],
                                    "application/pdf", key="pack_dl")

    with tab_print:
        import streamlit.components.v1 as _plcomps
        from datetime import datetime as _pldt

        pl_oid = st.text_input("Enter Order ID", key="pl_print_oid", placeholder="e.g. 1001")

        if pl_oid.strip():
            pl_docs = list(db.collection("PackingListRaw")
                           .where("OrderId", "==", pl_oid.strip()).stream())
            if not pl_docs:
                st.error("No packing list found for this Order ID")
            else:
                pl_data = pl_docs[0].to_dict()

                def _parse_pack_line(line):
                    if ":" not in line: return None
                    colour, wstr = line.split(":", 1)
                    ws = [w.strip() for w in wstr.split(",") if w.strip()]
                    try: total = round(sum(float(w) for w in ws), 2)
                    except Exception: total = 0.0
                    return {"colour": colour.strip(), "weights": ws, "rolls": len(ws), "total": total}

                def _section_rows_html(lines):
                    if not lines:
                        return "<tr><td colspan='4' style='text-align:center;color:#999;'>No data</td></tr>"
                    rows = ""
                    for line in lines:
                        p = _parse_pack_line(line)
                        if not p: continue
                        wt_str = ", ".join(f"{w} Kg" for w in p["weights"])
                        rows += (f"<tr><td><b>{p['colour']}</b></td>"
                                 f"<td style='text-align:center'>{p['rolls']}</td>"
                                 f"<td style='text-align:right'>{p['total']}</td>"
                                 f"<td>{wt_str}</td></tr>")
                    return rows

                f_lines = [l for l in pl_data.get("FabricDetails","").splitlines()  if l.strip()]
                a_lines = [l for l in pl_data.get("AccessoryDetails","").splitlines() if l.strip()]
                f_parsed = [p for l in f_lines for p in [_parse_pack_line(l)] if p]
                a_parsed = [p for l in a_lines for p in [_parse_pack_line(l)] if p]
                f_total_wt = round(sum(p["total"] for p in f_parsed), 2)
                f_total_rolls = sum(p["rolls"] for p in f_parsed)
                a_total_wt = round(sum(p["total"] for p in a_parsed), 2)
                a_total_rolls = sum(p["rolls"] for p in a_parsed)
                grand_wt = round(f_total_wt + a_total_wt, 2)
                grand_rolls = f_total_rolls + a_total_rolls

                raw_date = pl_data.get("Date","")
                try: disp_date = _pldt.strptime(raw_date, "%Y-%m-%d").strftime("%d/%m/%Y")
                except Exception: disp_date = raw_date

                html = f"""
                <style>
                  @media print {{ .no-print {{ display: none !important; }} body {{ margin: 0; }} }}
                  .pl-wrap {{ font-family: Arial, sans-serif; font-size: 13px; max-width: 900px; padding: 20px; color: #222; }}
                  .pl-header {{ display: flex; justify-content: space-between; align-items: flex-start;
                    margin-bottom: 20px; border-bottom: 2px solid #C4956A; padding-bottom: 12px; }}
                  .pl-title {{ font-size: 22px; font-weight: 700; margin: 0; }}
                  .pl-company {{ color: #888; margin: 3px 0 0; font-size: 13px; }}
                  .pl-meta td {{ padding: 2px 6px; font-size: 13px; }}
                  .pl-meta td:first-child {{ font-weight: 700; color: #555; }}
                  .pl-section {{ margin-top: 18px; }}
                  .pl-section h4 {{ font-size: 14px; margin: 0 0 6px; border-bottom: 1px solid #ddd;
                    padding-bottom: 4px; color: #5C3410; }}
                  .pl-table {{ width: 100%; border-collapse: collapse; font-size: 12px; }}
                  .pl-table th {{ background: #f0f0f0; border: 1px solid #ccc; padding: 6px 8px; text-align: left; }}
                  .pl-table td {{ border: 1px solid #ddd; padding: 5px 8px; vertical-align: top; }}
                  .pl-table tr:nth-child(even) td {{ background: #fafafa; }}
                  .pl-summary {{ display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; margin-top: 20px; }}
                  .pl-sum-box {{ border: 1px solid #ddd; border-radius: 6px; padding: 10px 14px; }}
                  .pl-sum-label {{ font-size: 11px; color: #888; margin: 0 0 4px; }}
                  .pl-sum-val {{ font-size: 18px; font-weight: 700; margin: 0; }}
                  .pl-sum-sub {{ font-size: 12px; color: #666; margin: 2px 0 0; }}
                  .print-btn {{ background: #C4956A; color: white; border: none; padding: 10px 28px;
                    font-size: 14px; border-radius: 8px; cursor: pointer; margin-bottom: 16px; font-weight: 600; }}
                  .print-btn:hover {{ background: #A07848; }}
                </style>
                <script>
                function printPackingList() {{
                    var content = document.getElementById('pl-content').outerHTML;
                    var style   = document.querySelector('style').outerHTML;
                    var win = window.open('', '_blank', 'width=960,height=800');
                    win.document.write('<html><head><title>Packing List</title>' + style + '</head>' +
                        '<body style="margin:20px;font-family:Arial,sans-serif;">' + content + '</body></html>');
                    win.document.close(); win.focus();
                    setTimeout(function() {{ win.print(); win.close(); }}, 400);
                }}
                </script>
                <button class="print-btn" onclick="printPackingList()">🖨️ Print</button>
                <div class="pl-wrap" id="pl-content">
                  <div class="pl-header">
                    <div><p class="pl-title">Packing List</p><p class="pl-company">{COMPANY_NAME}</p></div>
                    <table class="pl-meta">
                      <tr><td>OrderID:</td><td><b>{pl_data.get('OrderId','')}</b></td></tr>
                      <tr><td>Date:</td><td><b>{disp_date}</b></td></tr>
                      <tr><td>Customer:</td><td><b>{pl_data.get('Customer name','')}</b></td></tr>
                      <tr><td>Item:</td><td><b>{pl_data.get('Item','')}</b></td></tr>
                    </table>
                  </div>
                  <div class="pl-section"><h4>Fabric</h4>
                    <table class="pl-table"><thead><tr>
                      <th>Colour</th><th>Rolls</th><th>Total Wt</th><th>Roll Weights</th>
                    </tr></thead><tbody>{_section_rows_html(f_lines)}</tbody></table></div>
                  <div class="pl-section"><h4>Accessory</h4>
                    <table class="pl-table"><thead><tr>
                      <th>Colour</th><th>Rolls</th><th>Total Wt</th><th>Roll Weights</th>
                    </tr></thead><tbody>{_section_rows_html(a_lines)}</tbody></table></div>
                  <div class="pl-summary">
                    <div class="pl-sum-box"><p class="pl-sum-label">Fabric Total</p>
                      <p class="pl-sum-val">{f_total_wt} kg</p><p class="pl-sum-sub">Rolls: {f_total_rolls}</p></div>
                    <div class="pl-sum-box"><p class="pl-sum-label">Accessory Total</p>
                      <p class="pl-sum-val">{a_total_wt} kg</p><p class="pl-sum-sub">Rolls: {a_total_rolls}</p></div>
                    <div class="pl-sum-box"><p class="pl-sum-label">Grand Total</p>
                      <p class="pl-sum-val">{grand_wt} kg</p><p class="pl-sum-sub">Rolls: {grand_rolls}</p></div>
                  </div>
                </div>"""
                _plcomps.html(html, height=900, scrolling=True)

elif menu == "Cancel Order":
    st.markdown('<div class="page-header"><h1>❌ Cancel Order</h1></div>', unsafe_allow_html=True)

    if "cancel_result" not in st.session_state:
        st.session_state.cancel_result = None

    tab_cancel, tab_view = st.tabs(["Cancel Order", "View Cancelled Orders"])

    with tab_cancel:

        order_id_in = st.text_input("Order ID", key="cancel_oid")

        po_data = None
        if order_id_in.strip():
            po_doc = db.collection("po").document(order_id_in.strip()).get()
            if po_doc.exists:
                po_data = po_doc.to_dict()
            else:
                st.error("❌ No PO found for this Order ID — cancellation will be marked INVALID")

        # Show PO details for confirmation
        if po_data:
            st.success("✅ PO found")
            st.markdown("#### Order Details")
            c1, c2 = st.columns(2)
            with c1:
                st.text_input("Customer",  value=po_data.get("Customer name", ""), disabled=True, key="co_cust")
                st.text_input("Item",      value=po_data.get("Item", ""),           disabled=True, key="co_item")
                st.text_input("Category",  value=po_data.get("Category", ""),       disabled=True, key="co_cat")
            with c2:
                st.text_input("PO Date",   value=po_data.get("Date", ""),           disabled=True, key="co_date")
                st.text_input("Fabric Qty",value=str(po_data.get("facricqnty", "")),disabled=True, key="co_fqty")
                st.text_input("Customer PO No", value=po_data.get("customerpono", ""), disabled=True, key="co_pono")

            st.divider()

        # Cancel form
        cancel_date    = st.date_input("Cancellation Date", value=date.today(), format="DD/MM/YYYY", key="cancel_date")
        cancel_date_str = cancel_date.strftime("%Y-%m-%d")
        reason         = st.text_area("Reason for Cancellation (optional)", key="cancel_reason")

        st.warning("⚠️ This action will permanently mark the order as cancelled. This cannot be undone.")
        confirm = st.checkbox("I confirm I want to cancel this order", key="cancel_confirm")

        if confirm:
            if st.button("🚫 Cancel Order", type="primary", key="cancel_submit"):
                if not order_id_in.strip():
                    st.error("Enter an Order ID")
                else:
                    status = "VALID" if po_data else "INVALID"
                    doc_id = f"{order_id_in.strip()}_{cancel_date_str}"
                    data   = {
                        "OrderId":  order_id_in.strip(),
                        "Date":     cancel_date_str,
                        "Reason":   reason.strip(),
                        "Status":   status,
                        "Customer": po_data.get("Customer name", "") if po_data else "",
                        "Item":     po_data.get("Item", "")          if po_data else "",
                    }
                    db.collection("cancel_orders").document(doc_id).set(data)
                    st.session_state.cancel_result = {
                        "order_id": order_id_in.strip(),
                        "status":   status,
                    }
                    # Clear inputs
                    for k in ["cancel_oid", "cancel_reason", "cancel_confirm"]:
                        if k in st.session_state:
                            del st.session_state[k]
                    st.rerun()

        if st.session_state.cancel_result:
            res = st.session_state.cancel_result
            if res["status"] == "VALID":
                st.success(f"✅ Order **{res['order_id']}** has been cancelled successfully.")
            else:
                st.warning(f"⚠️ Cancel entry saved for Order **{res['order_id']}** — PO was not found (marked INVALID).")

    with tab_view:
        rows = [{**doc.to_dict(), "Date": _fmt_date(doc.to_dict().get("Date",""))} for doc in db.collection("cancel_orders").stream()]
        if rows:
            want = ["OrderId", "Date", "Customer", "Item", "Reason", "Status"]
            df   = pd.DataFrame(rows)
            cols = [c for c in want if c in df.columns]
            # Highlight VALID cancellations in red
            def highlight_status(row):
                if row.get("Status") == "VALID":
                    return ["background-color: #ffe0e0"] * len(row)
                return [""] * len(row)
            st.dataframe(
                df[cols].sort_values("Date", ascending=False),
                use_container_width=True,
            )
        else:
            st.info("No cancelled orders yet")

elif menu == "Reports":
    import plotly.express as px

    st.markdown('<div class="page-header"><h1>📈 Reports</h1></div>', unsafe_allow_html=True)
    if st.button("🔄 Refresh", key="rep_refresh"):
        st.rerun()

    with st.spinner("Loading..."):
        df = _load_status_df()

    if df.empty:
        st.info("No PO data yet")
        st.stop()

    df_active  = df[df["Status"] != "Cancelled"]   # cancelled excluded everywhere
    cancel_df  = df[df["Status"] == "Cancelled"]   # only for cancelled tab
    pending_df = df_active[df_active["Status"] == "Pending"]
    prod_df    = df_active[
        (df_active["Status"] == "Knitting") |
        df_active["Status"].str.startswith("On Dyeing", na=False) |
        (df_active["Status"] == "In House Finishing/Packing")
    ]

    # ── Left-panel navigation ──
    rpt_type = st.session_state.get("rpt_sub", "📋 All Orders")

    show_cols = ["OrderId", "Customer", "Item", "Category", "Date", "FabricQty", "Status"]

    def show_table(data, title=""):
        if title:
            st.markdown(f"**{title}  —  {len(data)} orders  |  Total Qty: {int(data['FabricQty'].sum())}**")
        if data.empty:
            st.info("No records")
            return
        cols = [c for c in show_cols if c in data.columns]
        st.dataframe(data[cols].sort_values("OrderId", ascending=False),
                     use_container_width=True, hide_index=True)

    if True:  # replaces: with rpt_col:
     if rpt_type == "📋 All Orders":
        # Status colour bar — active orders only (no cancelled)
        status_grp = df_active.groupby("Status").agg(Orders=("OrderId","count"),
                                                      Qty=("FabricQty","sum")).reset_index()
        fig = px.bar(status_grp, x="Status", y="Qty", color="Status",
                     text="Orders", title="Active Orders by Status (Qty)",
                     color_discrete_sequence=px.colors.qualitative.Safe)
        fig.update_layout(showlegend=False, height=300, margin=dict(t=40,b=0))
        st.plotly_chart(fig, use_container_width=True)
        show_table(df_active)

     elif rpt_type == "🔵 Pending — STRIPE":
        data = pending_df[pending_df["Category"] == "STRIPE"].copy()
        _pending_report(data, "STRIPE", "Blues",  "ps")

     elif rpt_type == "🟠 Pending — PLAIN":
        data = pending_df[pending_df["Category"] == "PLAIN"].copy()
        _pending_report(data, "PLAIN",  "Oranges", "pp")

     elif rpt_type == "⚙️ In Production":
        # Category filter
        cat_filter = st.radio(
            "Category", ["ALL", "STRIPE", "PLAIN"],
            horizontal=True, key="prod_cat_filter"
        )

        if cat_filter == "ALL":
            cat_prod_df = prod_df.copy()
        else:
            cat_prod_df = prod_df[prod_df["Category"] == cat_filter].copy()

        # Build On-Processing Qty per OrderId from process_out
        proc_out_docs = db.collection("process_out").stream()
        proc_out_qty  = {}
        for d in proc_out_docs:
            row = d.to_dict()
            oid = str(row.get("OrderId","")).strip()
            qty = float(row.get("Qnty", 0) or 0)
            proc_out_qty[oid] = proc_out_qty.get(oid, 0.0) + qty

        cat_prod_df["OnProcessingQty"] = cat_prod_df["OrderId"].map(
            lambda x: int(proc_out_qty.get(str(x), 0))
        )

        # KPI tiles for filtered set
        knit_df    = cat_prod_df[cat_prod_df["Status"] == "Knitting"]
        dye_df     = cat_prod_df[cat_prod_df["Status"].str.startswith("On Dyeing", na=False)]
        inhouse_df = cat_prod_df[cat_prod_df["Status"] == "In House Finishing/Packing"]

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Total In Production",        len(cat_prod_df),  f"{int(cat_prod_df['FabricQty'].sum()):,} qty")
        k2.metric("🧶 Knitting",                 len(knit_df),      f"{int(knit_df['FabricQty'].sum()):,} qty")
        k3.metric("🎨 On Dyeing/Washing",        len(dye_df),       f"{int(dye_df['FabricQty'].sum()):,} qty")
        k4.metric("🏠 In House (Rcvd from Proc)",len(inhouse_df),   f"{int(inhouse_df['FabricQty'].sum()):,} qty")

        st.markdown("---")

        if cat_prod_df.empty:
            st.info(f"No in-production orders for {cat_filter}")
        else:
            # ── Fetch shoot order dates ──
            from datetime import datetime as _ipdt, date as _ipdate
            so_date_map = {}
            for _sd in db.collection("shoot_order").stream():
                _sdd = _sd.to_dict()
                _oid = str(_sdd.get("OrderId","")).strip()
                _dt_raw = str(_sdd.get("Date","")).strip()
                try:
                    so_date_map[_oid] = _ipdt.strptime(_dt_raw, "%Y-%m-%d").date()
                except Exception:
                    pass

            today = _ipdate.today()
            cat_prod_df["ShootDate"] = cat_prod_df["OrderId"].astype(str).map(
                lambda x: so_date_map.get(x, None))
            cat_prod_df["DaysInProd"] = cat_prod_df["ShootDate"].apply(
                lambda d: (today - d).days if d else None)

            # ── Filters row ──
            fc1, fc2 = st.columns([2, 1])
            with fc1:
                ip_search = st.text_input("🔍 Search Order ID", placeholder="e.g. 1001",
                                          key="ip_search")
            with fc2:
                min_days = st.number_input("⏱ In production more than (days)",
                                           min_value=0, value=None, placeholder="e.g. 25",
                                           key="ip_min_days")

            if ip_search.strip():
                cat_prod_df = cat_prod_df[
                    cat_prod_df["OrderId"].astype(str).str.contains(ip_search.strip(), na=False)
                ]
            if min_days is not None:
                cat_prod_df = cat_prod_df[
                    cat_prod_df["DaysInProd"].apply(lambda d: d is not None and d > min_days)
                ]
                if cat_prod_df.empty:
                    st.info(f"No orders in production for more than {int(min_days)} days.")

            disp_cols = ["OrderId", "Customer", "Item", "Category", "Date",
                         "DaysInProd", "FabricQty", "OnProcessingQty", "Status"]
            disp_cols = [c for c in disp_cols if c in cat_prod_df.columns]

            from reportlab.platypus import HRFlowable
            from datetime import datetime as _iprdt

            st.markdown(f"**In Production — {cat_filter}  —  {len(cat_prod_df)} orders  |  "
                        f"Total Fabric Qty: {int(cat_prod_df['FabricQty'].sum()):,}  |  "
                        f"Total On Processing: {int(cat_prod_df['OnProcessingQty'].sum()):,}**")
            st.caption("Click a row to open the corresponding Shoot Order PDF.")

            # ── Export to PDF ──
            def _build_inprod_pdf(df_export, cat, min_d):
                buf  = io.BytesIO()
                doc  = SimpleDocTemplate(buf, pagesize=A4,
                                         topMargin=1.5*cm, bottomMargin=1.5*cm,
                                         leftMargin=1.5*cm, rightMargin=1.5*cm)
                styles = getSampleStyleSheet()
                el     = []
                # Header
                el.append(Paragraph("LKF ERP", ParagraphStyle("t", parent=styles["Heading1"],
                           fontSize=16, fontName="Helvetica-Bold", alignment=1, spaceAfter=4)))
                el.append(Paragraph("IN PRODUCTION REPORT", ParagraphStyle("s", parent=styles["Heading2"],
                           fontSize=13, alignment=1, spaceAfter=10)))
                filter_txt = f"Category: {cat}"
                if min_d: filter_txt += f"  |  More than {int(min_d)} days in production"
                filter_txt += f"  |  Generated: {_iprdt.today().strftime('%d/%m/%Y')}"
                el.append(Paragraph(filter_txt, ParagraphStyle("f", parent=styles["Normal"],
                           fontSize=9, textColor=colors.HexColor("#888888"), spaceAfter=12)))

                # Table
                hdrs = ["Order ID","Customer","Item","Category","Date","Days","Fabric Qty","On Proc. Qty","Status"]
                rows = [hdrs]
                for _, r in df_export.sort_values("OrderId", ascending=False).iterrows():
                    rows.append([
                        str(r.get("OrderId","")),
                        str(r.get("Customer","")),
                        str(r.get("Item","")),
                        str(r.get("Category","")),
                        str(r.get("Date","")),
                        str(r.get("DaysInProd","")) if r.get("DaysInProd") is not None else "—",
                        str(int(r.get("FabricQty",0))),
                        str(int(r.get("OnProcessingQty",0))),
                        str(r.get("Status","")),
                    ])
                col_w = [1.8*cm, 3.5*cm, 3*cm, 1.8*cm, 2.2*cm, 1.5*cm, 2*cm, 2.2*cm, 3*cm]
                t = Table(rows, colWidths=col_w, repeatRows=1)
                t.setStyle(TableStyle([
                    ("BACKGROUND",     (0,0),(-1,0),  colors.HexColor("#1a3c6e")),
                    ("TEXTCOLOR",      (0,0),(-1,0),  colors.white),
                    ("FONTNAME",       (0,0),(-1,0),  "Helvetica-Bold"),
                    ("FONTNAME",       (0,1),(-1,-1), "Helvetica"),
                    ("FONTSIZE",       (0,0),(-1,-1), 8),
                    ("GRID",           (0,0),(-1,-1), 0.4, colors.grey),
                    ("VALIGN",         (0,0),(-1,-1), "MIDDLE"),
                    ("PADDING",        (0,0),(-1,-1), 4),
                    ("ROWBACKGROUNDS", (0,1),(-1,-1), [colors.white, colors.HexColor("#f5f5f5")]),
                ]))
                el.append(t)

                # Summary
                el.append(Spacer(1, 0.5*cm))
                summary = Table([[
                    Paragraph(f"<b>Total Orders:</b> {len(df_export)}", styles["Normal"]),
                    Paragraph(f"<b>Total Fabric Qty:</b> {int(df_export['FabricQty'].sum()):,}", styles["Normal"]),
                    Paragraph(f"<b>Total On Processing:</b> {int(df_export['OnProcessingQty'].sum()):,}", styles["Normal"]),
                ]], colWidths=[6*cm, 6*cm, 6*cm])
                summary.setStyle(TableStyle([
                    ("BOX", (0,0),(-1,-1), 0.5, colors.HexColor("#C4956A")),
                    ("PADDING", (0,0),(-1,-1), 6),
                ]))
                el.append(summary)
                doc.build(el)
                return buf.getvalue()

            if st.button("📄 Export to PDF", key="ip_export_pdf"):
                with st.spinner("Generating PDF..."):
                    pdf_bytes = _build_inprod_pdf(cat_prod_df, cat_filter, min_days)
                    fname = f"InProduction_{cat_filter}_{_iprdt.today().strftime('%d%m%Y')}.pdf"
                    st.download_button("⬇️ Download PDF", pdf_bytes, fname,
                                       "application/pdf", key="ip_pdf_dl")

            # Selectable dataframe
            sel = st.dataframe(
                cat_prod_df[disp_cols].sort_values("OrderId", ascending=False),
                use_container_width=True, hide_index=True,
                on_select="rerun", selection_mode="single-row",
                key="ip_table_sel"
            )

            # ── Open Shoot Order PDF on row click ──
            selected_rows = sel.selection.rows if hasattr(sel, "selection") else []
            if selected_rows:
                sel_idx  = selected_rows[0]
                sel_oid  = str(cat_prod_df.sort_values("OrderId", ascending=False)
                               .iloc[sel_idx]["OrderId"])
                so_docs  = list(db.collection("shoot_order")
                                .where("OrderId", "==", sel_oid).stream())
                if so_docs:
                    pdf_url = so_docs[0].to_dict().get("pdf_url", "")
                    so_date = _fmt_date(so_docs[0].to_dict().get("Date", ""))
                    if pdf_url:
                        st.success(f"Order **{sel_oid}** — Shoot Date: {so_date}")
                        st.markdown(f"[📄 Open Shoot Order PDF]({pdf_url})")
                    else:
                        st.warning(f"Shoot Order found for {sel_oid} but no PDF linked yet.")
                else:
                    st.info(f"No Shoot Order found for Order ID {sel_oid}")

            if not ip_search.strip():
                grp = cat_prod_df.groupby("Customer")["FabricQty"].sum().sort_values(ascending=False).reset_index()
                grp.columns = ["Customer", "Qty"]
                fig = px.bar(grp, x="Customer", y="Qty",
                             title=f"In Production by Customer ({cat_filter})",
                             color="Qty", color_continuous_scale="Greens")
                fig.update_layout(height=280, margin=dict(t=40, b=60))
                fig.update_xaxes(tickangle=45)
                st.plotly_chart(fig, use_container_width=True)

     elif rpt_type == "❌ Cancelled":
        show_table(cancel_df, "Cancelled Orders")

     elif rpt_type == "👤 Customer Report":
        st.markdown("### Customer Status Report")

        # ── PDF builder ──
        def build_customer_report_pdf(customer, date_range_label, sections):
            from datetime import datetime as _dt
            buf = io.BytesIO()
            doc = SimpleDocTemplate(buf, pagesize=A4,
                                    topMargin=1.5*cm, bottomMargin=1.5*cm,
                                    leftMargin=1.5*cm, rightMargin=1.5*cm)
            styles  = getSampleStyleSheet()
            normal  = styles["Normal"]
            el      = []

            # Title
            el.append(Paragraph("Customer Status Report",
                                 ParagraphStyle("h", parent=normal, fontSize=18,
                                                fontName="Helvetica-Bold", spaceAfter=4)))
            el.append(Paragraph(f"Customer: {customer}",
                                 ParagraphStyle("sub", parent=normal, fontSize=10, spaceAfter=2)))
            el.append(Paragraph(f"Date Range: {date_range_label}",
                                 ParagraphStyle("sub2", parent=normal, fontSize=10, spaceAfter=14)))

            # ── KPI boxes ──
            def kpi_cell(label, count, qty):
                return Table(
                    [[Paragraph(f"<b>{label}</b>",
                                ParagraphStyle("kl", parent=normal, fontSize=9,
                                               textColor=colors.HexColor("#555555")))],
                     [Paragraph(str(count),
                                ParagraphStyle("kv", parent=normal, fontSize=14,
                                               fontName="Helvetica-Bold"))],
                     [Paragraph(f"Qty: {int(qty)} Kgs",
                                ParagraphStyle("kq", parent=normal, fontSize=9))]],
                    colWidths=[8.5*cm]
                )

            in_prod = sections.get("In Production", pd.DataFrame())
            pending = sections.get("Pending",       pd.DataFrame())
            dispatched = sections.get("Dispatched", pd.DataFrame())
            grand_count = sum(len(v) for v in sections.values())
            grand_qty   = sum(v["FabricQty"].sum() for v in sections.values())

            kpi_tbl = Table(
                [[kpi_cell("IN PRODUCTION", len(in_prod), in_prod["FabricQty"].sum() if not in_prod.empty else 0),
                  kpi_cell("PENDING",       len(pending), pending["FabricQty"].sum() if not pending.empty else 0)],
                 [kpi_cell("DISPATCHED",    len(dispatched), dispatched["FabricQty"].sum() if not dispatched.empty else 0),
                  kpi_cell("GRAND TOTAL",   grand_count, grand_qty)]],
                colWidths=[9*cm, 9*cm]
            )
            kpi_tbl.setStyle(TableStyle([
                ("BOX",     (0,0),(0,0), 0.5, colors.grey),
                ("BOX",     (1,0),(1,0), 0.5, colors.grey),
                ("BOX",     (0,1),(0,1), 0.5, colors.grey),
                ("BOX",     (1,1),(1,1), 0.5, colors.grey),
                ("PADDING", (0,0),(-1,-1), 10),
                ("VALIGN",  (0,0),(-1,-1), "TOP"),
            ]))
            el.append(kpi_tbl)
            el.append(Spacer(1, 0.6*cm))

            # ── Section tables ──
            # In Production includes Shoot Date; other sections do not
            _pdf_cols_prod = ["Date","ShootDate","OrderId","CustomerPoNo","Category","Item","GSM",
                              "FabricQty","AccQty","FabricPrice","AccPrice","image_url"]
            _pdf_hdrs_prod = ["PO Date","Shoot Date","Order ID","Cust PO No","Category","Item","GSM",
                              "Fabric Qty","Acc Qty","Fabric Price","Acc Price","Image"]
            _pdf_col_w_prod = [1.8*cm,1.8*cm,1.5*cm,2*cm,1.6*cm,2.8*cm,1*cm,1.6*cm,1.4*cm,1.6*cm,1.6*cm,2*cm]

            _pdf_cols_base = ["Date","OrderId","CustomerPoNo","Category","Item","GSM",
                              "FabricQty","AccQty","FabricPrice","AccPrice","image_url"]
            _pdf_hdrs_base = ["Date","Order ID","Cust PO No","Category","Item","GSM",
                              "Fabric Qty","Acc Qty","Fabric Price","Acc Price","Image"]
            _pdf_col_w_base = [2*cm,1.5*cm,2*cm,1.8*cm,3.2*cm,1*cm,1.8*cm,1.6*cm,1.8*cm,1.8*cm,2.2*cm]

            sec_title_s = ParagraphStyle("st", parent=normal, fontSize=14,
                                         fontName="Helvetica-Bold", spaceAfter=4)
            sec_sub_s   = ParagraphStyle("ss", parent=normal, fontSize=9,
                                         textColor=colors.HexColor("#555555"))
            cell_s      = ParagraphStyle("cs", parent=normal, fontSize=8)
            hdr_s       = ParagraphStyle("hs", parent=normal, fontSize=8,
                                         fontName="Helvetica-Bold")

            def fmt_date(d):
                try:
                    from datetime import datetime as _dt2
                    return _dt2.strptime(d, "%Y-%m-%d").strftime("%d-%b-%Y")
                except Exception:
                    return d

            for sec_name, sec_df in sections.items():
                if sec_df.empty:
                    continue
                qty_sum = int(sec_df["FabricQty"].sum())
                # Section header row
                sec_tbl = Table(
                    [[Paragraph(sec_name.upper(), sec_title_s),
                      Paragraph(f"Orders: {len(sec_df)} | Qty: {qty_sum} Kgs", sec_sub_s)]],
                    colWidths=[9*cm, 9*cm]
                )
                sec_tbl.setStyle(TableStyle([("VALIGN",(0,0),(-1,-1),"BOTTOM"),
                                             ("ALIGN",(1,0),(1,0),"RIGHT")]))
                el.append(sec_tbl)
                el.append(Spacer(1, 0.15*cm))

                is_prod   = sec_name == "In Production"
                tbl_hdrs  = _pdf_hdrs_prod  if is_prod else _pdf_hdrs_base
                col_w     = _pdf_col_w_prod if is_prod else _pdf_col_w_base

                data_rows = [[Paragraph(h, hdr_s) for h in tbl_hdrs]]
                for _, row in sec_df.sort_values("OrderId", ascending=False).iterrows():
                    img_url  = str(row.get("image_url","") or "")
                    img_cell = Paragraph(
                        f'<link href="{img_url}"><u>View</u></link>' if img_url else "—", cell_s)
                    base_cells = [
                        Paragraph(fmt_date(str(row.get("Date",""))),      cell_s),
                        Paragraph(str(row.get("OrderId","")),             cell_s),
                        Paragraph(str(row.get("CustomerPoNo","") or ""),  cell_s),
                        Paragraph(str(row.get("Category","")),            cell_s),
                        Paragraph(str(row.get("Item","")),                cell_s),
                        Paragraph(str(int(row.get("GSM",0))),             cell_s),
                        Paragraph(str(int(row.get("FabricQty",0))),       cell_s),
                        Paragraph(str(int(row.get("AccQty",0))),          cell_s),
                        Paragraph(str(int(row.get("FabricPrice",0))),     cell_s),
                        Paragraph(str(int(row.get("AccPrice",0))),        cell_s),
                        img_cell,
                    ]
                    if is_prod:
                        shoot_cell = Paragraph(str(row.get("ShootDate","") or "—"), cell_s)
                        data_rows.append([base_cells[0], shoot_cell] + base_cells[1:])
                    else:
                        data_rows.append(base_cells)

                dt = Table(data_rows, colWidths=col_w, repeatRows=1)
                dt.setStyle(TableStyle([
                    ("BACKGROUND",     (0,0),(-1,0),  colors.HexColor("#f0f0f0")),
                    ("FONTNAME",       (0,0),(-1,0),  "Helvetica-Bold"),
                    ("FONTSIZE",       (0,0),(-1,-1), 8),
                    ("GRID",           (0,0),(-1,-1), 0.4, colors.grey),
                    ("VALIGN",         (0,0),(-1,-1), "MIDDLE"),
                    ("PADDING",        (0,0),(-1,-1), 4),
                    ("ROWBACKGROUNDS", (0,1),(-1,-1), [colors.white, colors.HexColor("#fafafa")]),
                ]))
                el.append(dt)
                el.append(Spacer(1, 0.5*cm))

            doc.build(el)
            return buf.getvalue()

        # ── UI ──
        cc1, cc2, cc3 = st.columns([2, 1.5, 1.5])
        with cc1:
            cust_list = sorted(df_active["Customer"].unique().tolist())
            sel_cust  = st.selectbox("Select Customer", cust_list, key="cr_cust") if cust_list else None

        with cc2:
            date_filter = st.selectbox("Date Range", ["All Dates", "This Month", "Custom"], key="cr_drange")

        with cc3:
            include_dispatched = st.checkbox("Include Dispatched", value=False, key="cr_incl_disp")

        from_date, to_date = None, None
        if date_filter == "Custom":
            dc1, dc2 = st.columns(2)
            with dc1:
                from_date = st.date_input("From", format="DD/MM/YYYY", key="cr_from")
            with dc2:
                to_date   = st.date_input("To", format="DD/MM/YYYY", key="cr_to")

        if sel_cust:
            # Include Dispatched if toggled; otherwise use only active orders
            src_df = df if include_dispatched else df_active
            cdf = src_df[src_df["Customer"] == sel_cust].copy()

            # Apply date filter
            if date_filter == "This Month":
                from datetime import datetime as _dt
                cdf["_d"] = pd.to_datetime(cdf["Date"], dayfirst=True, errors="coerce")
                now = _dt.today()
                cdf = cdf[(cdf["_d"].dt.month == now.month) & (cdf["_d"].dt.year == now.year)]
                date_range_label = now.strftime("%B %Y")
            elif date_filter == "Custom" and from_date and to_date:
                cdf["_d"] = pd.to_datetime(cdf["Date"], dayfirst=True, errors="coerce")
                cdf = cdf[(cdf["_d"].dt.date >= from_date) & (cdf["_d"].dt.date <= to_date)]
                date_range_label = f"{from_date.strftime('%d/%m/%Y')} – {to_date.strftime('%d/%m/%Y')}"
            else:
                date_range_label = "All Dates"

            in_prod_df   = cdf[~cdf["Status"].isin(["Pending","Dispatched","Cancelled"])]
            pending_cdf  = cdf[cdf["Status"] == "Pending"]
            dispatch_cdf = cdf[cdf["Status"] == "Dispatched"] if include_dispatched else pd.DataFrame()

            # KPI tiles
            ck1, ck2, ck3, ck4 = st.columns(4)
            ck1.metric("⚙️ In Production", len(in_prod_df),   f"{int(in_prod_df['FabricQty'].sum())} Kgs")
            ck2.metric("⏳ Pending",        len(pending_cdf),  f"{int(pending_cdf['FabricQty'].sum())} Kgs")
            ck3.metric("📦 Dispatched",     len(dispatch_cdf) if include_dispatched else "—",
                                            f"{int(dispatch_cdf['FabricQty'].sum())} Kgs" if include_dispatched else "")
            ck4.metric("📊 Grand Total",    len(cdf),          f"{int(cdf['FabricQty'].sum())} Kgs")

            st.divider()

            _base_cols     = ["Date","OrderId","CustomerPoNo","Category","Customer","Item","GSM",
                              "FabricQty","AccQty","FabricPrice","AccPrice","Status","image_url"]
            _prod_cols     = ["Date","ShootDate","OrderId","CustomerPoNo","Category","Customer","Item","GSM",
                              "FabricQty","AccQty","FabricPrice","AccPrice","Status","image_url"]

            def show_section(label, sdf, cols):
                if sdf.empty:
                    return
                st.markdown(f"**{label}** — Orders: {len(sdf)} | Qty: {int(sdf['FabricQty'].sum())} Kgs")
                c = [x for x in cols if x in sdf.columns]
                st.dataframe(
                    sdf[c].sort_values("OrderId", ascending=False),
                    use_container_width=True, hide_index=True,
                    column_config={
                        "image_url": st.column_config.LinkColumn("Image", display_text="🖼️ View"),
                    }
                )

            show_section("IN PRODUCTION", in_prod_df,   _prod_cols)
            show_section("PENDING",       pending_cdf,   _base_cols)
            if include_dispatched:
                show_section("DISPATCHED", dispatch_cdf, _base_cols)

            st.divider()

            if st.button("📄 Generate Customer Report PDF", type="primary", key="cr_gen"):
                sections = {"In Production": in_prod_df, "Pending": pending_cdf}
                if include_dispatched and not dispatch_cdf.empty:
                    sections["Dispatched"] = dispatch_cdf
                with st.spinner("Generating PDF..."):
                    try:
                        pdf_bytes = build_customer_report_pdf(sel_cust, date_range_label, sections)
                        pdf_name  = f"CustomerReport_{sel_cust.replace(' ','_')}_{date_range_label.replace(' ','_')}.pdf"
                        st.download_button("⬇️ Download Report PDF", pdf_bytes, pdf_name,
                                           "application/pdf", key="cr_dl")
                    except Exception as e:
                        st.error(f"PDF error: {e}")

    # ══════════════════════════════════════════════════════
    #  CUSTOMER PENDING REPORT
    # ══════════════════════════════════════════════════════
     elif rpt_type == "👤 Customer Pending":
        st.markdown("### 👤 Customer Pending Report")

        customers_list = get_customer_list()
        cp_cust = st.selectbox("Select Customer", customers_list, index=None,
                               placeholder="Choose customer...", key="cp_cust")

        if cp_cust:
            cust_key   = cp_cust.upper().strip().replace(" ", "")
            cp_df      = pending_df[pending_df["Customer"] == cust_key].sort_values("OrderId", ascending=False)

            if cp_df.empty:
                st.info(f"No pending orders for **{cp_cust}**")
            else:
                st.success(f"**{len(cp_df)} pending orders** · **{int(cp_df['FabricQty'].sum()):,} KG total**")
                st.divider()

                for _, row in cp_df.iterrows():
                    oid = str(row["OrderId"])
                    po_doc = db.collection("po").document(oid).get()
                    po_d   = po_doc.to_dict() if po_doc.exists else {}

                    with st.expander(f"**{oid}**  |  {row['Item']}  |  {int(row['FabricQty']):,} KG  |  {row['Date']}", expanded=False):
                        r1, r2 = st.columns(2)
                        r1.markdown(f"**Category:** {row['Category']}")
                        r1.markdown(f"**GSM:** {int(row['GSM']) if row['GSM'] else '—'}")
                        r1.markdown(f"**Fabric Qty:** {int(row['FabricQty']):,} KG")
                        r1.markdown(f"**Fabric Price:** ₹{int(row['FabricPrice'])}")
                        r2.markdown(f"**Acc Qty:** {int(row['AccQty'])}")
                        r2.markdown(f"**Acc Price:** ₹{int(row['AccPrice'])}")
                        r2.markdown(f"**Customer PO No:** {po_d.get('customerpono','—')}")

                        if po_d.get("coloursinstructions"):
                            st.markdown(f"**Colours/Instructions:** {po_d['coloursinstructions']}")
                        if po_d.get("accessory"):
                            st.markdown(f"**Accessory Description:** {po_d['accessory']}")
                        if row.get("pdf_url"):
                            st.markdown(f"[📄 View PO PDF]({row['pdf_url']})")
                        elif po_d.get("pdf_url"):
                            st.markdown(f"[📄 View PO PDF]({po_d['pdf_url']})")

    # ══════════════════════════════════════════════════════
    #  DRILL-DOWN TAB
    # ══════════════════════════════════════════════════════
     elif rpt_type == "🔍 Pending Drill-Down":
        if "dd_cat"  not in st.session_state: st.session_state.dd_cat  = None
        if "dd_item" not in st.session_state: st.session_state.dd_item = None

        # ── Tier 1: Category ──
        st.markdown("### Step 1 — Select Category")
        stripe_pend = pending_df[pending_df["Category"] == "STRIPE"]
        plain_pend  = pending_df[pending_df["Category"] == "PLAIN"]

        bc1, bc2, bc3 = st.columns([1, 1, 3])
        with bc1:
            stripe_label = f"🔵 STRIPE\n{len(stripe_pend)} orders · {int(stripe_pend['FabricQty'].sum()):,} qty"
            if st.button(stripe_label, use_container_width=True, key="dd_stripe"):
                st.session_state.dd_cat  = "STRIPE"
                st.session_state.dd_item = None
                st.rerun()
        with bc2:
            plain_label = f"🟠 PLAIN\n{len(plain_pend)} orders · {int(plain_pend['FabricQty'].sum()):,} qty"
            if st.button(plain_label, use_container_width=True, key="dd_plain"):
                st.session_state.dd_cat  = "PLAIN"
                st.session_state.dd_item = None
                st.rerun()

        if st.session_state.dd_cat:
            cat_df = pending_df[pending_df["Category"] == st.session_state.dd_cat]

            # ── Tier 2: Items ──
            st.markdown("---")
            st.markdown(f"### Step 2 — Items in **{st.session_state.dd_cat}** ({len(cat_df)} pending orders)")

            items_grp = (
                cat_df.groupby("Item")
                .agg(Orders=("OrderId", "count"), TotalQty=("FabricQty", "sum"))
                .sort_values("TotalQty", ascending=False)
                .reset_index()
            )

            # Header row
            hc1, hc2, hc3, hc4 = st.columns([4, 1.2, 1.5, 1.2])
            hc1.markdown("**Item**")
            hc2.markdown("**Orders**")
            hc3.markdown("**Total Qty**")
            hc4.markdown("**Action**")
            st.markdown('<hr style="margin:4px 0 8px">', unsafe_allow_html=True)

            for _, row in items_grp.iterrows():
                is_selected = st.session_state.dd_item == row["Item"]
                rc1, rc2, rc3, rc4 = st.columns([4, 1.2, 1.5, 1.2])
                bg = "background:#FFF3E0;border-radius:6px;padding:4px 8px;" if is_selected else "padding:4px 8px;"
                rc1.markdown(f'<div style="{bg}">{"✅ " if is_selected else ""}{row["Item"]}</div>', unsafe_allow_html=True)
                rc2.markdown(f'<div style="{bg}">{int(row["Orders"])}</div>', unsafe_allow_html=True)
                rc3.markdown(f'<div style="{bg}">{int(row["TotalQty"]):,}</div>', unsafe_allow_html=True)
                with rc4:
                    btn_label = "Selected ✓" if is_selected else "View →"
                    if st.button(btn_label, key=f"dd_item_{row['Item']}", use_container_width=True):
                        st.session_state.dd_item = row["Item"]
                        st.rerun()

            # ── Tier 3: Customer + Order Details ──
            if st.session_state.dd_item:
                item_df = cat_df[cat_df["Item"] == st.session_state.dd_item].copy()

                st.markdown("---")

                # Breadcrumb
                st.markdown(
                    f'<div style="background:#FFF3E0;border-left:4px solid #C4956A;'
                    f'padding:10px 16px;border-radius:8px;margin-bottom:14px;">'
                    f'<span style="color:#9A6A40;font-size:12px;">DRILL-DOWN PATH</span><br>'
                    f'<b>Pending</b> › <b>{st.session_state.dd_cat}</b> › <b>{st.session_state.dd_item}</b>'
                    f'<span style="float:right;color:#C4956A;font-size:13px;">'
                    f'{len(item_df)} orders &nbsp;|&nbsp; {int(item_df["FabricQty"].sum()):,} qty</span>'
                    f'</div>',
                    unsafe_allow_html=True
                )

                import re as _re2

                def _get_drive_id(row):
                    fid = str(row.get("image_drive_id", "")).strip()
                    if fid:
                        return fid
                    url = str(row.get("image_url", "")).strip()
                    if url:
                        m = _re2.search(r"/d/([a-zA-Z0-9_-]+)", url)
                        if m:
                            return m.group(1)
                    return ""

                pass  # _fetch_image_bytes defined at module scope below

                # Customer summary
                st.markdown("#### Customer Summary")
                cust_grp = (
                    item_df.groupby("Customer")
                    .agg(Orders=("OrderId", "count"), Qty=("FabricQty", "sum"))
                    .sort_values("Qty", ascending=False)
                    .reset_index()
                )
                cust_grp["Qty"] = cust_grp["Qty"].astype(int)
                st.dataframe(cust_grp, use_container_width=True, hide_index=True)

                st.markdown("#### Order Details")

                for _, row in item_df.sort_values("OrderId", ascending=False).iterrows():
                    drive_id = _get_drive_id(row)

                    with st.container():
                        img_col, det_col = st.columns([1, 3])

                        with img_col:
                            if drive_id:
                                img_bytes = _fetch_image_bytes(drive_id)
                                if img_bytes:
                                    st.image(img_bytes, width=160)
                                else:
                                    st.markdown(
                                        '<div style="width:160px;height:120px;background:#F5EAD8;'
                                        'border-radius:8px;display:flex;align-items:center;'
                                        'justify-content:center;color:#C4956A;font-size:26px;">📷</div>',
                                        unsafe_allow_html=True)
                            else:
                                st.markdown(
                                    '<div style="width:160px;height:120px;background:#F0E8DA;'
                                    'border-radius:8px;display:flex;flex-direction:column;align-items:center;'
                                    'justify-content:center;color:#B09070;font-size:24px;">'
                                    '📷<br><span style="font-size:10px;margin-top:4px;">No image</span></div>',
                                    unsafe_allow_html=True)

                        with det_col:
                            st.markdown(
                                f'<div style="background:#FFFAF4;border:1px solid #E8D0A8;'
                                f'border-radius:10px;padding:12px 16px;">'
                                f'<div style="display:flex;justify-content:space-between;margin-bottom:8px;">'
                                f'<span style="font-size:16px;font-weight:700;color:#6B3F10;">Order #{row.get("OrderId","")}</span>'
                                f'<span style="font-size:12px;color:#9A6A40;">{row.get("Date","")}</span>'
                                f'</div>'
                                f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:4px 20px;font-size:13px;">'
                                f'<span><b>Customer:</b> {row.get("Customer","")}</span>'
                                f'<span><b>GSM:</b> {int(row.get("GSM",0))}</span>'
                                f'<span><b>Fabric Qty:</b> {int(row.get("FabricQty",0)):,}</span>'
                                f'<span><b>Fabric Price:</b> {int(row.get("FabricPrice",0))}</span>'
                                f'<span><b>Acc Qty:</b> {int(row.get("AccQty",0))}</span>'
                                f'<span><b>Acc Price:</b> {int(row.get("AccPrice",0))}</span>'
                                f'</div>'
                                f'</div>',
                                unsafe_allow_html=True
                            )

                        st.markdown('<hr style="margin:8px 0;border-color:#EAD0A8;">', unsafe_allow_html=True)

                if st.button("← Back to item list", key="dd_back"):
                    st.session_state.dd_item = None
                    st.rerun()

    # ══════════════════════════════════════════════════════
    #  PENDING BY ITEM TAB
    # ══════════════════════════════════════════════════════
     elif rpt_type == "📦 Pending by Item":
        import re as _re3

        # ── Full-size image dialog ──
        @st.dialog("Product Image", width="large")
        def _show_full_image(drive_id: str, order_id: str):
            st.caption(f"Order #{order_id}")
            img_bytes = _fetch_image_bytes(drive_id)
            if img_bytes:
                st.image(img_bytes, use_container_width=True)
            else:
                st.warning("Image could not be loaded from Drive.")

        def _drive_id_from_row(row):
            fid = str(row.get("image_drive_id", "")).strip()
            if fid:
                return fid
            url = str(row.get("image_url", "")).strip()
            if url:
                m = _re3.search(r"/d/([a-zA-Z0-9_-]+)", url)
                if m:
                    return m.group(1)
            return ""

        # ── Page header ──
        st.markdown("### Pending Orders by Item")

        # Item dropdown from item_master
        item_list = get_item_list()
        if not item_list:
            st.warning("No items in Item Master yet.")
            st.stop()

        sel_item = st.selectbox(
            "Select Item",
            ["— select an item —"] + item_list,
            key="pir_sel_item"
        )

        if sel_item and sel_item != "— select an item —":
            item_pend = pending_df[pending_df["Item"].str.upper() == sel_item.upper()].copy()

            if item_pend.empty:
                st.info(f"No pending orders for **{sel_item}**")
            else:
                # Summary banner
                st.markdown(
                    f'<div style="background:#FFF3E0;border-left:4px solid #C4956A;'
                    f'padding:10px 18px;border-radius:8px;margin:10px 0 16px;">'
                    f'<b>{sel_item}</b> &nbsp;·&nbsp; '
                    f'<b>{len(item_pend)}</b> pending orders &nbsp;|&nbsp; '
                    f'<b>{int(item_pend["FabricQty"].sum()):,}</b> qty</div>',
                    unsafe_allow_html=True
                )

                # ── Customer summary — clickable ──
                st.markdown("#### 👥 Customer Summary")
                st.caption("Click a customer row to see their order details below.")
                cust_grp = (
                    item_pend.groupby("Customer")
                    .agg(Orders=("OrderId","count"), Qty=("FabricQty","sum"))
                    .sort_values("Qty", ascending=False)
                    .reset_index()
                )
                cust_grp["Qty"] = cust_grp["Qty"].astype(int)

                cust_sel = st.dataframe(
                    cust_grp, use_container_width=True, hide_index=True,
                    on_select="rerun", selection_mode="single-row",
                    key="pir_cust_sel"
                )

                # Determine which customer is selected
                sel_rows = cust_sel.selection.rows if hasattr(cust_sel, "selection") else []
                if sel_rows:
                    sel_customer = cust_grp.iloc[sel_rows[0]]["Customer"]
                    orders_to_show = item_pend[item_pend["Customer"] == sel_customer]
                    st.markdown(f"---")
                    st.markdown(f"#### Order Details — **{sel_customer}** ({len(orders_to_show)} orders)")
                else:
                    orders_to_show = None
                    st.info("Click a customer row above to view their order details.")

                if orders_to_show is not None and not orders_to_show.empty:
                    for _, row in orders_to_show.sort_values("OrderId", ascending=False).iterrows():
                        drive_id = _drive_id_from_row(row)
                        img_col, det_col = st.columns([1, 3])

                        with img_col:
                            if drive_id:
                                img_bytes = _fetch_image_bytes(drive_id)
                                if img_bytes:
                                    st.image(img_bytes, width=160)
                                    if st.button("🔍 Full Size", key=f"pir_full_{row['OrderId']}",
                                                 use_container_width=True):
                                        _show_full_image(drive_id, str(row["OrderId"]))
                                else:
                                    st.markdown(
                                        '<div style="width:160px;height:120px;background:#F5EAD8;'
                                        'border-radius:8px;display:flex;flex-direction:column;align-items:center;'
                                        'justify-content:center;color:#B09070;font-size:24px;">'
                                        '📷<br><span style="font-size:10px;margin-top:4px;">Unavailable</span></div>',
                                        unsafe_allow_html=True)
                            else:
                                st.markdown(
                                    '<div style="width:160px;height:120px;background:#F0E8DA;'
                                    'border-radius:8px;display:flex;flex-direction:column;align-items:center;'
                                    'justify-content:center;color:#B09070;font-size:24px;">'
                                    '📷<br><span style="font-size:10px;margin-top:4px;">No image</span></div>',
                                    unsafe_allow_html=True)

                        with det_col:
                            st.markdown(
                                f'<div style="background:#FFFAF4;border:1px solid #E8D0A8;'
                                f'border-radius:10px;padding:12px 16px;">'
                                f'<div style="display:flex;justify-content:space-between;margin-bottom:8px;">'
                                f'<span style="font-size:16px;font-weight:700;color:#6B3F10;">'
                                f'Order #{row.get("OrderId","")}</span>'
                                f'<span style="font-size:12px;color:#9A6A40;">{row.get("Date","")}</span>'
                                f'</div>'
                                f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:6px 24px;font-size:13px;">'
                                f'<span><b>Category:</b> {row.get("Category","")}</span>'
                                f'<span><b>GSM:</b> {int(row.get("GSM",0))}</span>'
                                f'<span><b>Fabric Qty:</b> {int(row.get("FabricQty",0)):,}</span>'
                                f'<span><b>Fabric Price:</b> ₹{int(row.get("FabricPrice",0))}</span>'
                                f'<span><b>Acc Qty:</b> {int(row.get("AccQty",0))}</span>'
                                f'<span><b>Acc Price:</b> ₹{int(row.get("AccPrice",0))}</span>'
                                f'</div>'
                                + (f'<div style="margin-top:8px;">'
                                   f'<a href="{row.get("pdf_url","")}" target="_blank" '
                                   f'style="color:#C4956A;font-size:13px;">📄 Open PO PDF</a></div>'
                                   if row.get("pdf_url") else "")
                                + f'</div>',
                                unsafe_allow_html=True
                            )
                        st.markdown('<hr style="margin:10px 0;border-color:#EAD0A8;">', unsafe_allow_html=True)

     elif rpt_type == "🔄 Processing Report":
        import plotly.express as px

        st.markdown("### 🔄 Processing Report")
        st.caption("Orders where Process Out is done but Process Inward has not yet happened.")

        if st.button("🔄 Refresh", key="proc_rpt_refresh"):
            st.rerun()

        with st.spinner("Loading..."):
            out_docs = [d.to_dict() for d in db.collection("process_out").stream()]
            in_docs  = [d.to_dict() for d in db.collection("process_inward").stream()]

        # Lot Nos that have been received back
        received_lots = {d.get("LotNo","").upper().strip() for d in in_docs}

        # Filter: process_out lots NOT yet received
        pending_lots = [d for d in out_docs
                        if d.get("LotNo","").upper().strip() not in received_lots]

        if not pending_lots:
            st.success("✅ No lots currently pending — all sent lots have been received back.")
        else:
            pr_df = pd.DataFrame(pending_lots)

            # KPI tiles
            total_lots = len(pr_df)
            total_qty  = pr_df["Qnty"].apply(lambda x: float(x or 0)).sum()
            parties    = pr_df["PartyName"].nunique() if "PartyName" in pr_df.columns else 0

            k1, k2, k3 = st.columns(3)
            k1.metric("Lots On Processing",   total_lots)
            k2.metric("Total Qty (kg)",        f"{total_qty:,.2f}")
            k3.metric("Processors Involved",   parties)

            st.divider()

            # Optional filter by party
            if "PartyName" in pr_df.columns:
                party_opts = ["All Processors"] + sorted(pr_df["PartyName"].dropna().unique().tolist())
                sel_party  = st.selectbox("Filter by Processor", party_opts, key="pr_party_filter")
                if sel_party != "All Processors":
                    pr_df = pr_df[pr_df["PartyName"] == sel_party]

            # Bar chart — qty by party
            if "PartyName" in pr_df.columns and not pr_df.empty:
                grp = (pr_df.groupby("PartyName")["Qnty"]
                       .apply(lambda x: sum(float(v or 0) for v in x))
                       .reset_index())
                grp.columns = ["Processor", "Qty"]
                fig = px.bar(grp, x="Processor", y="Qty",
                             title="Pending Qty by Processor",
                             color="Qty", color_continuous_scale="Oranges")
                fig.update_layout(height=260, margin=dict(t=40, b=60), showlegend=False)
                fig.update_xaxes(tickangle=30)
                st.plotly_chart(fig, use_container_width=True)

            st.divider()

            # Full table
            want = ["ChallanNo", "Date", "PartyName", "OrderId", "LotNo",
                    "Customer name", "Item", "Colour", "Roll", "Qnty", "Process", "DiaGsm"]
            show = [c for c in want if c in pr_df.columns]

            rename_map = {"Customer name": "Customer", "PartyName": "Processor",
                          "DiaGsm": "Dia/GSM"}
            disp_df = (pr_df[show]
                       .rename(columns=rename_map)
                       .sort_values(["ChallanNo","LotNo"], ascending=True))

            st.markdown(f"**{len(disp_df)} lots pending inward** — sorted by Challan No")
            st.dataframe(disp_df, use_container_width=True, hide_index=True)

     elif rpt_type == "📦 Part Dispatched":
        st.markdown("### 📦 Part Dispatched Orders")
        st.caption("Orders where Packing List quantity is less than PO quantity (fabric or accessory).")

        if st.button("🔄 Refresh", key="pd_refresh"):
            st.rerun()

        pd_df = df[df["Status"] == "Part Dispatched"].copy()

        if pd_df.empty:
            st.success("✅ No part-dispatched orders found.")
        else:
            # Compute remaining quantities
            pd_df["RemainingFabric"] = (pd_df["FabricQty"] - pd_df["PackedFabricQty"]).round(2)
            pd_df["RemainingAcc"]    = (pd_df["AccQty"]     - pd_df["PackedAccQty"]).round(2)

            # KPI
            pk1, pk2, pk3 = st.columns(3)
            pk1.metric("Part Dispatched Orders",    len(pd_df))
            pk2.metric("Total Remaining Fabric Qty", f"{pd_df['RemainingFabric'].sum():,.2f}")
            pk3.metric("Total Remaining Acc Qty",    f"{pd_df['RemainingAcc'].sum():,.2f}")

            st.divider()

            disp = pd_df[[
                "OrderId","Customer","Item","Category","Date",
                "FabricQty","PackedFabricQty","RemainingFabric",
                "AccQty","PackedAccQty","RemainingAcc",
            ]].rename(columns={
                "FabricQty":       "PO Fabric Qty",
                "PackedFabricQty": "Packed Fabric",
                "RemainingFabric": "Remaining Fabric",
                "AccQty":          "PO Acc Qty",
                "PackedAccQty":    "Packed Acc",
                "RemainingAcc":    "Remaining Acc",
            }).sort_values("OrderId", ascending=False)

            st.dataframe(disp, use_container_width=True, hide_index=True)

            # Highlight which type of shortfall
            st.markdown("**Shortfall breakdown:**")
            fab_short = pd_df[pd_df["RemainingFabric"] > 0]
            acc_short = pd_df[pd_df["RemainingAcc"]    > 0]
            sc1, sc2 = st.columns(2)
            sc1.metric("Fabric not fully dispatched", len(fab_short))
            sc2.metric("Accessory not fully dispatched", len(acc_short))

     elif rpt_type == "🏠 In House Finishing":
        st.markdown("### 🏠 In House Finishing / Packing Report")
        st.caption("Orders received back from processing and currently in-house for finishing or packing.")

        if st.button("🔄 Refresh", key="ih_refresh"):
            st.rerun()

        ih_df = df[df["Status"] == "In House Finishing/Packing"].copy()

        if ih_df.empty:
            st.success("✅ No orders currently in-house finishing/packing.")
        else:
            # ── KPI ──
            k1, k2 = st.columns(2)
            k1.metric("Orders In House", len(ih_df))
            k2.metric("Total Fabric Qty", f"{ih_df['FabricQty'].sum():,.0f} Kgs")

            st.divider()

            # ── Search ──
            ih_search = st.text_input("🔍 Search Order ID or Customer", key="ih_search")
            if ih_search.strip():
                q = ih_search.strip().upper()
                ih_df = ih_df[
                    ih_df["OrderId"].astype(str).str.upper().str.contains(q, na=False) |
                    ih_df["Customer"].str.upper().str.contains(q, na=False)
                ]

            st.markdown(f"**{len(ih_df)} orders** — sorted by Order ID")

            # ── Table with PO PDF link ──
            disp_df = ih_df[[
                "OrderId","CustomerPoNo","Date","ShootDate",
                "Customer","Item","Category","GSM","FabricQty","pdf_url",
            ]].rename(columns={
                "CustomerPoNo": "Cust PO No",
                "ShootDate":    "Shoot Date",
                "FabricQty":    "Fabric Qty",
                "pdf_url":      "PO PDF",
            }).sort_values("OrderId", ascending=False)

            st.dataframe(
                disp_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "PO PDF": st.column_config.LinkColumn("PO PDF", display_text="📄 View"),
                }
            )

     elif rpt_type == "__removed__":
        pass  # Print Packing List moved to Packing form tab
        pl_oid = st.text_input("Enter Order ID", key="pl_print_oid", placeholder="e.g. 1001")

        if pl_oid.strip():
            pl_docs = list(db.collection("PackingListRaw")
                           .where("OrderId", "==", pl_oid.strip()).stream())
            if not pl_docs:
                st.error("No packing list found for this Order ID")
            else:
                pl_data = pl_docs[0].to_dict()

                # ── Parse helpers ──
                def _parse_pack_line(line):
                    if ":" not in line:
                        return None
                    colour, wstr = line.split(":", 1)
                    ws = [w.strip() for w in wstr.split(",") if w.strip()]
                    try:
                        total = round(sum(float(w) for w in ws), 2)
                    except Exception:
                        total = 0.0
                    return {"colour": colour.strip(), "weights": ws,
                            "rolls": len(ws), "total": total}

                def _section_rows_html(lines):
                    if not lines:
                        return "<tr><td colspan='4' style='text-align:center;color:#999;'>No data</td></tr>"
                    rows = ""
                    for line in lines:
                        p = _parse_pack_line(line)
                        if not p:
                            continue
                        wt_str = ", ".join(f"{w} Kg" for w in p["weights"])
                        rows += (f"<tr>"
                                 f"<td><b>{p['colour']}</b></td>"
                                 f"<td style='text-align:center'>{p['rolls']}</td>"
                                 f"<td style='text-align:right'>{p['total']}</td>"
                                 f"<td>{wt_str}</td>"
                                 f"</tr>")
                    return rows

                f_lines = [l for l in pl_data.get("FabricDetails","").splitlines()  if l.strip()]
                a_lines = [l for l in pl_data.get("AccessoryDetails","").splitlines() if l.strip()]

                f_parsed = [_parse_pack_line(l) for l in f_lines if _parse_pack_line(l)]
                a_parsed = [_parse_pack_line(l) for l in a_lines if _parse_pack_line(l)]

                f_total_wt    = round(sum(p["total"] for p in f_parsed), 2)
                f_total_rolls = sum(p["rolls"] for p in f_parsed)
                a_total_wt    = round(sum(p["total"] for p in a_parsed), 2)
                a_total_rolls = sum(p["rolls"] for p in a_parsed)
                grand_wt      = round(f_total_wt + a_total_wt, 2)
                grand_rolls   = f_total_rolls + a_total_rolls

                raw_date = pl_data.get("Date","")
                try:
                    disp_date = _pldt.strptime(raw_date, "%Y-%m-%d").strftime("%d/%m/%Y")
                except Exception:
                    disp_date = raw_date

                # ── HTML packing list ──
                html = f"""
                <style>
                  @media print {{
                    .no-print {{ display: none !important; }}
                    body {{ margin: 0; }}
                  }}
                  .pl-wrap {{
                    font-family: Arial, sans-serif;
                    font-size: 13px;
                    max-width: 900px;
                    padding: 20px;
                    color: #222;
                  }}
                  .pl-header {{
                    display: flex;
                    justify-content: space-between;
                    align-items: flex-start;
                    margin-bottom: 20px;
                    border-bottom: 2px solid #C4956A;
                    padding-bottom: 12px;
                  }}
                  .pl-title {{ font-size: 22px; font-weight: 700; margin: 0; }}
                  .pl-company {{ color: #888; margin: 3px 0 0; font-size: 13px; }}
                  .pl-meta td {{ padding: 2px 6px; font-size: 13px; }}
                  .pl-meta td:first-child {{ font-weight: 700; color: #555; }}
                  .pl-section {{ margin-top: 18px; }}
                  .pl-section h4 {{
                    font-size: 14px; margin: 0 0 6px;
                    border-bottom: 1px solid #ddd; padding-bottom: 4px;
                    color: #5C3410;
                  }}
                  .pl-table {{
                    width: 100%; border-collapse: collapse; font-size: 12px;
                  }}
                  .pl-table th {{
                    background: #f0f0f0; border: 1px solid #ccc;
                    padding: 6px 8px; text-align: left;
                  }}
                  .pl-table td {{
                    border: 1px solid #ddd; padding: 5px 8px;
                    vertical-align: top;
                  }}
                  .pl-table tr:nth-child(even) td {{ background: #fafafa; }}
                  .pl-summary {{
                    display: grid;
                    grid-template-columns: 1fr 1fr 1fr;
                    gap: 12px;
                    margin-top: 20px;
                  }}
                  .pl-sum-box {{
                    border: 1px solid #ddd;
                    border-radius: 6px;
                    padding: 10px 14px;
                  }}
                  .pl-sum-label {{ font-size: 11px; color: #888; margin: 0 0 4px; }}
                  .pl-sum-val {{ font-size: 18px; font-weight: 700; margin: 0; }}
                  .pl-sum-sub {{ font-size: 12px; color: #666; margin: 2px 0 0; }}
                  .print-btn {{
                    background: #C4956A; color: white; border: none;
                    padding: 10px 28px; font-size: 14px; border-radius: 8px;
                    cursor: pointer; margin-bottom: 16px; font-weight: 600;
                  }}
                  .print-btn:hover {{ background: #A07848; }}
                </style>

                <script>
                function printPackingList() {{
                    var content  = document.getElementById('pl-content').outerHTML;
                    var style    = document.querySelector('style').outerHTML;
                    var win = window.open('', '_blank', 'width=960,height=800');
                    win.document.write(
                        '<html><head><title>Packing List</title>' + style + '</head>' +
                        '<body style="margin:20px;font-family:Arial,sans-serif;">' +
                        content + '</body></html>'
                    );
                    win.document.close();
                    win.focus();
                    setTimeout(function() {{ win.print(); win.close(); }}, 400);
                }}
                </script>

                <button class="print-btn" onclick="printPackingList()">
                  🖨️ Print
                </button>

                <div class="pl-wrap" id="pl-content">
                  <div class="pl-header">
                    <div>
                      <p class="pl-title">Packing List</p>
                      <p class="pl-company">{COMPANY_NAME}</p>
                    </div>
                    <table class="pl-meta">
                      <tr><td>OrderID:</td><td><b>{pl_data.get('OrderId','')}</b></td></tr>
                      <tr><td>Date:</td><td><b>{disp_date}</b></td></tr>
                      <tr><td>Customer:</td><td><b>{pl_data.get('Customer name','')}</b></td></tr>
                      <tr><td>Item:</td><td><b>{pl_data.get('Item','')}</b></td></tr>
                    </table>
                  </div>

                  <div class="pl-section">
                    <h4>Fabric</h4>
                    <table class="pl-table">
                      <thead><tr>
                        <th>Colour</th><th>Rolls</th><th>Total Wt</th><th>Roll Weights</th>
                      </tr></thead>
                      <tbody>{_section_rows_html(f_lines)}</tbody>
                    </table>
                  </div>

                  <div class="pl-section">
                    <h4>Accessory</h4>
                    <table class="pl-table">
                      <thead><tr>
                        <th>Colour</th><th>Rolls</th><th>Total Wt</th><th>Roll Weights</th>
                      </tr></thead>
                      <tbody>{_section_rows_html(a_lines)}</tbody>
                    </table>
                  </div>

                  <div class="pl-summary">
                    <div class="pl-sum-box">
                      <p class="pl-sum-label">Fabric Total</p>
                      <p class="pl-sum-val">{f_total_wt} kg</p>
                      <p class="pl-sum-sub">Rolls: {f_total_rolls}</p>
                    </div>
                    <div class="pl-sum-box">
                      <p class="pl-sum-label">Accessory Total</p>
                      <p class="pl-sum-val">{a_total_wt} kg</p>
                      <p class="pl-sum-sub">Rolls: {a_total_rolls}</p>
                    </div>
                    <div class="pl-sum-box">
                      <p class="pl-sum-label">Grand Total (Fabric + Accessory)</p>
                      <p class="pl-sum-val">{grand_wt} kg</p>
                      <p class="pl-sum-sub">Rolls: {grand_rolls}</p>
                    </div>
                  </div>
                </div>
                """

                _plcomps.html(html, height=900, scrolling=True)


# ═════════════════════════════════════════════════════════
#  IMPORT DATA
# ═════════════════════════════════════════════════════════
# ═════════════════════════════════════════════════════════
#  EDIT PO
# ═════════════════════════════════════════════════════════
elif menu == "Edit PO":
    st.markdown('<div class="page-header"><h1>✏️ Edit PO</h1></div>', unsafe_allow_html=True)

    search_id = st.text_input("Enter Order ID to edit", key="edit_po_id")

    if search_id.strip():
        po_doc = db.collection("po").document(search_id.strip()).get()
        if not po_doc.exists:
            st.error("PO not found")
        else:
            d = po_doc.to_dict()
            st.success(f"PO {search_id} found — edit fields below and click Save")

            customers = get_customer_list()
            items     = get_item_list()

            # Normalise stored values for comparison
            po_category = (d.get("Category","") or "").upper().strip()
            po_customer = (d.get("Customer name","") or "").upper().strip().replace(" ", "")
            po_item     = (d.get("Item","") or "").upper().strip()

            ec1, ec2 = st.columns(2)
            with ec1:
                e_category = st.selectbox("Category", ["STRIPE","PLAIN"],
                                          index=["STRIPE","PLAIN"].index(po_category)
                                          if po_category in ["STRIPE","PLAIN"] else 0,
                                          key="epo_cat")
                e_customer = st.selectbox("Customer", customers,
                                          index=customers.index(po_customer)
                                          if po_customer in customers else 0,
                                          key="epo_cust") if customers else st.text_input("Customer", value=po_customer, key="epo_cust_txt")
                e_item     = st.selectbox("Item", items,
                                          index=items.index(po_item)
                                          if po_item in items else 0,
                                          key="epo_item") if items else st.text_input("Item", value=po_item, key="epo_item_txt")
                from datetime import datetime as _edt, date as _edate
                try:
                    e_date_val = _edt.strptime(d.get("Date",""), "%Y-%m-%d").date()
                except Exception:
                    e_date_val = _edate.today()
                e_date   = st.date_input("Date", value=e_date_val, format="DD/MM/YYYY", key="epo_date")
                e_gsm    = st.number_input("GSM",          min_value=0, value=int(d.get("gsm") or 0),           key="epo_gsm")
                e_fqty   = st.number_input("Fabric Qty",   min_value=0, value=int(d.get("facricqnty") or 0),    key="epo_fqty")
                e_aqty   = st.number_input("Accessory Qty",min_value=0, value=int(d.get("accessoryqnty") or 0), key="epo_aqty")
            with ec2:
                e_fprice  = st.number_input("Fabric Price",    min_value=0, value=int(d.get("fabricprice") or 0),    key="epo_fprice")
                e_aprice  = st.number_input("Accessory Price", min_value=0, value=int(d.get("accessoryprice") or 0), key="epo_aprice")
                e_colours = st.text_area("Colours / Instructions", value=d.get("coloursinstructions",""),             key="epo_colours")
                e_acc     = st.text_area("Accessory Description",  value=d.get("accessory",""),                       key="epo_acc")
                e_custpo  = st.text_input("Customer PO No",         value=d.get("customerpono",""),                   key="epo_custpo")

            # ── Product image section ──
            st.divider()
            st.markdown("#### Product Image")
            img_col, upload_col = st.columns([1, 2])

            existing_drive_id  = d.get("image_drive_id", "")
            existing_image_url = d.get("image", "")

            with img_col:
                st.markdown("**Current Image**")
                if existing_drive_id:
                    cur_img = _fetch_image_bytes(existing_drive_id)
                    if cur_img:
                        st.image(cur_img, width=200)
                    else:
                        st.caption("Cannot load from Drive")
                elif existing_image_url:
                    st.image(existing_image_url, width=200)
                else:
                    st.markdown(
                        '<div style="width:200px;height:150px;background:#F5EAD8;border-radius:8px;'
                        'display:flex;align-items:center;justify-content:center;'
                        'color:#B09070;font-size:28px;">📷</div>',
                        unsafe_allow_html=True)

            with upload_col:
                st.markdown("**Upload New Image** *(replaces current)*")
                new_image = st.file_uploader("", type=["jpg","jpeg","png","webp"], key="epo_img")
                if new_image:
                    new_img_bytes = new_image.read()
                    st.image(io.BytesIO(new_img_bytes), width=200, caption="New image preview")

            if st.button("💾 Save Changes", type="primary", key="epo_save"):
                update_data = {
                    "Category":            e_category,
                    "Customer name":       e_customer,
                    "Item":                e_item,
                    "Date":                e_date.strftime("%Y-%m-%d"),
                    "gsm":                 e_gsm,
                    "facricqnty":          e_fqty,
                    "fabricprice":         e_fprice,
                    "accessoryqnty":       e_aqty,
                    "accessoryprice":      e_aprice,
                    "coloursinstructions": e_colours,
                    "accessory":           e_acc,
                    "customerpono":        e_custpo,
                }

                if new_image:
                    with st.spinner("Uploading new image to Firebase Storage..."):
                        try:
                            ext       = new_image.name.rsplit(".", 1)[-1]
                            image_url = upload_to_firebase_storage(
                                new_img_bytes,
                                f"po_images/PO_{search_id.strip()}_image.{ext}",
                                new_image.type,
                            )
                            update_data["image"]          = image_url
                            update_data["image_drive_id"] = ""
                            _fetch_image_bytes.clear()   # clear cache so new image shows
                        except Exception as e:
                            st.warning(f"Image upload failed: {e}")

                db.collection("po").document(search_id.strip()).update(update_data)
                st.success(f"✅ PO {search_id} updated successfully")

            # ── Delete PO ──
            st.divider()
            st.markdown("#### 🗑️ Delete PO")
            confirm_del = st.checkbox(
                f"I confirm I want to permanently delete PO **{search_id.strip()}**",
                key="epo_del_confirm"
            )
            if st.button("🗑️ Delete PO", type="secondary", key="epo_del_btn", disabled=not confirm_del):
                with st.spinner("Deleting..."):
                    try:
                        db.collection("po").document(search_id.strip()).delete()
                        st.success(f"✅ PO **{search_id.strip()}** deleted successfully.")
                        st.session_state.pop("epo_del_confirm", None)
                    except Exception as _de:
                        st.error(f"Delete failed: {_de}")


# ═════════════════════════════════════════════════════════
#  EDIT PACKING LIST
# ═════════════════════════════════════════════════════════
elif menu == "Edit Packing List":
    st.markdown('<div class="page-header"><h1>✏️ Edit Packing List</h1></div>', unsafe_allow_html=True)

    search_oid = st.text_input("Enter Order ID", key="edit_pack_oid")

    if search_oid.strip():
        pack_docs = list(db.collection("PackingListRaw")
                         .where("OrderId", "==", search_oid.strip()).stream())
        if not pack_docs:
            st.error("No packing list found for this Order ID")
        else:
            pack_doc  = pack_docs[0]
            pack_data = pack_doc.to_dict()
            raw_id    = pack_doc.id

            st.success(f"Packing List found (Raw ID: {raw_id})")

            ep1, ep2 = st.columns(2)
            with ep1:
                e_customer = st.text_input("Customer Name",
                                           value=pack_data.get("Customer name",""), key="epl_cust")
                e_item     = st.text_input("Item",
                                           value=pack_data.get("Item",""),          key="epl_item")
            with ep2:
                from datetime import datetime as _epdt, date as _epdate
                try:
                    ep_date_val = _epdt.strptime(pack_data.get("Date",""), "%Y-%m-%d").date()
                except Exception:
                    ep_date_val = _epdate.today()
                e_pack_date = st.date_input("Date", value=ep_date_val, format="DD/MM/YYYY", key="epl_date")

            st.markdown("**Fabric Details** *(format: COLOUR: w1,w2,w3)*")
            e_fabric = st.text_area("Fabric Details", value=pack_data.get("FabricDetails",""),
                                    height=150, key="epl_fabric")

            st.markdown("**Accessory Details** *(format: COLOUR: w1,w2,w3)*")
            e_acc    = st.text_area("Accessory Details", value=pack_data.get("AccessoryDetails",""),
                                    height=100, key="epl_acc")

            if st.button("💾 Save Changes", type="primary", key="epl_save"):
                db.collection("PackingListRaw").document(raw_id).update({
                    "Customer name":    e_customer.strip().upper(),
                    "Item":             e_item.strip(),
                    "Date":             e_pack_date.strftime("%Y-%m-%d"),
                    "FabricDetails":    e_fabric.strip(),
                    "AccessoryDetails": e_acc.strip(),
                })
                st.success(f"✅ Packing List for Order {search_oid} updated successfully")


# ═════════════════════════════════════════════════════════
#  CANCEL SHOOT ORDER
# ═════════════════════════════════════════════════════════
# ═════════════════════════════════════════════════════════
#  DELETE PACKING LIST
# ═════════════════════════════════════════════════════════
elif menu == "Delete Packing List":
    st.markdown('<div class="page-header"><h1>🗑️ Delete Packing List</h1></div>', unsafe_allow_html=True)

    del_oid = st.text_input("Enter Order ID", key="del_pack_oid")

    if del_oid.strip():
        del_docs = list(db.collection("PackingListRaw")
                        .where("OrderId", "==", del_oid.strip()).stream())

        if not del_docs:
            st.error("No packing list found for this Order ID")
        else:
            del_data = del_docs[0].to_dict()
            del_id   = del_docs[0].id

            # Show summary of what will be deleted
            st.warning("⚠️ You are about to permanently delete this packing list. This cannot be undone.")
            dc1, dc2 = st.columns(2)
            dc1.text_input("Customer",  value=del_data.get("Customer name",""), disabled=True, key="dlp_cust")
            dc1.text_input("Item",      value=del_data.get("Item",""),          disabled=True, key="dlp_item")
            dc2.text_input("Order ID",  value=del_data.get("OrderId",""),       disabled=True, key="dlp_oid")
            dc2.text_input("Date",      value=del_data.get("Date",""),          disabled=True, key="dlp_date")

            confirm_del = st.checkbox("I confirm I want to delete this packing list", key="dlp_confirm")

            if confirm_del:
                if st.button("🗑️ Delete Packing List", type="primary", key="dlp_submit"):
                    db.collection("PackingListRaw").document(del_id).delete()
                    st.success(f"✅ Packing List for Order {del_oid} deleted successfully.")
                    if "del_pack_oid" in st.session_state:
                        del st.session_state["del_pack_oid"]
                    st.rerun()


# ═════════════════════════════════════════════════════════
#  EDIT PROCESS OUT
# ═════════════════════════════════════════════════════════
elif menu == "Edit Process Out":
    st.markdown('<div class="page-header"><h1>✏️ Edit Process Out</h1></div>', unsafe_allow_html=True)

    epo_challan = st.text_input("Enter Challan No", key="epo_challan_no")

    if epo_challan.strip():
        po_lots = [doc for doc in db.collection("process_out").stream()
                   if doc.to_dict().get("ChallanNo","") == epo_challan.strip()]

        if not po_lots:
            st.error("No Process Out records found for this Challan No")
        else:
            first = po_lots[0].to_dict()
            st.success(f"Found {len(po_lots)} lot(s) for Challan {epo_challan.strip()}")

            # ── Editable challan header ──
            st.markdown("#### Challan Header")
            eh1, eh2, eh3 = st.columns(3)
            with eh1:
                from datetime import datetime as _epdt2, date as _epdate2
                try:
                    epo_date_val = _epdt2.strptime(first.get("Date",""), "%Y-%m-%d").date()
                except Exception:
                    epo_date_val = _epdate2.today()
                epo_date = st.date_input("Date", value=epo_date_val, format="DD/MM/YYYY", key="epo_hdr_date")
            with eh2:
                processors = get_processor_list()
                epo_party  = st.selectbox("Processor / Party", processors,
                                          index=processors.index(first.get("PartyName",""))
                                          if first.get("PartyName","") in processors else 0,
                                          key="epo_hdr_party") if processors else st.text_input(
                                              "Party", value=first.get("PartyName",""), key="epo_hdr_party_txt")
            with eh3:
                epo_vehicle = st.text_input("Vehicle No", value=first.get("VehicleNo",""), key="epo_hdr_veh")

            st.divider()

            # ── Editable lots ──
            st.markdown("#### Lots")
            import re as _epo_re
            def _epo_extract_oid(lot_no):
                m = _epo_re.match(r'^(\d+)', lot_no.strip().upper())
                return m.group(1) if m else ""

            lot_updates = {}
            for doc in po_lots:
                lot    = doc.to_dict()
                lot_no = lot.get("LotNo","")

                # ── Per-lot session state init ──
                if f"epo_ln_{doc.id}"       not in st.session_state:
                    st.session_state[f"epo_ln_{doc.id}"]       = lot_no
                if f"epo_ln_prev_{doc.id}"  not in st.session_state:
                    st.session_state[f"epo_ln_prev_{doc.id}"]  = lot_no
                if f"epo_oid_drv_{doc.id}"  not in st.session_state:
                    st.session_state[f"epo_oid_drv_{doc.id}"]  = lot.get("OrderId","")
                if f"epo_cust_drv_{doc.id}" not in st.session_state:
                    st.session_state[f"epo_cust_drv_{doc.id}"] = lot.get("Customer name","")
                if f"epo_it_{doc.id}"       not in st.session_state:
                    st.session_state[f"epo_it_{doc.id}"]       = lot.get("Item","")

                # ── Detect Lot No change and re-derive OrderId + Customer + Item ──
                current_ln = st.session_state[f"epo_ln_{doc.id}"]
                if current_ln != st.session_state[f"epo_ln_prev_{doc.id}"]:
                    new_oid = _epo_extract_oid(current_ln)
                    st.session_state[f"epo_oid_drv_{doc.id}"] = new_oid
                    if new_oid:
                        _po = db.collection("po").document(new_oid).get()
                        if _po.exists:
                            _pod = _po.to_dict()
                            st.session_state[f"epo_cust_drv_{doc.id}"] = _pod.get("Customer name","")
                            st.session_state[f"epo_it_{doc.id}"]        = _pod.get("Item","")
                        else:
                            st.session_state[f"epo_cust_drv_{doc.id}"] = ""
                    else:
                        st.session_state[f"epo_cust_drv_{doc.id}"] = ""
                    st.session_state[f"epo_ln_prev_{doc.id}"] = current_ln

                derived_oid  = st.session_state[f"epo_oid_drv_{doc.id}"]
                derived_cust = st.session_state[f"epo_cust_drv_{doc.id}"]

                with st.expander(f"Lot: {lot_no}  |  Order: {lot.get('OrderId','')}  |  {lot.get('Colour','')}",
                                 expanded=False):
                    lc1, lc2 = st.columns(2)
                    with lc1:
                        e_lot_no = st.text_input("Lot No", key=f"epo_ln_{doc.id}")
                        # Set session state before widget so value= is respected each render
                        st.session_state[f"epo_oi_disp_{doc.id}"] = derived_oid
                        st.text_input("Order ID (auto)", key=f"epo_oi_disp_{doc.id}", disabled=True)
                        st.session_state[f"epo_cu_disp_{doc.id}"] = derived_cust
                        st.text_input("Customer", key=f"epo_cu_disp_{doc.id}", disabled=True)
                        e_item = st.text_input("Item", key=f"epo_it_{doc.id}")
                    with lc2:
                        e_colour  = st.text_input("Colour",    value=lot.get("Colour",""),                       key=f"epo_col_{doc.id}")
                        e_roll    = st.number_input("Roll",    min_value=0,   value=int(lot.get("Roll",0) or 0), key=f"epo_rol_{doc.id}")
                        e_qty     = st.number_input("Qty",     min_value=0.0, value=float(lot.get("Qnty",0) or 0), step=0.5, key=f"epo_qty_{doc.id}")
                        e_process = st.text_input("Process",   value=lot.get("Process",""),                      key=f"epo_prc_{doc.id}")
                        e_diagsm  = st.text_input("Dia / GSM", value=lot.get("DiaGsm",""),                       key=f"epo_dgs_{doc.id}")
                    lot_updates[doc.id] = {
                        "LotNo":         e_lot_no.strip().upper(),
                        "OrderId":       derived_oid,
                        "Customer name": derived_cust,
                        "Item":          e_item.strip(),
                        "Colour":        e_colour.strip(),
                        "Roll":    int(e_roll),
                        "Qnty":    float(e_qty),
                        "Process": e_process.strip(),
                        "DiaGsm":  e_diagsm.strip(),
                    }

            if st.button("💾 Save All Changes", type="primary", key="epo_save_all"):
                hdr_update = {
                    "Date":      epo_date.strftime("%Y-%m-%d"),
                    "PartyName": epo_party,
                    "VehicleNo": epo_vehicle.strip(),
                }
                for doc_id, lot_data in lot_updates.items():
                    db.collection("process_out").document(doc_id).update({**hdr_update, **lot_data})
                st.success(f"✅ Process Out Challan {epo_challan.strip()} updated successfully")


# ═════════════════════════════════════════════════════════
#  EDIT PROCESS INWARD
# ═════════════════════════════════════════════════════════
elif menu == "Edit Process Inward":
    st.markdown('<div class="page-header"><h1>✏️ Edit Process Inward</h1></div>', unsafe_allow_html=True)

    epi_challan = st.text_input("Enter Challan No", key="epi_challan_no")

    if epi_challan.strip():
        pi_lots = [doc for doc in db.collection("process_inward").stream()
                   if doc.to_dict().get("ChallanNo","") == epi_challan.strip()]

        if not pi_lots:
            st.error("No Process Inward records found for this Challan No")
        else:
            first_pi = pi_lots[0].to_dict()
            st.success(f"Found {len(pi_lots)} lot(s) for Challan {epi_challan.strip()}")

            # ── Editable challan header ──
            st.markdown("#### Challan Header")
            ih1, ih2, ih3 = st.columns(3)
            with ih1:
                from datetime import datetime as _epidt, date as _epidate
                try:
                    epi_date_val = _epidt.strptime(first_pi.get("Date",""), "%Y-%m-%d").date()
                except Exception:
                    epi_date_val = _epidate.today()
                epi_date = st.date_input("Date", value=epi_date_val, format="DD/MM/YYYY", key="epi_hdr_date")
            with ih2:
                processors_i = get_processor_list()
                epi_party    = st.selectbox("Processor / Party", processors_i,
                                            index=processors_i.index(first_pi.get("PartyName",""))
                                            if first_pi.get("PartyName","") in processors_i else 0,
                                            key="epi_hdr_party") if processors_i else st.text_input(
                                                "Party", value=first_pi.get("PartyName",""), key="epi_hdr_party_txt")
            with ih3:
                epi_vehicle = st.text_input("Vehicle No", value=first_pi.get("VehicleNo",""), key="epi_hdr_veh")

            st.divider()

            # ── Editable lots ──
            st.markdown("#### Lots")
            pi_updates = {}
            for doc in pi_lots:
                lot = doc.to_dict()
                lot_no = lot.get("LotNo","")
                sent_qty = float(lot.get("SentQty",0) or 0)

                with st.expander(f"Lot: {lot_no}  |  Order: {lot.get('OrderId','')}  |  {lot.get('Colour','')}",
                                 expanded=False):
                    ic1, ic2 = st.columns(2)
                    with ic1:
                        st.text_input("Lot No",     value=lot_no,                        disabled=True, key=f"epi_ln_{doc.id}")
                        st.text_input("Order ID",   value=lot.get("OrderId",""),          disabled=True, key=f"epi_oi_{doc.id}")
                        st.text_input("Colour",     value=lot.get("Colour",""),           disabled=True, key=f"epi_col_{doc.id}")
                        st.text_input("Process",    value=lot.get("Process",""),          disabled=True, key=f"epi_prc_{doc.id}")
                        st.text_input("Sent Roll",  value=str(lot.get("SentRoll","")),   disabled=True, key=f"epi_sr_{doc.id}")
                        st.text_input("Sent Qty",   value=str(sent_qty),                 disabled=True, key=f"epi_sq_{doc.id}")
                    with ic2:
                        e_recv_roll = st.number_input("Received Roll", min_value=0,
                                                      value=int(lot.get("ReceivedRoll",0) or 0),
                                                      key=f"epi_rr_{doc.id}")
                        e_recv_qty  = st.number_input("Received Qty",  min_value=0.0, step=0.5,
                                                      value=float(lot.get("ReceivedQty",0) or 0),
                                                      key=f"epi_rq_{doc.id}")
                        e_rate      = st.number_input("Rate",           min_value=0.0, step=0.5,
                                                      value=float(lot.get("Rate",0) or 0),
                                                      key=f"epi_rt_{doc.id}")
                        e_remarks   = st.text_input("Remarks", value=lot.get("Remarks",""), key=f"epi_rem_{doc.id}")

                        # Recalculate
                        short_qty = round(sent_qty - e_recv_qty, 3)
                        short_pct = round((short_qty / sent_qty) * 100, 2) if sent_qty > 0 else 0.0
                        amount    = round(e_recv_qty * e_rate, 2)

                        if e_recv_qty > sent_qty:
                            st.error(f"⚠️ Received ({e_recv_qty}) > Sent ({sent_qty})")
                        elif e_recv_qty > 0 and short_qty > 0:
                            st.warning(f"📉 Shortage: {short_qty} kg | {short_pct}%")

                        sc1, sc2, sc3 = st.columns(3)
                        sc1.text_input("Short Qty",  value=str(short_qty), disabled=True, key=f"epi_shq_{doc.id}")
                        sc2.text_input("Short %",    value=f"{short_pct}%", disabled=True, key=f"epi_shp_{doc.id}")
                        sc3.text_input("Amount",     value=str(amount),    disabled=True, key=f"epi_amt_{doc.id}")

                    pi_updates[doc.id] = {
                        "ReceivedRoll": int(e_recv_roll),
                        "ReceivedQty":  float(e_recv_qty),
                        "ShortQty":     short_qty,
                        "ShortPct":     short_pct,
                        "Rate":         float(e_rate),
                        "Amount":       amount,
                        "Remarks":      e_remarks.strip(),
                    }

            if st.button("💾 Save All Changes", type="primary", key="epi_save_all"):
                hdr_update_i = {
                    "Date":      epi_date.strftime("%Y-%m-%d"),
                    "PartyName": epi_party,
                    "VehicleNo": epi_vehicle.strip(),
                }
                for doc_id, lot_data in pi_updates.items():
                    db.collection("process_inward").document(doc_id).update({**hdr_update_i, **lot_data})
                st.success(f"✅ Process Inward Challan {epi_challan.strip()} updated successfully")


elif menu == "Cancel Shoot Order":
    st.markdown('<div class="page-header"><h1>🚫 Cancel Shoot Order</h1></div>', unsafe_allow_html=True)

    cs_oid = st.text_input("Enter Order ID", key="cancel_so_oid")

    if cs_oid.strip():
        so_docs = list(db.collection("shoot_order")
                       .where("OrderId", "==", cs_oid.strip()).stream())
        if not so_docs:
            st.error("No shoot order found for this Order ID")
        else:
            so_data = so_docs[0].to_dict()
            so_id   = so_docs[0].id

            st.success("Shoot Order found")
            sc1, sc2 = st.columns(2)
            sc1.text_input("Customer",    value=so_data.get("Customer name",""), disabled=True, key="cso_cust")
            sc1.text_input("Item",        value=so_data.get("Item",""),          disabled=True, key="cso_item")
            sc2.text_input("Shoot Date",  value=so_data.get("Date",""),          disabled=True, key="cso_date")
            sc2.text_input("Category",    value=so_data.get("Category",""),      disabled=True, key="cso_cat")

            st.warning("⚠️ Cancelling this shoot order will move the order back to **Pending** status.")
            confirm_cancel = st.checkbox("I confirm I want to cancel this shoot order", key="cso_confirm")

            if confirm_cancel:
                if st.button("🚫 Cancel Shoot Order", type="primary", key="cso_submit"):
                    db.collection("shoot_order").document(so_id).delete()
                    st.success(f"✅ Shoot Order for Order {cs_oid} cancelled. Order is now back to Pending status.")
                    # Clear input
                    if "cancel_so_oid" in st.session_state:
                        del st.session_state["cancel_so_oid"]
                    st.rerun()


elif menu == "Import Data":
    import re as _re
    from datetime import datetime as _dtt
    st.markdown('<div class="page-header"><h1>📥 Import Data from Google Sheets</h1></div>', unsafe_allow_html=True)
    st.info("Read-only access — your Google Sheet will never be modified.")

    # ── Danger Zone: Clear Collections ──
    with st.expander("🗑️  Clear Collection (use before re-importing)", expanded=False):
        st.warning("⚠️ This permanently deletes ALL documents in the selected collection. Cannot be undone.")

        CLEARABLE = {
            "po":              "Purchase Orders (po)",
            "shoot_order":     "Shoot Orders (shoot_order)",
            "PackingListRaw":  "Packing Lists (PackingListRaw)",
            "cancel_orders":   "Cancelled Orders (cancel_orders)",
            "process_out":     "Process Out (process_out)",
            "process_inward":  "Process Inward (process_inward)",
            "customer_master": "Customer Master (customer_master)",
            "item_master":     "Item Master (item_master)",
        }

        clr_coll = st.selectbox("Select collection to clear",
                                list(CLEARABLE.values()), key="clr_coll_sel")
        clr_key  = [k for k, v in CLEARABLE.items() if v == clr_coll][0]

        if "clr_doc_count" not in st.session_state:
            st.session_state.clr_doc_count = None
            st.session_state.clr_doc_key   = None

        if st.button("🔍 Count Documents", key="clr_count_btn"):
            try:
                clr_docs_check = list(db.collection(clr_key).stream())
                st.session_state.clr_doc_count = len(clr_docs_check)
                st.session_state.clr_doc_key   = clr_key
            except Exception as e:
                st.error(f"Error counting: {e}")

        if st.session_state.clr_doc_key == clr_key and st.session_state.clr_doc_count is not None:
            count = st.session_state.clr_doc_count
            st.markdown(f"**{count} documents** in `{clr_key}`")

            clr_confirm = st.checkbox(
                f"I confirm I want to delete all {count} records from `{clr_key}`",
                key="clr_confirm")

            if clr_confirm:
                if st.button("🗑️ Delete All Records", type="primary", key="clr_go"):
                    with st.spinner(f"Deleting {count} records..."):
                        try:
                            clr_docs = list(db.collection(clr_key).stream())
                            for doc in clr_docs:
                                db.collection(clr_key).document(doc.id).delete()
                            st.success(f"✅ Deleted {len(clr_docs)} records from `{clr_key}`")
                            st.session_state.clr_doc_count = None
                            st.session_state.clr_doc_key   = None
                            st.rerun()
                        except Exception as e:
                            st.error(f"Delete failed: {e}")

    st.divider()

    # ── Batch Image Migration ──
    with st.expander("🖼️  Migrate Images from Old Drive (one-time setup)", expanded=False):
        st.info(
            "Your imported POs have Google Drive image links. "
            "Share the folder containing those images with **firebase-adminsdk-fbsvc@lkf-erp-12c7d.iam.gserviceaccount.com** "
            "(Viewer access), then click Migrate below. No files are moved — we just extract the file IDs."
        )

        import re as _img_re

        def _extract_file_id(url: str) -> str:
            url = url or ""
            for pattern in [
                r"[?&]id=([a-zA-Z0-9_-]+)",
                r"/d/([a-zA-Z0-9_-]+)",
                r"/file/d/([a-zA-Z0-9_-]+)",
            ]:
                m = _img_re.search(pattern, url)
                if m:
                    return m.group(1)
            return ""

        mc1, mc2 = st.columns(2)
        with mc1:
            if st.button("🔍 Scan — how many images need migration?", key="img_scan"):
                with st.spinner("Scanning..."):
                    try:
                        all_po = list(db.collection("po").stream())
                        needs = [d for d in all_po
                                 if d.to_dict().get("image","") and not d.to_dict().get("image_drive_id","")]
                        st.session_state.img_needs = needs
                        st.success(f"Found **{len(needs)}** orders with image URLs but no Drive ID stored.")
                    except Exception as e:
                        st.error(f"Scan failed: {e}")

        if st.session_state.get("img_needs"):
            st.markdown(f"**{len(st.session_state.img_needs)} orders ready to migrate**")
            if st.button("🚀 Run Image Migration", type="primary", key="img_migrate"):
                needs   = st.session_state.img_needs
                ok = fail = skip = 0
                prog = st.progress(0)
                status_box = st.empty()

                for i, doc in enumerate(needs):
                    data     = doc.to_dict()
                    img_url  = data.get("image","")
                    file_id  = _extract_file_id(img_url)

                    if not file_id:
                        skip += 1
                    else:
                        try:
                            # Verify service account can access the file
                            svc = _drive_service()
                            svc.files().get(fileId=file_id, fields="id",
                                            supportsAllDrives=True).execute()
                            # Update Firebase with the extracted file ID
                            db.collection("po").document(doc.id).update({
                                "image_drive_id": file_id
                            })
                            ok += 1
                        except Exception:
                            fail += 1

                    prog.progress((i + 1) / len(needs))
                    status_box.caption(f"Processing {i+1}/{len(needs)}…")

                prog.empty()
                status_box.empty()
                _fetch_image_bytes.clear()
                st.session_state.img_needs = None
                st.success(
                    f"✅ Migration complete — **{ok} migrated**, "
                    f"{skip} skipped (no URL), {fail} inaccessible "
                    f"(share the Drive folder with the service account first)"
                )

    st.divider()

    # ── Sheets helper ──
    def _sheets_svc():
        creds = service_account.Credentials.from_service_account_info(
            _sa_info(),
            scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"],
        )
        return build("sheets", "v4", credentials=creds)

    def _extract_sheet_id(url_or_id: str) -> str:
        m = _re.search(r"/spreadsheets/d/([a-zA-Z0-9-_]+)", url_or_id)
        return m.group(1) if m else url_or_id.strip()

    def _read_sheet(sheet_id: str, tab: str) -> list:
        svc    = _sheets_svc()
        result = svc.spreadsheets().values().get(
            spreadsheetId=sheet_id, range=tab
        ).execute()
        return result.get("values", [])

    def _get_tabs(sheet_id: str) -> list:
        svc    = _sheets_svc()
        meta   = svc.spreadsheets().get(spreadsheetId=sheet_id).execute()
        return [s["properties"]["title"] for s in meta.get("sheets", [])]

    # ── Collection configurations ──
    COLLECTION_CFG = {
        "PO": {
            "collection": "po",
            "label": "Purchase Orders → `po` collection",
            "required": ["OrderId","Customer name","Item","Category","Date"],
            "fields": {
                "OrderId":            ("Order ID *",             ["order id","orderid","order_id","po id","po no","pono","serial"]),
                "Customer name":      ("Customer Name *",        ["customer","customer name","client","party name","buyer"]),
                "Item":               ("Item *",                 ["item","item name","design","design name","product","fabric"]),
                "Category":           ("Category *",             ["category","type","fabric type","cat"]),
                "Date":               ("Date *",                 ["date","po date","order date","booking date"]),
                "gsm":                ("GSM",                    ["gsm","weight"]),
                "facricqnty":         ("Fabric Qty",             ["fabric qty","fabric quantity","total fabric qty","qty","quantity","meters"]),
                "fabricprice":        ("Fabric Price",           ["fabric price","price","rate","fabric rate"]),
                "accessoryqnty":      ("Accessory Qty",          ["accessory qty","accessory quantity","acc qty","acc. qty"]),
                "accessoryprice":     ("Accessory Price",        ["accessory price","acc price","acc. price"]),
                "customerpono":       ("Customer PO No",         ["customer po","customer po no","cust po","buyer po","po ref"]),
                "coloursinstructions":("Colours/Instructions",   ["colours","colour","colors","instructions","remarks"]),
                "image":              ("Image URL",              ["image","image link","image url","photo","photo link","drive link","picture"]),
                "accessory":          ("Accessory Description",   ["accessory","accessory desc","accessory details","accessories","acc desc","acc detail"]),
            },
        },
        "Shoot Order": {
            "collection": "shoot_order",
            "label": "Shoot Orders → `shoot_order` collection",
            "required": ["OrderId","Date"],
            "fields": {
                "OrderId":            ("Order ID *",             ["order id","orderid","order_id","po id","po no","serial"]),
                "Date":               ("Shoot Date *",           ["date","shoot date","knitting date","start date"]),
                "Customer name":      ("Customer Name",          ["customer","customer name","client","party"]),
                "Item":               ("Item",                   ["item","item name","design","product"]),
                "Category":           ("Category",               ["category","type","cat"]),
                "gsm":                ("GSM",                    ["gsm","weight"]),
                "facricqnty":         ("Fabric Qty",             ["fabric qty","qty","quantity","total fabric qty"]),
                "coloursinstructions":("Colours/Instructions",   ["colours","colour","instructions","remarks"]),
                "image":              ("Image URL",              ["image","image link","image url","photo","picture"]),
            },
        },
        "Packing List": {
            "collection": "PackingListRaw",
            "label": "Packing Lists → `PackingListRaw` collection",
            "required": ["OrderId"],
            "fields": {
                "OrderId":            ("Order ID *",             ["order id","orderid","order_id","po id","po no","serial"]),
                "Customer name":      ("Customer Name",          ["customer","customer name","client","party"]),
                "Item":               ("Item",                   ["item","item name","design","product"]),
                "Date":               ("Date",                   ["date","packing date","dispatch date"]),
                "FabricDetails":      ("Fabric Details",         ["fabric details","fabric","fabric colour","fabric colors","fabric data"]),
                "AccessoryDetails":   ("Accessory Details",      ["accessory details","accessory","acc details","accessory data"]),
            },
        },
        "Cancel PO": {
            "collection": "cancel_orders",
            "label": "Cancelled Orders → `cancel_orders` collection",
            "required": ["OrderId","Date"],
            "fields": {
                "OrderId":            ("Order ID *",             ["order id","orderid","order_id","po id","po no","serial"]),
                "Date":               ("Cancel Date *",          ["date","cancel date","cancellation date"]),
                "Reason":             ("Reason",                 ["reason","remarks","comment","why"]),
                "Status":             ("Status",                 ["status","valid","validity"]),
            },
        },
    }

    # ── Collection selector ──
    st.markdown("#### Select Data Type to Import")
    coll_icons = {"PO": "📄","Shoot Order": "🎯","Packing List": "📦","Cancel PO": "❌"}
    coll_type = st.radio(
        "",
        list(COLLECTION_CFG.keys()),
        format_func=lambda x: f"{coll_icons[x]} {x}",
        horizontal=True,
        key="imp_coll_type",
        label_visibility="collapsed",
    )
    cfg = COLLECTION_CFG[coll_type]
    st.caption(f"Destination: **{cfg['label']}**")
    st.divider()

    FIELD_MAP = {k: v[1] for k, v in cfg["fields"].items()}

    def _auto_detect(headers: list) -> dict:
        mapping = {}
        h_lower = [h.lower().strip() for h in headers]
        for field, aliases in FIELD_MAP.items():
            for alias in aliases:
                if alias in h_lower:
                    mapping[field] = h_lower.index(alias)
                    break
        return mapping

    # ── Session state — clear cached sheet data when collection type changes ──
    if "imp_last_coll_type" not in st.session_state:
        st.session_state.imp_last_coll_type = None

    if st.session_state.imp_last_coll_type != coll_type:
        for k in ["imp_sheet_data","imp_headers","imp_mapping","imp_tab_list"]:
            st.session_state[k] = None
        st.session_state.imp_last_coll_type = coll_type

    for k in ["imp_sheet_data","imp_headers","imp_mapping","imp_tab_list"]:
        if k not in st.session_state:
            st.session_state[k] = None

    # ── Step 1: Sheet URL + Tab ──
    st.markdown("#### Step 1 — Connect to Sheet")
    c1, c2 = st.columns([3, 1])
    with c1:
        sheet_url = st.text_input("Google Sheet URL or Sheet ID", key="imp_url",
                                  placeholder="https://docs.google.com/spreadsheets/d/...")
    with c2:
        st.markdown("<br>", unsafe_allow_html=True)
        load_tabs = st.button("Load Tabs", key="imp_load_tabs")

    if load_tabs and sheet_url.strip():
        with st.spinner("Connecting..."):
            try:
                sid  = _extract_sheet_id(sheet_url)
                tabs = _get_tabs(sid)
                st.session_state.imp_tab_list = tabs
                st.success(f"Connected — {len(tabs)} tab(s) found")
            except Exception as e:
                st.error(f"Cannot connect: {e}\n\nMake sure the sheet is shared with **{service_account.Credentials.from_service_account_info(_sa_info(), scopes=[]).service_account_email}**")

    tab_name = None
    if st.session_state.imp_tab_list:
        tab_name = st.selectbox("Select Tab to Import", st.session_state.imp_tab_list, key="imp_tab")

    load_preview = st.button("📋 Load Preview", key="imp_preview_btn",
                              disabled=not (sheet_url.strip() and tab_name))

    if load_preview:
        with st.spinner("Loading sheet data..."):
            try:
                sid  = _extract_sheet_id(sheet_url)
                data = _read_sheet(sid, tab_name)
                if not data or len(data) < 2:
                    st.warning("Sheet appears empty or has only headers.")
                else:
                    st.session_state.imp_sheet_data = data
                    st.session_state.imp_headers    = data[0]
                    st.session_state.imp_mapping    = _auto_detect(data[0])
                    st.success(f"Loaded {len(data)-1} rows")
            except Exception as e:
                st.error(f"Error reading sheet: {e}")

    # ── Step 2: Column Mapping ──
    if st.session_state.imp_headers:
        headers = st.session_state.imp_headers
        mapping = st.session_state.imp_mapping

        st.divider()
        st.markdown(f"#### Step 2 — Map Sheet Columns  *(only required fields shown)*")
        st.caption("Auto-detected where possible. Set unused fields to — skip —.")

        col_options = ["— skip —"] + headers
        new_mapping = {}

        fields_list = list(cfg["fields"].items())
        cols_per_row = 3
        for i in range(0, len(fields_list), cols_per_row):
            row_fields = fields_list[i:i+cols_per_row]
            row_cols   = st.columns(cols_per_row)
            for j, (fld, (lbl, _)) in enumerate(row_fields):
                current_idx = mapping.get(fld, -1)
                default     = col_options[current_idx + 1] if current_idx >= 0 else "— skip —"
                sel = row_cols[j].selectbox(lbl, col_options,
                                            index=col_options.index(default),
                                            key=f"imp_col_{coll_type}_{fld}")
                if sel != "— skip —":
                    new_mapping[fld] = headers.index(sel)

        st.session_state.imp_mapping = new_mapping

        # Preview
        st.divider()
        st.markdown("#### Step 3 — Preview (first 5 rows)")
        preview_data = []
        for row in st.session_state.imp_sheet_data[1:6]:
            rec = {fld: (row[idx] if idx < len(row) else "") for fld, idx in new_mapping.items()}
            preview_data.append(rec)
        if preview_data:
            st.dataframe(pd.DataFrame(preview_data), use_container_width=True, hide_index=True)

        # Import options
        st.divider()
        st.markdown("#### Step 4 — Import Options")
        o1, o2 = st.columns(2)
        with o1:
            conflict = st.radio("If record already exists:",
                                ["Skip (keep existing)", "Update (overwrite)"],
                                key="imp_conflict")
        with o2:
            also_masters = st.checkbox("Auto-add Customers & Items to master lists",
                                       value=True, key="imp_masters")

        # When updating existing records only, OrderId is the only required field.
        # All other required fields are only needed when creating new records.
        if conflict == "Update (overwrite)":
            required = {"OrderId"}
        else:
            required = set(cfg["required"])
        missing = required - set(new_mapping.keys())
        if missing:
            st.warning(f"Required columns not mapped: {', '.join(missing)}")

        def _norm_date(raw):
            for fmt in ["%d/%m/%Y","%Y-%m-%d","%d-%m-%Y","%m/%d/%Y","%d-%b-%Y","%d-%b-%y"]:
                try:
                    return _dtt.strptime(raw.strip(), fmt).strftime("%Y-%m-%d")
                except Exception:
                    pass
            return raw.strip()

        def _to_float(v):
            try:
                return float(str(v).replace(",","").strip() or 0)
            except Exception:
                return 0.0

        if not missing:
            if st.button("🚀 Start Import", type="primary", key="imp_start"):
                all_rows   = st.session_state.imp_sheet_data[1:]
                skip_cnt = upd_cnt = new_cnt = err_cnt = 0
                err_rows = []
                progress   = st.progress(0)
                status_box = st.empty()

                # Pre-load existing IDs for duplicate check
                coll_ref   = db.collection(cfg["collection"])
                if coll_type in ("PO", "Packing List"):
                    existing_ids = {doc.id for doc in coll_ref.stream()}
                elif coll_type in ("Shoot Order", "Cancel PO"):
                    existing_ids = {
                        doc.to_dict().get("OrderId","") for doc in coll_ref.stream()
                    }
                else:
                    existing_ids = set()

                existing_customers = {doc.id.upper().strip() for doc in db.collection("customer_master").stream()}
                existing_items     = {doc.id.upper().strip() for doc in db.collection("item_master").stream()}

                # Auto RawId counter for Packing List
                raw_id_counter = max(
                    (int(d.to_dict().get("RawId",0)) for d in db.collection("PackingListRaw").stream()
                     if str(d.to_dict().get("RawId","")).isdigit()), default=0
                ) + 1 if coll_type == "Packing List" else None

                for i, row in enumerate(all_rows):
                    try:
                        rec = {fld: row[idx].strip() if idx < len(row) else ""
                               for fld, idx in new_mapping.items()}

                        oid = str(rec.get("OrderId","")).strip()
                        if not oid:
                            err_cnt += 1
                            continue

                        date_val = _norm_date(rec.get("Date",""))

                        # ── PO ──
                        if coll_type == "PO":
                            cat = rec.get("Category","").upper().strip()
                            doc_data = {
                                "OrderId":             oid,
                                "Customer name":       rec.get("Customer name","").upper().strip(),
                                "Item":                rec.get("Item","").strip(),
                                "Category":            cat if cat in ("STRIPE","PLAIN") else "PLAIN",
                                "Date":                date_val,
                                "gsm":                 _to_float(rec.get("gsm",0)),
                                "facricqnty":          _to_float(rec.get("facricqnty",0)),
                                "fabricprice":         _to_float(rec.get("fabricprice",0)),
                                "accessoryqnty":       _to_float(rec.get("accessoryqnty",0)),
                                "accessoryprice":      _to_float(rec.get("accessoryprice",0)),
                                "customerpono":        rec.get("customerpono",""),
                                "coloursinstructions": rec.get("coloursinstructions",""),
                                "image":               rec.get("image",""),
                                "image_drive_id":      "",
                                "pdf_url":             "",
                                "accessory":           rec.get("accessory",""),
                            }
                            if oid in existing_ids:
                                if conflict == "Skip (keep existing)":
                                    skip_cnt += 1
                                else:
                                    # Only update fields that were explicitly mapped
                                    # This prevents overwriting existing fields with empty values
                                    update_data = {k: doc_data[k] for k in rec if k in doc_data}
                                    update_data["OrderId"] = oid
                                    db.collection("po").document(oid).update(update_data)
                                    upd_cnt += 1
                            else:
                                db.collection("po").document(oid).set(doc_data)
                                existing_ids.add(oid); new_cnt += 1

                            if also_masters:
                                cust = doc_data["Customer name"].upper().strip()
                                if cust and cust not in existing_customers:
                                    db.collection("customer_master").document(cust).set({"CustomerName": cust})
                                    existing_customers.add(cust)
                                itm = doc_data["Item"].upper().strip()
                                if itm and itm not in existing_items:
                                    db.collection("item_master").document(itm).set({"ItemName": itm})
                                    existing_items.add(itm)

                        # ── Shoot Order ──
                        elif coll_type == "Shoot Order":
                            doc_data = {
                                "OrderId":             oid,
                                "Date":                date_val,
                                "Customer name":       rec.get("Customer name","").upper().strip(),
                                "Item":                rec.get("Item","").strip(),
                                "Category":            rec.get("Category","").upper().strip(),
                                "gsm":                 _to_float(rec.get("gsm",0)),
                                "facricqnty":          _to_float(rec.get("facricqnty",0)),
                                "coloursinstructions": rec.get("coloursinstructions",""),
                                "image":               rec.get("image",""),
                                "image_drive_id":      "",
                            }
                            if oid in existing_ids and conflict == "Skip (keep existing)":
                                skip_cnt += 1
                            else:
                                db.collection("shoot_order").add(doc_data)
                                existing_ids.add(oid); new_cnt += 1

                        # ── Packing List ──
                        elif coll_type == "Packing List":
                            doc_data = {
                                "RawId":            str(raw_id_counter),
                                "OrderId":          oid,
                                "Customer name":    rec.get("Customer name","").upper().strip(),
                                "Item":             rec.get("Item","").strip(),
                                "Date":             date_val,
                                "FabricDetails":    rec.get("FabricDetails",""),
                                "AccessoryDetails": rec.get("AccessoryDetails",""),
                            }
                            if oid in existing_ids and conflict == "Skip (keep existing)":
                                skip_cnt += 1
                            else:
                                db.collection("PackingListRaw").document(str(raw_id_counter)).set(doc_data)
                                existing_ids.add(oid); raw_id_counter += 1; new_cnt += 1

                        # ── Cancel PO ──
                        elif coll_type == "Cancel PO":
                            po_exists = db.collection("po").document(oid).get().exists
                            status_val = rec.get("Status","").upper().strip() or ("VALID" if po_exists else "INVALID")
                            doc_id   = f"{oid}_{date_val}"
                            doc_data = {
                                "OrderId": oid,
                                "Date":    date_val,
                                "Reason":  rec.get("Reason",""),
                                "Status":  status_val,
                            }
                            if oid in existing_ids and conflict == "Skip (keep existing)":
                                skip_cnt += 1
                            else:
                                db.collection("cancel_orders").document(doc_id).set(doc_data)
                                existing_ids.add(oid); new_cnt += 1

                    except Exception as _import_err:
                        err_cnt += 1
                        err_rows.append(f"Row {i+2}: OrderId={rec.get('OrderId','?')} — {_import_err}")

                    progress.progress((i + 1) / len(all_rows))
                    status_box.caption(f"Processing row {i+1} of {len(all_rows)}...")

                progress.empty()
                status_box.empty()
                st.success(f"✅ Import complete — **{new_cnt} added**, {upd_cnt} updated, {skip_cnt} skipped, {err_cnt} errors")
                if err_rows:
                    with st.expander(f"⚠️ {err_cnt} error(s) — click to see details"):
                        for msg in err_rows:
                            st.error(msg)
