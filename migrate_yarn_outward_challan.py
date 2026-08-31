"""One-time migration: prefix Yarn Outward challan numbers with 'YD-'.

Updates:
- yarn_outward.ChallanNo:            "101"                -> "YD-101"
- yarn_inward.ClearedChallans[].ChallanNo: "101"           -> "YD-101"
  (kept in sync since these are cross-references used for pending-yarn calc)

Only touches values that are plain numeric strings; already-prefixed
values are left untouched, so this script is safe to re-run.
"""
import firebase_admin
from firebase_admin import credentials, firestore

cred = credentials.Certificate("firebase-key.json")
firebase_admin.initialize_app(cred)
db = firestore.client()


def _prefixed(val: str) -> str:
    val = str(val or "").strip()
    return f"YD-{val}" if val.isdigit() else val


out_updated = 0
for doc in db.collection("yarn_outward").stream():
    data = doc.to_dict()
    old = str(data.get("ChallanNo", "")).strip()
    if old.isdigit():
        doc.reference.set({"ChallanNo": _prefixed(old)}, merge=True)
        out_updated += 1

in_updated = 0
in_refs_updated = 0
for doc in db.collection("yarn_inward").stream():
    data = doc.to_dict()
    cleared = data.get("ClearedChallans", [])
    if not cleared:
        continue
    changed = False
    new_cleared = []
    for c in cleared:
        cn = str(c.get("ChallanNo", "")).strip()
        if cn.isdigit():
            c = {**c, "ChallanNo": _prefixed(cn)}
            changed = True
            in_refs_updated += 1
        new_cleared.append(c)
    if changed:
        doc.reference.set({"ClearedChallans": new_cleared}, merge=True)
        in_updated += 1

print(f"yarn_outward docs updated: {out_updated}")
print(f"yarn_inward docs updated: {in_updated} ({in_refs_updated} ClearedChallans references re-prefixed)")
