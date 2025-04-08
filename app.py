from flask import Flask, request, jsonify
import fitz  # PyMuPDF
import re
import io
import base64
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

@app.route('/extract-payslip', methods=['POST'])
def extract_payslip():
    extracted_text = None
    user_id = None

    try:
        # ✅ Case 1: multipart/form-data (from OutSystems with form fields)
        if 'file' in request.files and 'user_id' in request.form:
            file = request.files['file']
            user_id = int(request.form['user_id'])

            if not file.filename.lower().endswith('.pdf'):
                return jsonify({"error": "Only PDF files are supported"}), 400

            pdf_bytes = file.read()
            extracted_text = extract_text_from_pdf(io.BytesIO(pdf_bytes))

        # ✅ Case 2: application/json with base64
        elif request.is_json:
            data = request.get_json()
            user_id = int(data.get("user_id"))
            base64_str = data.get("file")

            if not base64_str:
                return jsonify({"error": "Missing base64-encoded file"}), 400

            pdf_bytes = base64.b64decode(base64_str)
            extracted_text = extract_text_from_pdf(io.BytesIO(pdf_bytes))

        else:
            return jsonify({"error": "Unsupported content type"}), 400

        # ✅ Extract info
        net_pay = extract_value("Net Pay", extracted_text)
        employment_type = extract_employment_type(extracted_text)
        result_id = str(uuid.uuid4())

        # ✅ Store in Supabase
        response = supabase.table("payslip_results").insert({
            "id": result_id,
            "user_id": user_id,
            "net_pay": net_pay,
            "employment_type": employment_type
        }).execute()

        if not response.data:
            return jsonify({"error": "Failed to store in Supabase"}), 500

        return jsonify({
            "id": result_id,
            "user_id": user_id,
            "NetPay": net_pay,
            "EmploymentType": employment_type
        })

    except ValueError:
        return jsonify({"error": "Invalid or missing user_id"}), 400
    except Exception as e:
        return jsonify({"error": "Something went wrong", "details": str(e)}), 500


# ✅ GET /get-payslips/<user_id>
@app.route('/get-payslips/<user_id>', methods=['GET'])
def get_payslips_by_user(user_id):
    try:
        user_id = int(user_id)  # cast for bigint match
        response = supabase.table("payslip_results") \
            .select("*") \
            .eq("user_id", user_id) \
            .order("created_at", desc=True) \
            .execute()

        if not response.data:
            return jsonify({"message": "No records found"}), 404

        return jsonify(response.data)

    except ValueError:
        return jsonify({"error": "Invalid user_id. Must be a number."}), 400
    except Exception as e:
        return jsonify({"error": "Something went wrong", "details": str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True, port=5000)
