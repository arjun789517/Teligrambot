import requests
import json
from random import randint
from time import sleep
import re
import math

# Проверка и установка необходимых библиотек
try:
    import telebot
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
except ModuleNotFoundError:
    print("Устанавливаем необходимые библиотеки...")
    import subprocess
    subprocess.check_call(['pip', 'install', 'pyTelegramBotAPI'])
    import telebot
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

# ============= НАСТРОЙКИ =============
BOT_TOKEN = "8735045882:dGnfJAPg"  # Ваш токен от @BotFather
API_TOKEN = ""  # Вставьте сюда токен от Leakosint (получите командой /API в боте LeakosintBot)
LANG = "ru"     # Язык результатов: "ru", "en" и т.д.
LIMIT = 300     # Лимит поиска (от 100 до 10000)
API_URL = "https://leakosintapi.com/"
# ====================================

# Кэш для хранения результатов поиска
search_cache = {}

def check_user_access(user_id):
    """
    Функция проверки доступа пользователя.
    Здесь можно реализовать свою логику: проверка БД, белый список и т.д.
    """
    # Белый список пользователей (ID Telegram) - оставьте пустым для открытого доступа
    whitelist = []  # Например: [123456789, 987654321]
    
    if not whitelist:  # Если список пуст - доступ открыт всем
        return True
    
    return user_id in whitelist

def calculate_complexity(query):
    """
    Рассчитывает сложность запроса на основе количества слов
    """
    # Находим фразы в кавычках и считаем их как одно слово
    quoted_phrases = re.findall(r'"([^"]*)"', query)
    
    # Убираем кавычки из запроса для подсчета остальных слов
    temp_query = query
    for phrase in quoted_phrases:
        temp_query = temp_query.replace(f'"{phrase}"', '')
    
    # Разбиваем на слова
    words = temp_query.split()
    
    # Фильтруем слова по правилам из документации
    filtered_words = []
    for word in words:
        # Пропускаем даты (простейшая проверка)
        if re.match(r'\d{2}[./-]\d{2}[./-]\d{4}', word):
            continue
        # Пропускаем короткие строки (< 4 символов)
        if len(word) < 4:
            continue
        # Пропускаем короткие числа (< 6 цифр)
        if word.isdigit() and len(word) < 6:
            continue
        filtered_words.append(word)
    
    # Добавляем фразы из кавычек обратно
    total_words = len(filtered_words) + len(quoted_phrases)
    
    # Расчет сложности по формуле из документации
    if total_words <= 1:
        return 1
    elif total_words == 2:
        return 5
    elif total_words == 3:
        return 16
    else:
        return 40

def calculate_price(limit, complexity):
    """
    Рассчитывает стоимость запроса в долларах
    Формула: 0.0002 * (5 + sqrt(Limit * Complexity))
    """
    price = 0.0002 * (5 + math.sqrt(limit * complexity))
    return round(price, 6)

def search_request(query, query_id):
    """
    Выполняет поисковый запрос к API
    """
    global search_cache, API_URL, API_TOKEN, LIMIT, LANG
    
    if not API_TOKEN:
        return None
    
    # Разбиваем запрос на отдельные строки, если их несколько
    queries = query.strip().split('\n')
    
    all_results = []
    
    for single_query in queries:
        if not single_query.strip():
            continue
            
        data = {
            "token": API_TOKEN,
            "request": single_query.strip(),
            "limit": LIMIT,
            "lang": LANG,
            "type": "json"
        }
        
        try:
            print(f"Отправка запроса: {single_query}")
            response = requests.post(API_URL, json=data, timeout=30)
            result = response.json()
            print(f"Ответ API получен")
            
            if "Error code" in result:
                print(f"Ошибка API: {result['Error code']}")
                return None
                
            all_results.append({
                "query": single_query,
                "response": result
            })
            
        except requests.exceptions.Timeout:
            print("Таймаут запроса к API")
            return None
        except Exception as e:
            print(f"Ошибка при запросе: {e}")
            return None
    
    if not all_results:
        return None
    
    # Форматируем результаты для отправки в Telegram
    search_cache[str(query_id)] = []
    
    for result_data in all_results:
        query_text = result_data["query"]
        response_data = result_data["response"]
        
        # Рассчитываем сложность и стоимость
        complexity = calculate_complexity(query_text)
        price = calculate_price(LIMIT, complexity)
        
        # Добавляем информацию о запросе
        header = f"🔍 <b>Запрос:</b> {query_text}\n📊 <b>Сложность:</b> {complexity}\n💰 <b>Стоимость:</b> ${price}\n\n"
        
        # Обрабатываем результаты
        if "List" not in response_data:
            search_cache[str(query_id)].append(header + "❌ Результатов не найдено")
            continue
            
        for db_name, db_data in response_data["List"].items():
            message_parts = [header]
            message_parts.append(f"📁 <b>{db_name}</b>")
            
            if "InfoLeak" in db_data and db_data["InfoLeak"]:
                message_parts.append(f"ℹ️ {db_data['InfoLeak']}")
            
            if db_name == "No results found":
                message_parts.append("❌ Ничего не найдено")
            elif "Data" in db_data and db_data["Data"]:
                for item in db_data["Data"]:
                    message_parts.append("")
                    for key, value in item.items():
                        # Экранируем HTML-символы
                        safe_key = str(key).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                        safe_value = str(value).replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
                        message_parts.append(f"<b>{safe_key}:</b> {safe_value}")
            else:
                message_parts.append("📭 Нет данных")
            
            full_message = "\n".join(message_parts)
            
            # Обрезаем сообщение, если оно слишком длинное
            if len(full_message) > 3500:
                full_message = full_message[:3500] + "\n\n✂️ Сообщение обрезано из-за ограничения Telegram"
            
            search_cache[str(query_id)].append(full_message)
    
    if not search_cache[str(query_id)]:
        search_cache[str(query_id)].append("❌ Результатов не найдено")
    
    return search_cache[str(query_id)]

