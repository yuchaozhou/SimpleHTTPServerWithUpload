#!/usr/bin/env python3

"""Simple HTTP Server With Upload for Python 3.

This module builds on http.server by implementing the standard GET
and HEAD requests in a fairly straightforward manner, with added
file upload functionality.

"""

__version__ = "1.0"
__all__ = ["SimpleHTTPRequestHandler"]

import os
import posixpath
import http.server
import urllib.parse
import cgi
import shutil
import mimetypes
import re
import html
from io import StringIO, BytesIO


class SimpleHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    """Simple HTTP request handler with GET/HEAD/POST commands.

    This serves files from the current directory and any of its
    subdirectories. The MIME type for files is determined by
    calling the .guess_type() method. And can receive file uploaded
    by client.

    The GET/HEAD/POST requests are identical except that the HEAD
    request omits the actual contents of the file.
    """

    server_version = "SimpleHTTPWithUpload/" + __version__

    def do_POST(self):
        """Serve a POST request."""
        r, info = self.deal_post_data()
        print(r, info, "by:", self.client_address)
        
        # Create response HTML
        html_content = f'''<!DOCTYPE html>
<html>
<head>
    <title>Upload Result Page</title>
    <meta charset="utf-8">
</head>
<body>
    <h2>Upload Result Page</h2>
    <hr>
    <p><strong>{"Success" if r else "Failed"}:</strong> {html.escape(info)}</p>
    <p><a href="{self.headers.get('referer', '/')}">Back</a></p>
    <hr>
    <small>Powered By: Python 3 SimpleHTTPServerWithUpload</small>
</body>
</html>'''
        
        # Send response
        content = html_content.encode('utf-8')
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def deal_post_data(self):
        """Handle POST data for file upload."""
        try:
            content_type = self.headers.get('content-type')
            if not content_type:
                return (False, "Content-Type header is missing")
            
            if not content_type.startswith('multipart/form-data'):
                return (False, "Content-Type is not multipart/form-data")
            
            # Parse the boundary
            boundary = content_type.split("boundary=")[1].encode('utf-8')
            content_length = int(self.headers.get('content-length', 0))
            
            if content_length <= 0:
                return (False, "No data received")
            
            # Read the entire POST data
            post_data = self.rfile.read(content_length)
            
            # Split by boundary
            parts = post_data.split(b'--' + boundary)
            
            for part in parts:
                if b'Content-Disposition' in part and b'filename=' in part:
                    # Extract filename
                    lines = part.split(b'\r\n')
                    filename = None
                    content_start = 0
                    
                    for i, line in enumerate(lines):
                        if b'Content-Disposition' in line:
                            # Extract filename using regex
                            match = re.search(rb'filename="([^"]*)"', line)
                            if match:
                                filename = match.group(1).decode('utf-8')
                        elif line == b'':
                            content_start = i + 1
                            break
                    
                    if filename and content_start < len(lines):
                        # Get file content (excluding the last \r\n--)
                        file_content = b'\r\n'.join(lines[content_start:])
                        if file_content.endswith(b'\r\n'):
                            file_content = file_content[:-2]
                        
                        # Save file
                        path = self.translate_path(self.path)
                        if not os.path.isdir(path):
                            path = os.path.dirname(path)
                        
                        filepath = os.path.join(path, filename)
                        
                        try:
                            with open(filepath, 'wb') as f:
                                f.write(file_content)
                            return (True, f"File '{filename}' uploaded successfully!")
                        except IOError as e:
                            return (False, f"Can't save file: {str(e)}")
            
            return (False, "No file found in upload data")
            
        except Exception as e:
            return (False, f"Error processing upload: {str(e)}")

    def list_directory(self, path):
        """Helper to produce a directory listing (absent index.html)."""
        try:
            file_list = os.listdir(path)
        except OSError:
            self.send_error(404, "No permission to list directory")
            return None
        
        file_list.sort(key=lambda a: a.lower())
        
        displaypath = html.escape(urllib.parse.unquote(self.path), quote=False)
        
        html_content = f'''<!DOCTYPE html>
<html>
<head>
    <title>Directory listing for {displaypath}</title>
    <meta charset="utf-8">
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        .upload-form {{ 
            background: #f5f5f5; 
            padding: 20px; 
            border-radius: 5px; 
            margin: 20px 0; 
        }}
        .file-list {{ list-style-type: none; padding: 0; }}
        .file-list li {{ 
            padding: 8px; 
            border-bottom: 1px solid #eee; 
        }}
        .file-list a {{ 
            text-decoration: none; 
            color: #0066cc; 
        }}
        .file-list a:hover {{ text-decoration: underline; }}
        .directory {{ font-weight: bold; }}
        .symlink {{ font-style: italic; }}
    </style>
</head>
<body>
    <h2>Directory listing for {displaypath}</h2>
    
    <div class="upload-form">
        <h3>Upload File</h3>
        <form enctype="multipart/form-data" method="post">
            <input name="file" type="file" required>
            <input type="submit" value="Upload">
        </form>
    </div>
    
    <hr>
    <ul class="file-list">'''

        for name in file_list:
            fullname = os.path.join(path, name)
            displayname = linkname = name
            css_class = ""
            
            # Append / for directories or @ for symbolic links
            if os.path.isdir(fullname):
                displayname = name + "/"
                linkname = name + "/"
                css_class = ' class="directory"'
            elif os.path.islink(fullname):
                displayname = name + "@"
                css_class = ' class="symlink"'
            
            html_content += f'''        <li{css_class}>
            <a href="{urllib.parse.quote(linkname, safe='/')}">{html.escape(displayname)}</a>
        </li>
'''

        html_content += '''    </ul>
    <hr>
</body>
</html>'''
        
        content = html_content.encode('utf-8')
        
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        
        return BytesIO(content)

    def translate_path(self, path):
        """Translate a /-separated PATH to the local filename syntax."""
        # abandon query parameters
        path = path.split('?', 1)[0]
        path = path.split('#', 1)[0]
        path = posixpath.normpath(urllib.parse.unquote(path))
        words = path.split('/')
        words = [word for word in words if word]  # filter out empty strings
        path = os.getcwd()
        for word in words:
            drive, word = os.path.splitdrive(word)
            head, word = os.path.split(word)
            if word in (os.curdir, os.pardir):
                continue
            path = os.path.join(path, word)
        return path


def run_server(port=8000, bind=''):
    """Run the HTTP server."""
    server_address = (bind, port)
    httpd = http.server.HTTPServer(server_address, SimpleHTTPRequestHandler)
    
    print(f"Serving HTTP on {bind if bind else 'all interfaces'} port {port} ...")
    print(f"Server URL: http://localhost:{port}/")
    print("Press Ctrl+C to stop the server")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nServer stopped.")
        httpd.server_close()


if __name__ == '__main__':
    import argparse
    
    parser = argparse.ArgumentParser(description='Simple HTTP Server with Upload')
    parser.add_argument('--port', '-p', default=8000, type=int, 
                       help='Specify alternate port (default: 8000)')
    parser.add_argument('--bind', '-b', default='', metavar='ADDRESS',
                       help='Specify alternate bind address (default: all interfaces)')
    
    args = parser.parse_args()
    run_server(port=args.port, bind=args.bind) 