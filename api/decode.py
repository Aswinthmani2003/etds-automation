from flask import Flask, request, jsonify
import fitz
from pyzbar.pyzbar import decode
from PIL import Image
import traceback

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
            return jsonify({'success': False, 'barcode': None, 'error': f'PDF open failed: {str(e)}'}), 200

        barcodes_found = []
        max_pages = min(pdf.page_count, 5)

        for page_num in range(max_pages):
            try:
                page = pdf[page_num]
                pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))

                if pix.n - pix.alpha < 3:
                    continue

                img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)

                try:
                    decoded = decode(img)
                    for obj in decoded:
                        try:
                            barcode_data = obj.data.decode('utf-8')
                            digits = ''.join(c for c in barcode_data if c.isdigit())
                            if len(digits) >= 15:
                                barcodes_found.append(digits)
                        except:
                            pass
                except Exception as pyzbar_error:
                    pass

            except Exception as page_error:
                pass

        pdf.close()

        if barcodes_found:
            return jsonify({'success': True, 'barcode': barcodes_found[0]})
        else:
            return jsonify({'success': False, 'barcode': None})

    except Exception as e:
        return jsonify({'success': False, 'barcode': None, 'error': f'Server error: {str(e)}'}), 200
