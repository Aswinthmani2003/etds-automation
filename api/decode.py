from flask import Flask, request, jsonify
import fitz
from PIL import Image
import easyocr
import re

app = Flask(__name__)

# Initialize OCR reader once
reader = None

def get_ocr_reader():
    global reader
    if reader is None:
        try:
            reader = easyocr.Reader(['en'], gpu=False)
        except:
            reader = None
    return reader

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

        ocr_reader = get_ocr_reader()
        if ocr_reader is None:
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
                img_array = __import__('numpy').array(img)

                try:
                    results = ocr_reader.readtext(img_array)
                    for detection in results:
                        text = detection[1]
                        numbers = re.findall(r'\d+', text)
                        for num in numbers:
                            if len(num) >= 15:
                                barcodes_found.append(num)
                except:
                    pass

            except:
                pass

        pdf.close()

        if barcodes_found:
            return jsonify({'success': True, 'barcode': barcodes_found[0]})
        else:
            return jsonify({'success': False, 'barcode': None})

    except:
        return jsonify({'success': False, 'barcode': None}), 200
