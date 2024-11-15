from flask import Flask, Response, request
import requests
import re
from urllib.parse import urljoin, urlparse, quote
import logging

# Debug logging control
DEBUG_LOGGING = False

app = Flask(__name__)

# Configure logging based on DEBUG_LOGGING constant
if DEBUG_LOGGING:
    logging.basicConfig(level=logging.DEBUG)
else:
    logging.basicConfig(level=logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)
    logging.getLogger('urllib3').setLevel(logging.WARNING)


def modify_m3u8_content(content, base_url, proxy_base_url):
    """
    Modifies M3U8 playlist content by replacing URLs with proxy versions.
    """
    lines = content.split("\n")
    modified_lines = []

    for line in lines:
        if line.startswith("#"):
            # Handle URI tags (e.g., #EXT-X-KEY:URI="...")
            if 'URI="' in line:
                modified_line = re.sub(
                    r'URI="([^"]+)"',
                    lambda m: f'URI="{proxy_base_url}/proxy?url={quote(m.group(1), safe="")}"',
                    line,
                )
                app.logger.debug(f"Modified URI Line: {modified_line}")
                modified_lines.append(modified_line)
            else:
                modified_lines.append(line)
        elif line.strip():
            # Handle URL segments
            if line.strip().startswith(('http://', 'https://')):
                absolute_url = line.strip()
            else:
                absolute_url = urljoin(base_url, line.strip())
            proxy_url = f"{proxy_base_url}/proxy?url={quote(absolute_url, safe='')}"
            app.logger.debug(f"Rewritten Segment URL: {proxy_url}")
            modified_lines.append(proxy_url)
        else:
            modified_lines.append(line)

    modified_content = "\n".join(modified_lines)
    app.logger.debug(f"Modified M3U8 Content Length: {len(modified_content)}")
    return modified_content


@app.route("/proxy")
def proxy():
    """
    Handles proxy requests for M3U8 playlists and media segments.
    """
    url = request.args.get("url")
    app.logger.debug(f"Received URL: {url}")
    if not url:
        return "URL parameter is required", 400

    # Validate the URL
    parsed_url = urlparse(url)
    if not parsed_url.scheme or not parsed_url.netloc:
        return "Invalid URL parameter", 400

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Accept": "*/*",
            "Connection": "keep-alive"
        }

        # Fetch the content from the upstream server
        response = requests.get(url, headers=headers, stream=True, allow_redirects=True, timeout=30)

        app.logger.debug(f"Upstream server responded with status code: {response.status_code}")

        if response.status_code != 200:
            app.logger.error(f"Upstream server returned {response.status_code}")
            return f"Upstream server returned {response.status_code}", response.status_code

        # Determine the base URL for relative paths
        base_url = url.rsplit('/', 1)[0] + "/"
        app.logger.debug(f"Base URL: {base_url}")

        # Get and normalize the content type
        content_type = response.headers.get("content-type", "").lower()
        app.logger.debug(f"Content-Type from upstream: {content_type}")

        # Updated condition to check for any 'mpegurl' in content-type
        if "mpegurl" in content_type or url.endswith(".m3u8"):
            # Handle M3U8 playlist
            try:
                content = response.content.decode("utf-8")
            except UnicodeDecodeError as e:
                app.logger.error(f"Error decoding content: {e}")
                return f"Error decoding content: {str(e)}", 500

            proxy_base_url = f"{request.scheme}://{request.host}"
            modified_content = modify_m3u8_content(content, base_url, proxy_base_url)

            response_headers = {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type",
                "Content-Type": "application/vnd.apple.mpegurl; charset=utf-8",
                "Content-Disposition": "inline",
                "Cache-Control": "no-cache",
                "X-Content-Type-Options": "nosniff",
            }

            app.logger.debug(f"Returning modified M3U8 content with length: {len(modified_content)}")
            return Response(modified_content, headers=response_headers, mimetype="application/vnd.apple.mpegurl; charset=utf-8")
        else:
            # Handle media segments
            response_headers = {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type",
                "Content-Type": response.headers.get("content-type"),
                # Let Flask handle Content-Length
                "Accept-Ranges": response.headers.get("accept-ranges"),
                "Cache-Control": "no-cache",
            }

            app.logger.debug("Proxying media segment content.")
            return Response(
                response.iter_content(chunk_size=8192),
                headers=response_headers,
                status=response.status_code,
                direct_passthrough=True,
            )

    except requests.exceptions.RequestException as e:
        app.logger.exception("A requests exception occurred while proxying the request")
        return f"Request exception: {str(e)}", 500
    except Exception as e:
        app.logger.exception("An unexpected error occurred while proxying the request")
        return f"Unexpected error: {str(e)}", 500


@app.route("/health")
def health():
    return "OK", 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
