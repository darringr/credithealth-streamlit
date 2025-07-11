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

def evaluate_credit(data):
    issues = []
    if data["late_payments"] > 0:
        issues.append("Late Payments")
    if data["negative_items"] > 0:
        issues.append("Negative Items")
    if data["utilization"] > 30:
        issues.append("High Utilization")
    if data["inquiries"] > 3:
        issues.append("Too Many Inquiries")
    if data["open_accounts"] < 3:
        issues.append("Low Number of Accounts")
    if data["credit_age"] < 3:
        issues.append("Low Credit Age")

    status = "Good" if not issues else "Needs Improvement"
    return status, issues

def extract_data_from_pdf(pdf_file):
    with pdfplumber.open(pdf_file) as pdf:
        text = ""
        for page in pdf.pages:
            text += page.extract_text() + "\n"

    name_match = re.search(r"Name\s*\n(.*?)\n", text)
    name = name_match.group(1).strip().title() if name_match else "Unknown"

    late_30 = max(map(int, re.findall(r"30:\s*(\d+)", text)), default=0)
    late_60 = max(map(int, re.findall(r"60:\s*(\d+)", text)), default=0)
    late_90 = max(map(int, re.findall(r"90:\s*(\d+)", text)), default=0)
    total_late = late_30 + late_60 + late_90

    derogatory_matches = re.findall(r"Derogatory:\s*\n?(\d+)", text)
    negative_items = max(map(int, derogatory_matches), default=0)

    inquiries = max(map(int, re.findall(r"Inquiries\s*\(2 years\):\s*\n?.*?(\d+)", text)), default=0)
    open_accounts = max(map(int, re.findall(r"Open Accounts:\s*\n?(\d+)", text)), default=0)

    balances = sum(map(lambda x: int(x.replace(",", "")), re.findall(r"Balances:\s*\$([\d,]+)", text)))
    limits = sum(map(lambda x: int(x.replace(",", "")), re.findall(r"Credit Limit:\s*\$?([\d,]+)", text)))
    utilization = round((balances / limits) * 100, 1) if limits > 0 else 0

    years = re.findall(r"Date Opened:\s*\n?(\d{1,2}/\d{1,2}/\d{4})", text)
    oldest = min([datetime.strptime(d, "%m/%d/%Y") for d in years]) if years else datetime.today()
    age_years = round((datetime.today() - oldest).days / 365, 1)

    return {
        "name": name,
        "late_payments": total_late,
        "negative_items": negative_items,
        "utilization": utilization,
        "inquiries": inquiries,
        "open_accounts": open_accounts,
        "credit_age": age_years,
    }

uploaded = st.file_uploader("📄 Upload Credit Report PDF", type="pdf")

if uploaded:
    try:
        parsed_data = extract_data_from_pdf(uploaded)
        st.write(f"Extracted Data for **{parsed_data['name']}**")
        st.json(parsed_data)

        status, issues = evaluate_credit(parsed_data)

        if status == "Good":
            st.success("✅ Credit Profile is in GOOD standing")
            st.markdown("<h1 style='color:green;'>🟢</h1>", unsafe_allow_html=True)
        else:
            st.error("⚠️ Credit Profile needs improvement")
            st.markdown("<h1 style='color:red;'>🔴</h1>", unsafe_allow_html=True)
            st.write("Issues found:")
            for issue in issues:
                st.write(f"• {issue}")

        save_client_record(parsed_data["name"], status, issues)

    except Exception as e:
        st.error(f"Something went wrong: {e}")

st.subheader("📋 Stored Clients")
clients_df = load_client_data()
st.dataframe(clients_df, use_container_width=True)
