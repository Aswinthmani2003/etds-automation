from flask import Flask, request, jsonify
from openpyxl import load_workbook
import re
import io

app = Flask(__name__)

def extract_digits(text):
    if text is None:
        return ""
    return re.sub(r'[^0-9]', '', str(text))

def parse_excel(excel_file):
    try:
        wb = load_workbook(excel_file)
        token_map = {}

        for sheet_name in wb.sheetnames:
            sheet = wb[sheet_name]
            rows = list(sheet.iter_rows(values_only=True))

            for row in rows:
                if not row or len(row) < 2:
                    continue

                token = None
                target = None

                for cell in row:
                    if cell is None:
                        continue
                    d = extract_digits(cell)
                    if len(d) == 20 and not token:
                        token = d
                    if len(d) == 15 and not target:
                        target = d

                if token and target:
                    if token not in token_map:
                        token_map[token] = target

        return token_map
    except Exception as e:
        raise Exception(f"Excel parsing failed: {str(e)}")

@app.route('/api/process', methods=['POST'])
def process():
    try:
        if 'excel' not in request.files:
            return jsonify({'error': 'No Excel file provided'}), 400
        if 'pdfs' not in request.files or len(request.files.getlist('pdfs')) == 0:
            return jsonify({'error': 'No PDF files provided'}), 400

        excel_file = request.files['excel']
        pdf_files = request.files.getlist('pdfs')

        # Parse Excel
        try:
            token_map = parse_excel(excel_file)
            if not token_map:
                return jsonify({'error': 'No valid token/receipt pairs found in Excel'}), 400
        except Exception as e:
            return jsonify({'error': f'Excel error: {str(e)}'}), 400

        # Process PDFs - for now, just return them with placeholder tokens
        results = []
        matched = 0
        unmatched = 0

        for pdf_file in pdf_files:
            filename = pdf_file.filename

            # Try to extract token from filename as fallback
            token_from_name = extract_digits(filename)

            row = {
                'original': filename,
                'token': '',
                'newName': '',
                'status': '',
                'reason': ''
            }

            # Check if filename contains a barcode-like number
            if len(token_from_name) >= 15:
                token = token_from_name
                row['token'] = token

                # Match against Excel
                receipt = token_map.get(token)
                if receipt:
                    row['newName'] = receipt + '.pdf'
                    row['status'] = 'matched'
                    matched += 1
                else:
                    row['status'] = 'unmatched'
                    row['reason'] = 'Barcode not in Excel'
                    unmatched += 1
            else:
                row['status'] = 'unmatched'
                row['reason'] = 'No barcode in filename'
                unmatched += 1

            results.append(row)

        return jsonify({
            'success': True,
            'results': results,
            'matched': matched,
            'unmatched': unmatched,
            'total': len(results),
            'note': 'Barcode extraction requires PDF processing - uploading renamed files with barcodes in filenames works best'
        })

    except Exception as e:
        return jsonify({'error': f'Server error: {str(e)}'}), 500

if __name__ == '__main__':
    app.run(debug=True)
