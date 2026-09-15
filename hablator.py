import base64
import json
import os
import urllib.request
import urllib.parse
from http.server import BaseHTTPRequestHandler, HTTPServer


API_URL = os.environ["API_URL"]
API_AUTH = base64.b64encode(f"api:{os.environ['API_AUTH']}".encode()).decode()
FROM_EMAIL = os.environ["FROM_EMAIL"]
BCC_EMAIL = os.environ["BCC_EMAIL"]


def send_email(to_list: list[str], subject: str, text: str) -> tuple[int, str]:
    data = urllib.parse.urlencode({
        "from": FROM_EMAIL,
        "to": ", ".join(to_list),
        "bcc": BCC_EMAIL,
        "subject": subject,
        "html": text,
    }).encode("utf-8")

    req = urllib.request.Request(
        API_URL,
        data=data,
        headers={"Authorization": f"Basic {API_AUTH}"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != "/send-email":
            self._reply(404, {"error": "Not found"})
            return

        encoding = self.headers.get("Transfer-Encoding", "").lower()
        length = self.headers.get("Content-Length")

        if encoding == "chunked":
            body = self.read_chunked(self.rfile)
        elif length:
            body = self.rfile.read(int(length))
        else:
            body = self.rfile.read()

        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            self._reply(400, {"error": "Invalid JSON"})
            return

        emails = payload.get("emails")
        subject = payload.get("subject", "")
        text = payload.get("text", "")

        if not emails or not isinstance(emails, list):
            self._reply(400, {"error": "'emails' must be a non-empty list"})
            return

        if not subject or not text:
            self._reply(400, {"error": "'subject' and 'text' are required"})
            return

        status, response = send_email(emails, subject, text)

        if 200 <= status < 300:
            self._reply(200, {"message": "Emails sent successfully", "response": response})
        else:
            self._reply(502, {"error": "Failed to send emails", "response": response})

    def _reply(self, code: int, body: dict):
        payload = json.dumps(body).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, fmt, *args):
        print(f"[{self.address_string()}] {fmt % args}")

    def read_chunked(self, rfile) -> bytes:
        chunks = []
        while True:
            size_line = rfile.readline().strip()
            size = int(size_line, 16)
            if size == 0:
                break
            chunks.append(rfile.read(size))
            rfile.read(2)  # consume trailing \r\n after chunk data
        return b"".join(chunks)


if __name__ == "__main__":
    server = HTTPServer(("0.0.0.0", 80), Handler)
    print("Server running at http://0.0.0.0:80")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")