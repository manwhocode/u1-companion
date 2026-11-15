"""Pure nginx transformation used by the backup-first AI installer."""
BEGIN = '    # BEGIN U1 COMPANION AI\n'
END = '    # END U1 COMPANION AI\n'
BLOCK = BEGIN + '''    location /u1-ai/api/ {
        proxy_pass http://127.0.0.1:4547;
        proxy_set_header Host $host;
        proxy_set_header X-U1-Origin "$scheme://$http_host";
        proxy_set_header X-U1-AI-Session $http_x_u1_ai_session;
        proxy_set_header Origin $http_origin;
        proxy_set_header Referer $http_referer;
        proxy_connect_timeout 3s;
        proxy_read_timeout 20s;
        client_max_body_size 128k;
        add_header Cache-Control "no-store" always;
    }
''' + END


def nginx(text):
    if BEGIN in text or END in text:
        if text.count(BEGIN) != 1 or text.count(END) != 1:
            raise ValueError('Неоднозначная конфигурация AI proxy.')
        start, end = text.index(BEGIN), text.index(END) + len(END)
        return text[:start] + BLOCK + text[end:]
    import re
    starts = list(re.finditer(r'(?m)^\s*server\s*\{\s*\n', text))
    # U1 HTTPS also has a separate certificate-download server on 8081.
    # Add the API only to the main HTTPS server, never the download listener.
    known_https = (len(starts) == 2
                   and re.search(r'(?m)^\s*listen 443 ssl;', text[starts[0].end():starts[1].start()])
                   and re.search(r'(?m)^\s*listen 8081;', text[starts[1].end():])
                   and 'location / { return 404; }' in text[starts[1].end():])
    if (len(starts) != 1 and not known_https) or '/u1-ai/api/' in text:
        raise ValueError('Неизвестная конфигурация nginx; автоматическое изменение запрещено.')
    at = starts[0].end()
    return text[:at] + BLOCK + text[at:]
