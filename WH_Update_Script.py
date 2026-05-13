# =============================================================
# metabase_to_jotform_dropdown.py
# WORKING - Author: Ankit
# -------------------------------------------------------------
# Purpose:
#     Fetches warehouse list from Metabase saved question and
#     updates two Jotform dropdown fields' OPTIONS so they are
#     available to users while filling/editing the form.
#
#     This updates the FORM DEFINITION (dropdown options),
#     NOT any submission data.
#
# Flow:
#     Metabase API -> Fetch warehouse names
#         |
#     Jotform API -> POST /form/{formId}/question/{qid}
#         |          with data: question[options] = "A|B|C"
#         |
#     Dropdown options updated in form builder
#         |
#     Verification GET to confirm options were saved
#
# Dropdowns updated:
#     - Question 326 (selectWarehouse)
#     - Question 328 (selectWarehouse328)
#
# Schedule:
#     Run daily via cron on Raspberry Pi
#     Example: 0 7 * * * python3 /home/pi/metabase_to_jotform_dropdown.py
#
# Requirements:
#     pip install requests
#
#
# =============================================================

import requests
import os
import sys

# =============================================================
# METABASE CONFIG
# =============================================================
METABASE_URL     = "https://reporting.daalchini.co.in"
METABASE_API_KEY = os.environ.get("METABASE_API_KEY")      # replace with actual key
METABASE_CARD_ID = 14926
WAREHOUSE_COLUMN = "name"

# =============================================================
# JOTFORM CONFIG
# =============================================================
JOTFORM_API_KEY      = os.environ.get("JOTFORM_API_KEY") 
JOTFORM_FORM_ID      = "251590768630059"
JOTFORM_QUESTION_IDS = [326, 328]               # both warehouse dropdowns

# =============================================================
# STEP 1 — FETCH WAREHOUSE LIST FROM METABASE
# =============================================================
def fetch_warehouses():
    print("\n[1/3] Fetching warehouses from Metabase...")
    url     = f"{METABASE_URL}/api/card/{METABASE_CARD_ID}/query/json"
    headers = {"x-api-key": METABASE_API_KEY}

    res = requests.post(url, headers=headers)

    if res.status_code != 200:
        print(f"  X Metabase fetch failed | Status: {res.status_code}")
        print(f"  Response: {res.text}")
        return None

    data       = res.json()
    warehouses = []
    for row in data:
        name = row.get(WAREHOUSE_COLUMN) or row.get(WAREHOUSE_COLUMN.capitalize())
        if name:
            warehouses.append(str(name).strip())

    print(f"  + Fetched {len(warehouses)} warehouses from Metabase")
    return warehouses

# =============================================================
# STEP 2 — UPDATE JOTFORM DROPDOWN OPTIONS
# Key learnings:
#   - Endpoint: /question/{qid}  (singular, not /questions/)
#   - Method:   POST             (not PUT)
#   - Data key: question[options] (not bare "options")
# =============================================================
def update_jotform_dropdown(question_id, options_list):
    url         = f"https://api.jotform.com/form/{JOTFORM_FORM_ID}/question/{question_id}"
    options_str = "|".join(options_list)

    res = requests.post(
        url,
        params={"apiKey": JOTFORM_API_KEY},
        data={
            "question[type]":    "control_dropdown",
            "question[options]": options_str
        }
    )

    if res.status_code == 200:
        result = res.json()
        if result.get("responseCode") == 200:
            print(f"  + Question {question_id} updated with {len(options_list)} options")
            return True
        else:
            print(f"  X Question {question_id} — Jotform error: {result}")
            return False
    else:
        print(f"  X Question {question_id} failed | Status: {res.status_code} | {res.text}")
        return False

# =============================================================
# STEP 3 — VERIFY OPTIONS WERE SAVED (READ-ONLY CHECK)
# content is a flat dict — options key is directly inside it
# =============================================================
def verify_dropdown(question_id, expected_count):
    url = f"https://api.jotform.com/form/{JOTFORM_FORM_ID}/question/{question_id}"
    res = requests.get(url, params={"apiKey": JOTFORM_API_KEY})

    if res.status_code != 200:
        print(f"  ? Could not verify question {question_id}")
        return

    content       = res.json().get("content", {})
    saved_options = content.get("options", "")
    count         = len(saved_options.split("|")) if saved_options else 0

    if count == expected_count:
        print(f"  + Verified question {question_id}: {count} options saved correctly")
    else:
        print(f"  ! Mismatch on question {question_id}: expected {expected_count}, found {count}")

# =============================================================
# MAIN
# =============================================================
if __name__ == "__main__":
    print("=" * 60)
    print("  METABASE -> JOTFORM DROPDOWN SYNC")
    print("=" * 60)

    # Step 1: Fetch from Metabase
    warehouses = fetch_warehouses()

    if not warehouses:
        print("\nX No warehouse data returned. Jotform NOT updated.")
        print("  Check Metabase API key and card ID.")
        exit(1)

    if len(warehouses) < 5:
        print(f"\n! Only {len(warehouses)} warehouses returned — suspiciously low.")
        print("  Aborting to avoid wiping the dropdown with bad data.")
        exit(1)

    # Step 2: Update both dropdowns
    print(f"\n[2/3] Updating Jotform dropdowns...")
    results = {}
    for qid in JOTFORM_QUESTION_IDS:
        results[qid] = update_jotform_dropdown(qid, warehouses)

    # Step 3: Verify
    print(f"\n[3/3] Verifying saved options...")
    for qid, success in results.items():
        if success:
            verify_dropdown(qid, len(warehouses))

    print("\n" + "=" * 60)
    all_ok = all(results.values())
    print(f"  SYNC {'COMPLETE' if all_ok else 'FINISHED WITH ERRORS'}")
    print("=" * 60)
