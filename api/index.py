from http.server import BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import sys
import os
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip('/')
        params = parse_qs(parsed.query)
        
        # === Route: /api/index hoặc /api/index?action=scan ===
        if path in ["/api/index", ""]:
            action = params.get("action", ["scan"])[0]
            
            if action == "scan":
                from lib.scan_logic import do_scan
                do_scan(self, params)
            elif action == "check":
                # Check 1 mã ngay lập tức: ?action=check&symbol=VCB
                from lib.scan_logic import do_check_symbol
                do_check_symbol(self, params)
            else:
                self._json(400, {"error": "Unknown action. Use ?action=scan or ?action=check&symbol=VCB"})
        
        else:
            self._json(404, {"error": "Not found", "path": path})
    
    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path.rstrip('/')
        
        if path in ["/api/index", ""]:
            from lib.webhook_logic import do_webhook
            do_webhook(self)
        else:
            self._json(404, {"error": "Not found"})
    
    def _json(self, status, data):
        self.send_response(status)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))
