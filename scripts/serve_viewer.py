import argparse
import io
import os
import re
from functools import partial
from http import HTTPStatus
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from roadgraphtool.viewer import STATIC_DIR

parser = argparse.ArgumentParser(
    description="Serve a viewer built by the `viewer` component locally. The HTML/JS/CSS files are served directly from "
                "the Road Graph Tool sources, so changes to them are visible after reloading the page, without "
                "rebuilding the viewer."
)
parser.add_argument("dir", type=Path, help="the viewer directory (`viewer.dir` of the config)")
parser.add_argument("--port", type=int, default=8000, help="port of the server (default: 8000)")
args = parser.parse_args()


class ViewerRequestHandler(SimpleHTTPRequestHandler):
    # explicit types, because on Windows, the system registry may map .js to text/plain, which browsers refuse to run
    extensions_map = {
        **SimpleHTTPRequestHandler.extensions_map,
        ".html": "text/html",
        ".js": "text/javascript",
        ".css": "text/css",
        ".json": "application/json",
        ".pmtiles": "application/octet-stream",
        ".bin": "application/octet-stream",
    }

    def translate_path(self, path):
        local_path = Path(super().translate_path(path))
        if local_path == Path(self.directory):
            local_path = local_path / "index.html"
        static_path = STATIC_DIR / local_path.name
        if local_path.parent == Path(self.directory) and static_path.exists():
            return str(static_path)
        return str(local_path)

    def end_headers(self):
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def send_head(self):
        """Adds the support of single byte ranges (``Range: bytes=start-end``) needed by the PMTiles library."""
        range_header = self.headers.get("Range")
        path = self.translate_path(self.path)
        if range_header is None or not os.path.isfile(path):
            return super().send_head()

        size = os.path.getsize(path)
        match = re.fullmatch(r"bytes=(\d+)-(\d*)", range_header)
        start = int(match[1]) if match else size
        end = min(int(match[2]), size - 1) if match and match[2] else size - 1
        if start > end:
            self.send_error(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
            return None

        with open(path, "rb") as file:
            file.seek(start)
            data = file.read(end - start + 1)
        self.send_response(HTTPStatus.PARTIAL_CONTENT)
        self.send_header("Content-Type", self.guess_type(path))
        self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        return io.BytesIO(data)


viewer_dir = args.dir.resolve()
server = ThreadingHTTPServer(("127.0.0.1", args.port), partial(ViewerRequestHandler, directory=str(viewer_dir)))
print(f"Serving {viewer_dir} at http://localhost:{args.port}/ (Ctrl+C to stop)")
try:
    server.serve_forever()
except KeyboardInterrupt:
    pass
