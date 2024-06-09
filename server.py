import os
from http.server import HTTPServer, BaseHTTPRequestHandler
import cgi
import pandas as pd
from datetime import timedelta
from io import BytesIO

class SimpleHTTPRequestHandler(BaseHTTPRequestHandler):

    def _set_headers(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()

    def _set_download_headers(self, filename):
        self.send_response(200)
        self.send_header('Content-type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
        self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
        self.end_headers()

    def do_GET(self):
        self._set_headers()
        self.wfile.write(b'''
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>File Upload</title>
            <link href="https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/css/bootstrap.min.css" rel="stylesheet">
            <style>
                body, html {
                    height: 100%;
                }
                .container {
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    height: 100%;
                }
                .form-container {
                    border: 1px solid #ced4da;
                    border-radius: 0.25rem;
                    padding: 2rem;
                    background-color: #fff;
                    box-shadow: 0 0.125rem 0.25rem rgba(0, 0, 0, 0.075);
                }
            </style>
        </head>
        <body>
            <div class="container">
                <div class="form-container">
                    <h1 class="mb-4 text-center">Upload Files</h1>
                    <form id="uploadForm" action="/upload" method="post" enctype="multipart/form-data" class="needs-validation" novalidate>
                        <div class="input-group form-group mb-3">
                            <label for="file1">Upload Statement from Bank:</label>
                            <input type="file" class="form-control-file" id="file1" name="file1" required>
                            <div class="invalid-feedback">Please upload the bank statement.</div>
                        </div>
                        <hr>
                        <div class="input-group form- mb-3">
                            <label for="file2">Upload Statement from Remita (Bookfinance):</label>
                            <input type="file" class="form-control-file" id="file2" name="file2" required>
                            <div class="invalid-feedback">Please upload the Remita statement.</div>
                        </div>
                        <button type="submit" class="btn btn-primary btn-block">Upload and Process</button>
                    </form>
                </div>
            </div>

            <script src="https://code.jquery.com/jquery-3.5.1.slim.min.js"></script>
            <script src="https://cdn.jsdelivr.net/npm/@popperjs/core@2.9.3/dist/umd/popper.min.js"></script>
            <script src="https://stackpath.bootstrapcdn.com/bootstrap/4.5.2/js/bootstrap.min.js"></script>
            <script>
                (function() {
                    'use strict';
                    window.addEventListener('load', function() {
                        var forms = document.getElementsByClassName('needs-validation');
                        var validation = Array.prototype.filter.call(forms, function(form) {
                            form.addEventListener('submit', function(event) {
                                if (form.checkValidity() === false) {
                                    event.preventDefault();
                                    event.stopPropagation();
                                }
                                form.classList.add('was-validated');
                            }, false);
                        });
                    }, false);
                })();
            </script>
        </body>
        </html>
        ''')

    def do_POST(self):
        if self.path == '/upload':
            ctype, pdict = cgi.parse_header(self.headers['content-type'])
            if ctype == 'multipart/form-data':
                form = cgi.FieldStorage(fp=self.rfile, headers=self.headers, environ={'REQUEST_METHOD': 'POST'})
                file1 = form['file1'].file.read()
                file2 = form['file2'].file.read()

                df1 = pd.read_excel(BytesIO(file1))
                df2 = pd.read_excel(BytesIO(file2))

                # Transform data from TEST 2.xlsx
                df1['mandate_number'] = df1['Reference'].str.split(':').str[-1].astype(str)
                df1['date'] = pd.to_datetime(df1['Date'], dayfirst=True).dt.date
                df1['Amount'] = df1['Amount'].round(2)

                # Prepare data from TEST 1.xlsx
                df2['paymentdate'] = pd.to_datetime(df2['PaymentDate'], dayfirst=True).dt.date
                df2['CreditedAmount'] = df2['CreditedAmount'].round(2)
                df2['MandateRefID'] = df2['MandateRefID'].apply(lambda x: str(int(x)) if pd.notnull(x) else x)

                def find_matching_row(row):
                    matched_rows = df2[
                        (df2['MandateRefID'].str.contains(row['mandate_number'], na=False)) &
                        (df2['CreditedAmount'] == row['Amount']) &
                        (df2['paymentdate'] >= row['date'] - timedelta(days=7)) &
                        (df2['paymentdate'] <= row['date'] + timedelta(days=7))
                    ]
                    return matched_rows

                results = pd.concat(df1.apply(find_matching_row, axis=1).tolist())

                output = BytesIO()
                with pd.ExcelWriter(output, engine='openpyxl') as writer:
                    results.to_excel(writer, sheet_name='Matching Results', index=False)
                output.seek(0)

                self._set_download_headers("matching_results.xlsx")
                self.wfile.write(output.read())
                output.close()

def run(server_class=HTTPServer, handler_class=SimpleHTTPRequestHandler, port=8000):
    server_address = ('', port)
    httpd = server_class(server_address, handler_class)
    print(f'Starting httpd server on port {port}...')
    httpd.serve_forever()

if __name__ == '__main__':
    run()
