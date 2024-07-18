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

    def _set_error_headers(self, error_message=""):
        self.send_response(500)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(f"An error occurred: {error_message}".encode())

    def _set_success_headers(self, success_message=""):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        self.wfile.write(f"Success: {success_message}".encode())

    def do_GET(self):
        self._set_headers()
        try:
            with open('index.html', 'rb') as file:
                self.wfile.write(file.read())
        except FileNotFoundError:
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"File not found.")

    def do_POST(self):
        if self.path == '/upload':
            try:
                ctype, pdict = cgi.parse_header(self.headers['content-type'])
                if ctype == 'multipart/form-data':
                    form = cgi.FieldStorage(fp=self.rfile, headers=self.headers, environ={'REQUEST_METHOD': 'POST'})
                    file1 = form['file1'].file.read()
                    file2 = form['file2'].file.read()

                    df1 = pd.read_excel(BytesIO(file1))
                    df2 = pd.read_excel(BytesIO(file2))

                    # Transform data from TEST 2.xlsx
                    df1['mandate_number'] = df1['MANDATE NUMBER'] # .str.split(':').str[-1].astype(str)
                    # df1['date'] = pd.to_datetime(df1['Date'], dayfirst=True).dt.date
                    # df1['Amount'] = df1['Amount'].round(2)

                    # Prepare data from TEST 1.xlsx
                   # df2['paymentdate'] = pd.to_datetime(df2['PaymentDate'], dayfirst=True).dt.date
                   # df2['CreditedAmount'] = df2['CreditedAmount'].round(2)
                    df2['MandateRefID'] = df2['MANDATENO'] #.apply(lambda x: str(int(x)) if pd.notnull(x) else x)

                    def find_matching_row(row):
                        matched_rows = df2[
                        (df2['MandateRefID'] == (row['mandate_number'])) 
                           # (df2['MandateRefID'].str.contains(row['mandate_number'], na=False)) 
                            #  &
                          #  (df2['CreditedAmount'] == row['Amount']) & (
                           # df2['paymentdate'] <= row['date'] + timedelta(days=7))
                            ]

                        return matched_rows

                    # Apply function to each row in df1 and concatenate results
                    results_list = []
                    unmatched_list = []

                    for _, row in df1.iterrows():
                        matched_rows = find_matching_row(row)
                        if not matched_rows.empty:
                            results_list.append(matched_rows)
                        else:
                            unmatched_list.append(row)

                    results = pd.concat(results_list, ignore_index=True) if results_list else pd.DataFrame()
                    unmatched = pd.DataFrame(unmatched_list)

                    output = BytesIO()
                    with pd.ExcelWriter(output, engine='openpyxl') as writer:
                        if not results.empty:
                            results.to_excel(writer, sheet_name='Matching Results', index=False)
                        if not unmatched.empty:
                            unmatched.to_excel(writer, sheet_name='Unmatched Results', index=False)
                    output.seek(0)

                    self._set_download_headers("results.xlsx")
                    self.wfile.write(output.read())
                    output.close()
                else:
                    self._set_error_headers("Unsupported content type.")
            except pd.errors.EmptyDataError:
                self._set_error_headers("Uploaded file is empty or not readable.")
            except pd.errors.ParserError:
                self._set_error_headers("Error parsing file. Ensure the file format is correct.")
            except Exception as e:
                self._set_error_headers(str(e))

def run(server_class=HTTPServer, handler_class=SimpleHTTPRequestHandler, port=8000):
    server_address = ('', port)
    httpd = server_class(server_address, handler_class)
    print(f'Starting httpd server on port {port}...')
    httpd.serve_forever()

if __name__ == '__main__':
    run()
