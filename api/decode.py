from flask import Flask, request, jsonify
import fitz
import re

app = Flask(__name__)

@app.route('/api/decode', methods=['POST'])
def decode_pdf():
    try:
        if 'pdf' not in request.files:
            return jsonify({'success': False, 'barcode': None}), 200

        pdf_file = request.files['pdf']
        pdf_bytes = pdf_file.read()

        if not pdf_bytes:
            return jsonify({'success': False, 'barcode': None}), 200

        try:
            pdf = fitz.open(stream=pdf_bytes, filetype="pdf")
        except:
            return jsonify({'success': False, 'barcode': None}), 200

        barcodes_found = []
        max_pages = min(pdf.page_count, 5)

        for page_num in range(max_pages):
            try:
                page = pdf[page_num]
                text = page.get_text()

                numbers = re.findall(r'\d{15,20}', text)
                barcodes_found.extend(numbers)

            except:
                pass

        pdf.close()

        if barcodes_found:
            return jsonify({'success': True, 'barcode': barcodes_found[0]})
        else:
            return jsonify({'success': False, 'barcode': None})

    except:
        return jsonify({'success': False, 'barcode': None}), 200