def create_keyboard(query_id, page_num, total_pages):
    """
    Создает инлайн-клавиатуру для навигации
    """
    markup = InlineKeyboardMarkup(row_width=3)
    
    if total_pages <= 1:
        return markup
    
    # Нормализуем номер страницы
    if page_num < 0:
        page_num = total_pages - 1
    elif page_num >= total_pages:
        page_num = 0
    
    buttons = [
        InlineKeyboardButton("◀️ Назад", callback_data=f"page:{query_id}:{page_num - 1}"),
        InlineKeyboardButton(f"{page_num + 1}/{total_pages}", callback_data="none"),
        InlineKeyboardButton("Вперед ▶️", callback_data=f"page:{query_id}:{page_num + 1}")
    ]
    markup.add(*buttons)
    
    return markup

# Инициализация бота
bot = telebot.TeleBot(BOT_TOKEN)

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    welcome_text = """
🤖 <b>Добро пожаловать в бот поиска утечек данных!</b>

Я использую API Leakosint для поиска информации в базах данных.

<b>🔍 Как использовать:</b>
Просто отправьте мне текст для поиска:
• <code>example@gmail.com</code>
• <code>Имя Фамилия</code>
• <code>"фраза в кавычках"</code>

<b>📊 Команды:</b>
/start - Показать это сообщение
/help - Помощь
/price - Информация о ценообразовании
/status - Статус вашего аккаунта
/setapikey - Установить API ключ Leakosint

<b>💡 Советы:</b>
• Используйте кавычки для поиска точных фраз
• Ограничение результатов: {} записей
• Несколько запросов можно отправить с новой строки

<b>💰 Стоимость:</b>
Формула: <code>0.0002 × (5 + √(Лимит × Сложность))</code>

<i>Для начала работы установите API ключ командой /setapikey</i>
    """.format(LIMIT)
    
    bot.reply_to(message, welcome_text, parse_mode='HTML')

@bot.message_handler(commands=['setapikey'])
def set_api_key(message):
    global API_TOKEN
    msg = bot.reply_to(message, "🔑 Отправьте ваш API ключ от Leakosint:\n\n(Получить ключ можно командой /API в боте @LeakosintBot)")
    bot.register_next_step_handler(msg, save_api_key)

def save_api_key(message):
    global API_TOKEN
    API_TOKEN = message.text.strip()
    bot.reply_to(message, "✅ API ключ успешно сохранен! Теперь вы можете использовать бота для поиска.", parse_mode='HTML')

@bot.message_handler(commands=['price'])
def show_price(message):
    price_text = """
<b>💰 Калькулятор стоимости запросов</b>

<b>Формула:</b>
<code>0.0002 × (5 + √(Лимит × Сложность))</code>

<b>Сложность (Complexity):</b>
• 1 слово: 1
• 2 слова: 5
• 3 слова: 16
• >3 слов: 40

<b>Примеры для лимита {}:</b>
• 1 слово: ${:.6f}
• 2 слова: ${:.6f}
• 3 слова: ${:.6f}
• 4+ слова: ${:.6f}

<i>Цены указаны в долларах США</i>
    """.format(LIMIT, 
               calculate_price(LIMIT, 1),
               calculate_price(LIMIT, 5),
               calculate_price(LIMIT, 16),
               calculate_price(LIMIT, 40))
    
    bot.reply_to(message, price_text, parse_mode='HTML')

@bot.message_handler(commands=['status'])
def show_status(message):
    api_status = "✅ Установлен" if API_TOKEN else "❌ Не установлен"
    api_preview = API_TOKEN[:15] + "..." if API_TOKEN and len(API_TOKEN) > 15 else (API_TOKEN or "Не установлен")
    
    status_text = f"""
<b>📊 Статус аккаунта</b>

🔑 <b>API ключ:</b> {api_status}
📝 <b>Ключ:</b> <code>{api_preview}</code>
⚙️ <b>Лимит запроса:</b> {LIMIT}
🌐 <b>Язык:</b> {LANG}

<b>Команды:</b>
/setapikey - Установить API ключ
/price - Информация о ценообразовании

<i>Для получения API ключа используйте команду /API в боте @LeakosintBot</i>
    """
    
    bot.reply_to(message, status_text, parse_mode='HTML')

