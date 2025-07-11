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

    # Extract name: looks for "Name\nRASHAWN DARRING"
    name_match = re.search(r"Name\s*\n([A-Z\s]+)", text)
    name = name_match.group(1).strip().title() if name_match else "Unknown"

    bureaus = ["Transunion", "Experian", "Equifax"]
    sections = {}
    bureau_flags = {}
    bureau_scores = {}

    for bureau in bureaus:
        # Find each bureau's section
        start = text.lower().find(bureau.lower())
        if start == -1:
            continue
        end = min([text.lower().find(b.lower(), start + 1) for b in bureaus if text.lower().find(b.lower(), start + 1) != -1] + [len(text)])
        section_text = text[start:end]
        sections[bureau] = section_text

        # Score (first number under bureau name)
        score_match = re.search(rf"{bureau}\s*\n?(\d{{3}})", section_text, re.IGNORECASE)
        score = int(score_match.group(1)) if score_match else None
        bureau_scores[bureau] = score

        # Derogatory
        derog_match = re.search(r"Derogatory:\s*\n?(\d+)", section_text)
        derogatory = int(derog_match.group(1)) if derog_match else 0

        # Inquiries
        inquiry_match = re.search(r"Inquiries\s*\(2 years\):\s*\n?(\d+)", section_text)
        inquiries = int(inquiry_match.group(1)) if inquiry_match else 0

        # Open Accounts
        open_match = re.search(r"Open Accounts:\s*\n?(\d+)", section_text)
        open_accounts = int(open_match.group(1)) if open_match else 0

        # Red flag logic
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
        "bureau_flags": bureau_flags
    }

def flag_icon(is_red):
    return "🔴 Needs Improvement" if is_red else "🟢 OK"

uploaded = st.file_uploader("📄 Upload Credit Report PDF", type="pdf")

if uploaded:
    try:
        parsed = extract_data_from_pdf(uploaded)
        name = parsed.get("name", "Unknown")
        st.write(f"Extracted Data for **{name}**")
        st.json(parsed)

        # Show scores
        st.subheader("📈 Bureau Credit Scores")
        st.write(pd.DataFrame(parsed["bureau_scores"], index=["Score"]).T)

        # Show bureau red/green matrix
        st.subheader("📊 Bureau Evaluation Table")
        bureau_df = pd.DataFrame(parsed["bureau_flags"]).T
        bureau_df_display = bureau_df.applymap(flag_icon)
        st.dataframe(bureau_df_display, use_container_width=True)

        # Determine status
        all_flags = [f"{bureau} - {issue}" for bureau, flags in parsed["bureau_flags"].items() for issue, is_red in flags.items() if is_red]
        status = "Good" if not all_flags else "Needs Improvement"

        # Save client
        save_client_record(name, status, all_flags)

    except Exception as e:
        st.error(f"Something went wrong: {e}")

# Show past clients
st.subheader("📋 Stored Clients")
clients_df = load_client_data()
st.dataframe(clients_df, use_container_width=True)
