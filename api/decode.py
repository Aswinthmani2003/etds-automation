from flask import Flask, request, jsonify
import fitz
from pyzbar.pyzbar import decode
from PIL import Image
import io

app = Flask(__name__)

@app.route('/api/decode', methods=['POST'])
def decode_pdf():
    if 'pdf' not in request.files:
        return jsonify({'error': 'No PDF provided'}), 400

    pdf_file = request.files['pdf']

    try:
        pdf_bytes = pdf_file.read()
        pdf = fitz.open(stream=pdf_bytes, filetype="pdf")

        barcodes_found = []

        for page_num in range(min(pdf.page_count, 5)):
            page = pdf[page_num]
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

            decoded = decode(img)
            for obj in decoded:
                barcode_data = obj.data.decode('utf-8')
                digits = ''.join(c for c in barcode_data if c.isdigit())
                if len(digits) >= 15:
                    barcodes_found.append(digits)

        pdf.close()

        if barcodes_found:
            return jsonify({'success': True, 'barcode': barcodes_found[0]})
        else:
            return jsonify({'success': False, 'barcode': None, 'error': 'No barcode detected'})

    except Exception as e:
        return jsonify({'error': str(e)}), 500
