from flask import Flask, request, jsonify
import fitz  # PyMuPDF
import re
import io

app = Flask(__name__)

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
    if 'file' not in request.files:
        return jsonify({"error": "PDF file is missing"}), 400

    file = request.files['file']
    filename = file.filename

    if not filename.lower().endswith('.pdf'):
        return jsonify({"error": "Only PDF files are supported"}), 400

    pdf_bytes = file.read()
    extracted_text = extract_text_from_pdf(io.BytesIO(pdf_bytes))

    net_pay = extract_value("Net Pay", extracted_text)
    employment_type = extract_employment_type(extracted_text)

    return jsonify({
        "NetPay": net_pay,
        "EmploymentType": employment_type
    })

if __name__ == '__main__':
    app.run(debug=True, port=5000)
