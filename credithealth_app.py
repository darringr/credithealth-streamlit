import streamlit as st
import pdfplumber
import re
import pandas as pd
from datetime import datetime

st.set_page_config(page_title="CreditHealth Checker", page_icon="💳")

st.title("💳 CreditHealth Checker")
st.subheader("Upload a PDF Credit Report to Evaluate")

DB_FILE = "clients.csv"

def load_client_data():
    try:
        return pd.read_csv(DB_FILE)
    except FileNotFoundError:
        return pd.DataFrame(columns=["Name", "Upload Date", "Status", "Issues"])

def save_client_record(name, status, issues):
    date = datetime.today().strftime("%Y-%m-%d")
    new_entry = pd.DataFrame([[name, date, status, "; ".join(issues)]],
                             columns=["Name", "Upload Date", "Status", "Issues"])
    df = load_client_data()
    df = pd.concat([df, new_entry], ignore_index=True)
    df.to_csv(DB_FILE, index=False)

def extract_data_from_pdf(pdf_file):
    with pdfplumber.open(pdf_file) as pdf:
        text = ""
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text += page_text + "\n"

    # Extract name from "Name\nRASHAWN DARRING"
    name_match = re.search(r"Name\s*\n([A-Z\s]+)", text)
    name = name_match.group(1).strip().title() if name_match else "Unknown"

    bureaus = ["Transunion", "Experian", "Equifax"]
    sections = {}
    bureau_flags = {}
    bureau_scores = {}
    utilization_data = {}
    inquiries_data = {}
    open_accounts_data = {}

    # Credit age extraction (across all bureaus)
    date_matches = re.findall(r"Date Opened:\s*\n?(\d{1,2}/\d{1,2}/\d{4})", text)
    if date_matches:
        oldest = min([datetime.strptime(d, "%m/%d/%Y") for d in date_matches])
        credit_age = round((datetime.today() - oldest).days / 365, 1)
    else:
        credit_age = 0

    for bureau in bureaus:
        start = text.lower().find(bureau.lower())
        if start == -1:
            continue
        end = min([text.lower().find(b.lower(), start + 1) for b in bureaus if text.lower().find(b.lower(), start + 1) != -1] + [len(text)])
        section_text = text[start:end]
        sections[bureau] = section_text

        score_match = re.search(rf"{bureau}\s*\n?(\d{{3}})", section_text, re.IGNORECASE)
        score = int(score_match.group(1)) if score_match else None
        bureau_scores[bureau] = score

        # Derogatory
        derog_match = re.search(r"Derogatory:\s*\n?(\d+)", section_text)
        derogatory = int(derog_match.group(1)) if derog_match else 0

        # Inquiries
        inquiry_match = re.search(r"Inquiries\s*\(2 years\):\s*\n?(\d+)", section_text)
        inquiries = int(inquiry_match.group(1)) if inquiry_match else 0
        inquiries_data[bureau] = inquiries

        # Open Accounts
        open_match = re.search(r"Open Accounts:\s*\n?(\d+)", section_text)
        open_accounts = int(open_match.group(1)) if open_match else 0
        open_accounts_data[bureau] = open_accounts

        # Utilization
        util_match = re.search(r"Percent Utilization.*?([\d.]+)%", section_text, re.DOTALL)
        utilization = float(util_match.group(1)) if util_match else 100.0
        utilization_data[bureau] = utilization

        # Flag indicators
        flags = {
            "Credit Score": score < 700 if score is not None else True,
            "Derogatory": derogatory > 0,
            "Inquiries": inquiries > 3,
            "Open Accounts": open_accounts < 3
        }
        bureau_flags[bureau] = flags

    return {
        "name": name,
        "bureau_scores": bureau_scores,
        "bureau_flags": bureau_flags,
        "utilization": utilization_data,
        "open_accounts": open_accounts_data,
        "inquiries": inquiries_data,
        "credit_age": credit_age
    }

def flag_icon(is_red):
    return "🔴 Needs Improvement" if is_red else "🟢 OK"

def build_qualification_table(parsed):
    bureaus = ["Transunion", "Experian", "Equifax"]
    rows = {
        "700+ Credit Score": [],
        "730+ Credit Score": [],
        "Utilization under 30%": [],
        "5+ Open Revolving Accounts": [],
        "Credit Age ≥ 3 Years": [],
        "Card ≥ 3 Years w/ $5k Limit": [],
        "≤ 4 New Unsecured Accounts": [],
        "No Inquiries": [],
        "No Bankruptcies (7 Years)": [],
        "No Collections/Judgments/Late Payments": []
    }

    for bureau in bureaus:
        score = parsed["bureau_scores"].get(bureau, 0)
        utilization = parsed["utilization"].get(bureau, 100)
        open_accts = parsed["open_accounts"].get(bureau, 0)
        inquiries = parsed["inquiries"].get(bureau, 99)
        credit_age = parsed["credit_age"]

        rows["700+ Credit Score"].append(score >= 700)
        rows["730+ Credit Score"].append(score >= 730)
        rows["Utilization under 30%"].append(utilization < 30)
        rows["5+ Open Revolving Accounts"].append(open_accts >= 5)
        rows["Credit Age ≥ 3 Years"].append(credit_age >= 3)
        rows["Card ≥ 3 Years w/ $5k Limit"].append(True)  # placeholder
        rows["≤ 4 New Unsecured Accounts"].append(True)   # placeholder
        rows["No Inquiries"].append(inquiries == 0)
        rows["No Bankruptcies (7 Years)"].append(True)    # placeholder
        rows["No Collections/Judgments/Late Payments"].append(True)  # placeholder

    return pd.DataFrame(rows, index=bureaus).T

uploaded = st.file_uploader("📄 Upload Credit Report PDF", type="pdf")

if uploaded:
    try:
        parsed = extract_data_from_pdf(uploaded)
        name = parsed.get("name", "Unknown")
        st.write(f"Extracted Data for **{name}**")
        st.json(parsed)

        # Scores Table
        st.subheader("📈 Bureau Credit Scores")
        st.write(pd.DataFrame(parsed["bureau_scores"], index=["Score"]).T)

        # Bureau Flags Matrix
        st.subheader("📊 Bureau Evaluation Table")
        bureau_df = pd.DataFrame(parsed["bureau_flags"]).T
        bureau_df_display = bureau_df.applymap(flag_icon)
        st.dataframe(bureau_df_display, use_container_width=True)

        # Do You Qualify? Table
        st.subheader("📋 Do You Qualify?")
        qual_df = build_qualification_table(parsed)
        qual_display = qual_df.applymap(lambda v: "✅" if v else "❌")
        st.dataframe(qual_display, use_container_width=True)

        # Save to history
        all_flags = [f"{bureau} - {issue}" for bureau, flags in parsed["bureau_flags"].items() for issue, is_red in flags.items() if is_red]
        status = "Good" if not all_flags else "Needs Improvement"
        save_client_record(name, status, all_flags)

    except Exception as e:
        st.error(f"Something went wrong: {e}")

st.subheader("📋 Stored Clients")
clients_df = load_client_data()
st.dataframe(clients_df, use_container_width=True)
