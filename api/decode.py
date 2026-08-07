from flask import Flask, request, jsonify
import fitz
from PIL import Image
import pytesseract
import re

app = Flask(__name__)

@app.route('/api/decode', methods=['POST'])
def decode_pdf():
    try:
        if 'pdf' not in request.files:
            return jsonify({'error': 'No PDF provided'}), 400

        pdf_file = request.files['pdf']
        pdf_bytes = pdf_file.read()

        if not pdf_bytes:
            return jsonify({'error': 'Empty PDF'}), 400

        try:
            pdf = fitz.open(stream=pdf_bytes, filetype="pdf")
        except Exception as e:
            return jsonify({'success': False, 'barcode': None}), 200

        barcodes_found = []
        max_pages = min(pdf.page_count, 5)

        for page_num in range(max_pages):
            try:
                page = pdf[page_num]
                pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))

                if pix.n - pix.alpha < 3:
                    continue

                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

                try:
                    text = pytesseract.image_to_string(img)
                    numbers = re.findall(r'\d+', text)
                    for num in numbers:
                        if len(num) >= 15:
                            barcodes_found.append(num)
                except Exception as ocr_error:
                    pass

            except Exception as page_error:
                pass

        pdf.close()

        if barcodes_found:
            return jsonify({'success': True, 'barcode': barcodes_found[0]})
        else:
            return jsonify({'success': False, 'barcode': None})

    except Exception as e:
        return jsonify({'success': False, 'barcode': None}), 200
