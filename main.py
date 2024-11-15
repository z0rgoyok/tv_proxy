from flask import Flask, Response, request
import requests
import re
from urllib.parse import urljoin

app = Flask(__name__)


def modify_m3u8_content(content, base_url, proxy_base_url):
    """
    Модифицирует содержимое M3U8 плейлиста, заменяя URL-адреса на прокси-версии
    """
    lines = content.decode("utf-8").split("\n")
    modified_lines = []

    for line in lines:
        if line.startswith("#"):
            # Обработка URI в тегах (например, #EXT-X-KEY:URI=")
            if 'URI="' in line:
                modified_line = re.sub(
                    r'URI="([^"]+)"',
                    lambda m: f'URI="{proxy_base_url}/proxy?url={urljoin(base_url, m.group(1))}"',
                    line,
                )
                modified_lines.append(modified_line)
            else:
                modified_lines.append(line)
        elif line.strip():
            # Обработка URL сегментов
            absolute_url = urljoin(base_url, line.strip())
            proxy_url = f"{proxy_base_url}/proxy?url={absolute_url}"
            modified_lines.append(proxy_url)
        else:
            modified_lines.append(line)

    return "\n".join(modified_lines)


@app.route("/proxy")
def proxy():
    """
    Обрабатывает запросы на проксирование как для M3U8 плейлистов, так и для медиа-сегментов
    """
    url = request.args.get("url")
    if not url:
        return "URL parameter is required", 400

    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
        }
        response = requests.get(url, headers=headers, stream=True)

        # Определяем базовый URL для относительных путей
        base_url = "/".join(url.split("/")[:-1]) + "/"

        content_type = response.headers.get("content-type", "")

        if "application/vnd.apple.mpegurl" in content_type or url.endswith(".m3u8"):
            # Обработка M3U8 плейлиста
            content = response.content
            proxy_base_url = f"{request.scheme}://{request.host}"
            modified_content = modify_m3u8_content(content, base_url, proxy_base_url)

            # Добавляем специфичные заголовки для M3U8
            response_headers = {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type",
                "Content-Type": "application/vnd.apple.mpegurl",
                "Content-Disposition": "inline",
                "Cache-Control": "no-cache",
                "X-Content-Type-Options": "nosniff",
            }

            return Response(modified_content, headers=response_headers)
        else:
            # Для медиа-сегментов
            response_headers = {
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, OPTIONS",
                "Access-Control-Allow-Headers": "Content-Type",
                "Content-Type": response.headers.get("content-type"),
                "Content-Length": response.headers.get("content-length"),
                "Accept-Ranges": response.headers.get("accept-ranges"),
                "Content-Range": response.headers.get("content-range"),
                "Cache-Control": "no-cache",
            }

            return Response(
                response.iter_content(chunk_size=8192),
                headers=response_headers,
                status=response.status_code,
                direct_passthrough=True,
            )

    except Exception as e:
        return str(e), 500


@app.route("/health")
def health():
    return "OK", 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5001)
