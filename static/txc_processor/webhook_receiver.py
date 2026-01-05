#!/usr/bin/env python3
"""
Simple webhook receiver to mark workflow completion
Runs on VM #1, receives callbacks from GitHub Actions
"""

from http.server import HTTPServer, BaseHTTPRequestHandler
import json
from pathlib import Path
import sys

TRACKING_DIR = Path("/home/ubuntu/pt-analytics/static/txc_processor/tracking")
PORT = 8765

class WebhookHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        # Read payload
        content_length = int(self.headers['Content-Length'])
        body = self.rfile.read(content_length)
        
        try:
            data = json.loads(body)
            workflow_type = data.get('type')  # 'monthly' or 'daily'
            status = data.get('status')       # 'success' or 'failed'
            
            if workflow_type == 'monthly':
                status_file = TRACKING_DIR / "monthly_status.txt"
                status_file.write_text(status)
                print(f"✓ Monthly workflow marked as: {status}")
                
            elif workflow_type == 'daily':
                status_file = TRACKING_DIR / "daily_status.txt"
                status_file.write_text(status)
                print(f"✓ Daily workflow marked as: {status}")
            
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b'OK')
            
        except Exception as e:
            print(f"Error: {e}")
            self.send_response(500)
            self.end_headers()
    
    def log_message(self, format, *args):
        # Suppress default logging
        pass

if __name__ == '__main__':
    TRACKING_DIR.mkdir(parents=True, exist_ok=True)
    
    server = HTTPServer(('0.0.0.0', PORT), WebhookHandler)
    print(f"Webhook receiver listening on port {PORT}...")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        sys.exit(0)
