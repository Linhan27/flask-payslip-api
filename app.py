from flask import Flask, request, jsonify
import fitz  # PyMuPDF
import re
import io
import uuid
import os
from dotenv import load_dotenv
from supabase import create_client

app = Flask(__name__)
load_dotenv()

# Supabase setup
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def extract_text_from_pdf(file_stream):
    text = ""
    pdf = fitz.open(stream=file_stream, filetype="pdf")
    for page in pdf:
        text += page.get_text()
    return text

def extract_value(label, text):
    pattern = rf"{label}:\s*\$?([\d,]+\.\d{{2}})"
    match = re.search(pattern, text)
    if match:
        return float(match.group(1).replace(",", ""))
    return None

def extract_employment_type(text):
    pattern = r"Employment Type:\s*(.+)"
    match = re.search(pattern, text)
    return match.group(1).strip() if match else None

# ✅ POST /extract-payslip
@app.route('/extract-payslip', methods=['POST'])
def extract_payslip():
    if 'file' not in request.files or 'user_id' not in request.form:
        return jsonify({"error": "Missing file or user_id"}), 400

    file = request.files['file']
    user_id = request.form['user_id']
    filename = file.filename

    if not filename.lower().endswith('.pdf'):
        return jsonify({"error": "Only PDF files are supported"}), 400

    try:
        pdf_bytes = file.read()
        extracted_text = extract_text_from_pdf(io.BytesIO(pdf_bytes))

        net_pay = extract_value("Net Pay", extracted_text)
        employment_type = extract_employment_type(extracted_text)
        result_id = str(uuid.uuid4())

        response = supabase.table("payslip_results").insert({
            "id": result_id,
            "user_id": user_id,
            "net_pay": net_pay,
            "employment_type": employment_type
        }).execute()

        if response.error:
            print("Supabase insert error:", response.error.message)
            return jsonify({"error": response.error.message}), 500

        return jsonify({
            "id": result_id,
            "user_id": user_id,
            "NetPay": net_pay,
            "EmploymentType": employment_type
        })

    except Exception as e:
        print("Exception occurred:", e)
        return jsonify({"error": "Something went wrong", "details": str(e)}), 500


# ✅ GET /get-payslips/<user_id>
@app.route('/get-payslips/<user_id>', methods=['GET'])
def get_payslips_by_user(user_id):
    response = supabase.table("payslip_results") \
        .select("*") \
        .eq("user_id", user_id) \
        .order("created_at", desc=True) \
        .execute()

    if response.error:
        return jsonify({"error": response.error.message}), 500

    return jsonify(response.data)

if __name__ == '__main__':
    app.run(debug=True, port=5000)