@bot.message_handler(func=lambda message: True)
def handle_search(message):
    global API_TOKEN
    
    user_id = message.from_user.id
    
    # Проверка доступа
    if not check_user_access(user_id):
        bot.send_message(message.chat.id, "⛔ У вас нет доступа к этому боту")
        return
    
    if message.content_type != 'text':
        bot.send_message(message.chat.id, "❌ Пожалуйста, отправьте текстовый запрос")
        return
    
    # Проверка наличия API ключа
    if not API_TOKEN:
        bot.send_message(
            message.chat.id, 
            "❌ <b>API ключ не установлен!</b>\n\nПожалуйста, установите API ключ командой:\n/setapikey\n\nПолучить ключ можно в боте @LeakosintBot командой /API",
            parse_mode='HTML'
        )
        return
    
    # Отправляем уведомление о начале поиска
    status_msg = bot.send_message(message.chat.id, "🔍 <i>Поиск данных... Это может занять несколько секунд</i>", parse_mode='HTML')
    
    # Генерируем уникальный ID запроса
    query_id = randint(0, 9999999)
    
    # Выполняем поиск
    results = search_request(message.text, query_id)
    
    # Удаляем уведомление
    try:
        bot.delete_message(message.chat.id, status_msg.message_id)
    except:
        pass
    
    if results is None:
        bot.send_message(
            message.chat.id, 
            "❌ <b>Ошибка API</b>\n\nВозможные причины:\n• Неверный API ключ\n• Недостаточно средств\n• Проблемы с соединением\n\nПроверьте ключ командой /status",
            parse_mode='HTML'
        )
        return
    
    if not results:
        bot.send_message(message.chat.id, "❌ <b>Результатов не найдено</b>\n\nПопробуйте изменить запрос.", parse_mode='HTML')
        return
    
    # Отправляем результаты
    total_pages = len(results)
    keyboard = create_keyboard(query_id, 0, total_pages)
    
    try:
        bot.send_message(
            message.chat.id, 
            results[0], 
            parse_mode='HTML', 
            reply_markup=keyboard,
            disable_web_page_preview=True
        )
    except telebot.apihelper.ApiTelegramException as e:
        # Если HTML не проходит, отправляем без форматирования
        if "can't parse entities" in str(e):
            plain_text = results[0].replace('<b>', '').replace('</b>', '').replace('<i>', '').replace('</i>', '')
            bot.send_message(message.chat.id, plain_text, reply_markup=keyboard)
        else:
            bot.send_message(message.chat.id, results[0][:4000], reply_markup=keyboard)

@bot.callback_query_handler(func=lambda call: True)
def handle_callback(call: CallbackQuery):
    global search_cache
    
    if call.data.startswith("page:"):
        try:
            _, query_id, page_num = call.data.split(":")
            page_num = int(page_num)
            
            if query_id not in search_cache:
                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text="⏰ Результаты поиска устарели. Пожалуйста, выполните поиск заново."
                )
                return
            
            results = search_cache[query_id]
            total_pages = len(results)
            
            if page_num < 0:
                page_num = total_pages - 1
            elif page_num >= total_pages:
                page_num = 0
            
            keyboard = create_keyboard(query_id, page_num, total_pages)
            
            try:
                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text=results[page_num],
                    parse_mode='HTML',
                    reply_markup=keyboard,
                    disable_web_page_preview=True
                )
            except telebot.apihelper.ApiTelegramException:
                plain_text = results[page_num].replace('<b>', '').replace('</b>', '').replace('<i>', '').replace('</i>', '')
                bot.edit_message_text(
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    text=plain_text,
                    reply_markup=keyboard
                )
            
            # Отвечаем на callback, чтобы убрать "часики"
            bot.answer_callback_query(call.id)
            
        except Exception as e:
            print(f"Ошибка в callback: {e}")
            bot.answer_callback_query(call.id, "Произошла ошибка", show_alert=False)
    
    elif call.data == "none":
        bot.answer_callback_query(call.id)

# Запуск бота с автоматическим переподключением
if __name__ == "__main__":
    print("=" * 50)
    print("🤖 БОТ ЗАПУЩЕН")
    print("=" * 50)
    print(f"📝 API URL: {API_URL}")
    print(f"🔑 Bot Token: {BOT_TOKEN[:15]}...")
    print(f"🔐 API Token: {'Установлен' if API_TOKEN else 'Не установлен'}")
    print(f"⚙️ Лимит: {LIMIT}")
    print(f"🌐 Язык: {LANG}")
    print("=" * 50)
    print("✅ Бот готов к работе!")
    print("📍 Нажмите: https://t.me/" + BOT_TOKEN.split(":")[0] + " чтобы открыть бота")
    print("=" * 50)
    
    while True:
        try:
            bot.polling(none_stop=True, interval=1, timeout=60)
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            print("🔄 Переподключение через 5 секунд...")
            sleep(5)
