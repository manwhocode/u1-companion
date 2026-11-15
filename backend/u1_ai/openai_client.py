"""Fixed-origin Responses API transport. No secret-bearing redirects or automatic retries."""
import json
import urllib.error
import urllib.request


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class OpenAIError(Exception):
    pass


def api_error(error):
    # Inspect only fixed machine-readable codes; never echo the response body.
    if error.code == 429:
        code = ''
        try:
            body = error.read(65537)
            if len(body) <= 65536:
                value = json.loads(body).get('error', {})
                code = value.get('code') or value.get('type')
        except Exception:
            pass
        if code in ('insufficient_quota', 'billing_hard_limit_reached', 'billing_not_active'):
            return 'OpenAI API: нет доступной квоты или достигнут лимит оплаты. Проверьте баланс и лимиты API-проекта в OpenAI Platform. Повтор позже сам по себе это не исправит.'
        if code == 'rate_limit_exceeded':
            return 'OpenAI временно ограничил частоту запросов. Подождите и повторите вручную. Автоматического повтора нет.'
        return 'OpenAI вернул HTTP 429. Причина не уточнена: проверьте квоту API и ограничения частоты запросов в OpenAI Platform.'
    return {401: 'OpenAI отклонил API-ключ.', 403: 'Модель или проект недоступны.',
            400: 'OpenAI отклонил параметры запроса. Проверьте поддержку выбранной модели.'}.get(error.code, 'OpenAI вернул HTTP ' + str(error.code))


class OpenAIClient:
    def __init__(self, key, opener=None):
        self.key = key
        self.opener = opener or urllib.request.build_opener(NoRedirect())

    def request(self, path, payload=None):
        if path not in ('responses', 'models'):
            raise ValueError('Неизвестный метод OpenAI.')
        raw = None if payload is None else json.dumps(payload, ensure_ascii=False, allow_nan=False).encode()
        if raw is not None and len(raw) > 1024 * 1024:
            raise OpenAIError('Контекст запроса слишком большой. Начните новый диалог или уменьшите его объём.')
        req = urllib.request.Request('https://api.openai.com/v1/' + path, data=raw,
                                     headers={'Authorization': 'Bearer ' + self.key, 'Content-Type': 'application/json'})
        try:
            with self.opener.open(req, timeout=120) as response:
                data = response.read(4 * 1024 * 1024 + 1)
                if len(data) > 4 * 1024 * 1024:
                    raise OpenAIError('Ответ OpenAI слишком большой.')
                return json.loads(data)
        except urllib.error.HTTPError as error:
            # Never echo server bodies, request headers or keys into browser/logs.
            raise OpenAIError(api_error(error)) from None
        except (TimeoutError, urllib.error.URLError):
            raise OpenAIError('Нет подтверждённого ответа OpenAI. Автоматического повтора нет.') from None

    def models(self):
        return sorted(row['id'] for row in self.request('models').get('data', []) if isinstance(row.get('id'), str))

    def response(self, settings, items, tools):
        return self.request('responses', {'model': settings['model'], 'input': items, 'tools': tools,
                                         'store': False, 'parallel_tool_calls': False,
                                         'max_output_tokens': settings['maxOutputTokens'],
                                         'include': ['reasoning.encrypted_content']})

class ChatGPTClient(OpenAIClient):
    """Account-token transport; a completed SSE event is the only success signal."""
    def models(self):
        return [r['slug'] for r in self.request('models').get('models', []) if r.get('visibility') == 'list' and isinstance(r.get('slug'),str)]

    def response(self, settings, items, tools):
        payload={'model':settings['model'],'input':items,'store':False,'stream':True,
                 'tools':[{'type':'namespace','name':'u1','description':'U1 Companion tools','tools':tools}],
                 'parallel_tool_calls':False,'include':['reasoning.encrypted_content']}
        req=urllib.request.Request('https://api.openai.com/v1/responses',data=json.dumps(payload).encode(),headers={'Authorization':'Bearer '+self.key,'Content-Type':'application/json'})
        try:
            with self.opener.open(req,timeout=120) as response:
                return parse_events(response)
        except urllib.error.HTTPError as e:
            raise OpenAIError('ChatGPT отклонил запрос (HTTP '+str(e.code)+'). Проверьте доступ модели и лимит аккаунта.') from None
        except (TimeoutError,urllib.error.URLError):raise OpenAIError('Ответ ChatGPT не подтверждён; автоматического повтора нет.') from None

def parse_events(response):
    total=0;data=[]
    for raw in response:
        total+=len(raw)
        if total>4*1024*1024 or len(raw)>4*1024*1024:raise OpenAIError('Ответ ChatGPT слишком большой.')
        line=raw.decode('utf-8').rstrip('\r\n')
        if line.startswith('data:'):data.append(line[5:].lstrip())
        elif not line and data:
            text='\n'.join(data);data=[]
            if text=='[DONE]':break
            event=json.loads(text)
            if event.get('type')=='response.completed':
                value=event['response']
                for item in value.get('output',[]):
                    if item.get('type')=='function_call' and item.get('namespace') not in (None,'u1'):raise OpenAIError('Неизвестное пространство инструментов.')
                return value
            if event.get('type') in ('response.failed','response.incomplete','error'):raise OpenAIError('ChatGPT не завершил ответ. Проверьте лимит аккаунта; автоматического повтора нет.')
    raise OpenAIError('Поток ChatGPT прерван до подтверждения ответа. Повтор не отправлен.')
