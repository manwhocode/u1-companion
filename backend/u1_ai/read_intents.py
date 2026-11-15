"""Conservative read-only prefetch; unknown messages stay with the model planner."""
import re

def reads_for(text):
    if not isinstance(text, str) or len(text) > 600:
        return []
    t = text.casefold()
    # Quoted examples, code and explanations must not trigger live telemetry.
    if any(x in t for x in ('```', '«', '»', '"', 'объясн', 'как работает', 'зачем', 'почему', 'что такое', 'перевед', 'translate', 'explain', 'why ', 'how does', 'was ist', 'erklär')):
        return []
    if re.search(r'рекоменд|для печати|какую.*(?:выбрать|ставить)|установи|нагрей|выключи|измени|recommend|should i|set .*temp|heat |für.*druck',t):
        return []
    query = re.search(r'\?|сейчас|покажи|проверь|посмотри|сколько|какая|какой|какие|статус|остаток|температур|what|current|show|check|how much|status|temperature|remaining|aktuell|zeige|prüf|wie viel|temperatur|остаток|залиш|температур',t)
    if not query:
        return []
    result=[]
    def add(name):
        if name not in result:result.append(name)
    if re.search(r'температур|temperature|temperatur',t) and re.search(r'сейчас|текущ|current|aktuell|покажи|проверь|посмотри|show|check|сопл|стол|головк|nozzle|bed|extruder|düse|bett|^температур',t):add('get_temperatures')
    if re.search(r'остат|остав|грамм|потрачен|израсход|расход|remaining|filament.*(?:left|used)|grams|verbrauch|restmenge|залиш',t):add('get_filament_status')
    if re.search(r'статус|состояни|печатает|прогресс|готов.*принтер|принтер.*готов|ид[её]т.*печать|printer.*(?:status|ready|printing)|print progress|drucker.*status|druckfortschritt|стан принтер',t):add('get_printer_status')
    return result[:3]
