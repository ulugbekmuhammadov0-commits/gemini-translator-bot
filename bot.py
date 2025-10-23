1  import os
 2  import asyncio
 3  # import sys  <-- ЭТО УЖЕ НЕ НУЖНО, ТАК КАК МЫ НЕ ИСПОЛЬЗУЕМ WEBHOOK
 4  # from dotenv import load_dotenv  <-- ЭТА СТРОКА УДАЛЕНА
 5  from aiogram import Bot, Dispatcher, types, F
 6  from aiogram.filters import Command 
 7  from deep_translator import GoogleTranslator 
 8  from google import genai
 9  from google.genai.errors import APIError
10  from google.genai.types import HarmCategory as HCategory, SafetySetting, HarmBlockThreshold 
11  from google.genai.errors import APIError
12  
13  # ==================================
14  # 1. Инициализация и настройки 
15  # ==================================
16  
17  # load_dotenv()  <-- ЭТА СТРОКА УДАЛЕНА
18  
19  # Чтение ключей из окружения (эти ключи подставлены Render!)
20  BOT_TOKEN = os.getenv("BOT_TOKEN") 
21  GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
22  
23  if not BOT_TOKEN or not GEMINI_API_KEY:
24      # Ошибка, если ключи не заданы в переменных окружения Render
25      print("❌ Ключи BOT_TOKEN или GEMINI_API_KEY не найдены в переменных окружения Render.")
26  
27  # Инициализация ботов и клиентов
28  bot = Bot(token=BOT_TOKEN)
29  dp = Dispatcher()
30  
31  # Инициализация deep-translator
32  translator = GoogleTranslator(source='auto', target='en')
33  
34  # Настройки языков
35  languages = {
36      "Русский 🇷🇺": "ru",
37      "Английский 🇬🇧": "en",
38      "Узбекский 🇺🇿": "uz"
39  }
40  
41  user_lang = {}
42  
43  # КОНФИГУРАЦИЯ БЕЗОПАСНОСТИ (для Gemini)
44  SAFETY_SETTINGS = [
45      SafetySetting(
46          category=category,
47          threshold=HarmBlockThreshold.BLOCK_NONE,
48      )
49      for category in [
50          HCategory.HARM_CATEGORY_HARASSMENT,
51          HCategory.HARM_CATEGORY_HATE_SPEECH,
52          HCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT,
53          HCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
54      ]
55  ]
56  
57  # Инициализация клиента Gemini
58  try:
59      gemini_client = genai.Client(api_key=GEMINI_API_KEY)
60  except Exception as e:
61      print(f"Ошибка инициализации Gemini: {e}")
62  
63  
64  # ==================================
65  # 2. Общая функция для вызова Gemini
66  # ==================================
67  
68  async def get_gemini_response(prompt: str):
69      """Отправляет запрос в Gemini и возвращает текст или ошибку."""
70      try:
71          response = gemini_client.models.generate_content(
72              model='gemini-2.5-flash',
73              contents=prompt,
74              config=genai.types.GenerateContentConfig(
75                  temperature=0.4,
76                  max_output_tokens=400,
77                  safety_settings=SAFETY_SETTINGS
78              )
79          )
80          if response and response.text:
81              return response.text.strip()
82          return "⚠️ Gemini не смог дать ответ."
83      except APIError as e:
84          return f"⚠️ Ошибка ИИ (API Gemini): {e}"
85      except Exception as e:
86          return f"⚠️ Неизвестная ошибка ИИ: {e}"
87  
88  
89  # ==================================
90  # 3. Хендлеры (Обработчики сообщений)
91  # ==================================
92  
93  @dp.message(Command('start'))
94  async def start(message: types.Message):
95      button_list = [types.KeyboardButton(text=lang_name) for lang_name in languages.keys()]
96      
97      keyboard = types.ReplyKeyboardMarkup(
98          keyboard=[button_list], 
99          resize_keyboard=True,
100         one_time_keyboard=True
101     )
102     
103     await message.answer(
104         "👋 Привет! Я умный переводчик и помощник.\n"
105         "Выбери язык, на который я буду переводить:",
106         reply_markup=keyboard
107     )
108 
109 @dp.message(F.text.in_(languages.keys()))
110 async def set_language(message: types.Message):
111     user_lang[message.from_user.id] = languages[message.text]
112     await message.answer(f"✅ Отлично! Перевожу на {message.text}.\nТеперь просто напиши фразу для перевода и объяснения.",
113                          reply_markup=types.ReplyKeyboardRemove())
114 
115 @dp.message(F.text)
116 async def handle_text(message: types.Message):
117     target_lang_code = user_lang.get(message.from_user.id, "en")
118     source_text = message.text
119 
120     # --- Шаг 1: Перевод с помощью deep-translator ---
121     translation = ""
122     try:
123         translator.target = target_lang_code 
124         translation = await asyncio.to_thread(translator.translate, source_text)
125         if not translation:
126              translation = source_text
127     except Exception as e:
128         await message.answer(f"⚠️ Ошибка перевода: {e}")
129         return
130 
131     # --- Шаг 2: Объяснение с помощью Gemini (Обходной путь через Английский) ---
132     gemini_output_lang = "en"
133     ai_text = ""
134     ai_text_en = ""
135     
136     # 1. Gemini всегда генерирует объяснение на английском
137     prompt_en = (
138         f"Объясни значение и дай краткий контекст для фразы: '{translation}'. "
139         f"Ответ должен быть на АНГЛИЙСКОМ языке и быть максимально коротким и по существу."
140     )
141     ai_text_en = await get_gemini_response(prompt_en)
142     
143     # 2. Перевод ответа Gemini на целевой язык
144     if ai_text_en and not ai_text_en.startswith("⚠️"):
145         if target_lang_code != gemini_output_lang:
146             try:
147                 translator.source = gemini_output_lang
148                 translator.target = target_lang_code
149                 ai_text = await asyncio.to_thread(translator.translate, ai_text_en)
150             except Exception as e:
151                 ai_text = f"⚠️ Ошибка перевода объяснения: {e}"
152         else:
153             ai_text = ai_text_en
154     else:
155         ai_text = ai_text_en # Передаем ошибку, если она была
156 
157     # --- Шаг 3: Отправка результата с кнопкой "Синонимы" ---
158     
159     # Используем ТОЛЬКО ПЕРВОЕ СЛОВО перевода для callback_data (для стабильности)
160     first_word = translation.split()[0][:20] 
161     synonym_callback_data = f"SYNONYM_{target_lang_code}_{first_word}"
162     
163     inline_keyboard = types.InlineKeyboardMarkup(
164         inline_keyboard=[
165             [
166                 types.InlineKeyboardButton(text="🔎 Синонимы", callback_data=synonym_callback_data)
167             ]
168         ]
169     )
170 
171     await message.answer(
172         f"🌍 <b>Перевод:</b>\n{translation}\n\n🤖 <b>Объяснение от Gemini:</b>\n{ai_text}",
173         parse_mode="HTML",
174         reply_markup=inline_keyboard
175     )
176 
177 
178 # ==================================
179 # 4. Хендлер для инлайн-кнопки "Синонимы"
180 # ==================================
181 
182 @dp.callback_query(F.data.startswith("SYNONYM_"))
183 async def handle_synonym_request(callback_query: types.CallbackQuery):
184     # Разбираем данные: SYNONYM_[lang_code]_[word]
185     _, lang_code, word = callback_query.data.split('_')
186     
187     # Убираем кнопку
188     await bot.edit_message_reply_markup(
189         chat_id=callback_query.message.chat.id,
190         message_id=callback_query.message.message_id,
191         reply_markup=None
192     )
193 
194     await callback_query.answer("Ищем синонимы...")
195 
196     synonyms_text = ""
197     
198     # --- Динамический выбор метода запроса ---
199 
200     if lang_code == "uz":
201         # Узбекский (uz): Двойной перевод (Англ -> Узбек) для надежности
202         prompt_synonym_en = (
203             f"Provide 5-7 synonyms for the word '{word}' and list them. The response must be a simple, clean, unnumbered list in ENGLISH."
204         )
205         synonyms_en = await get_gemini_response(prompt_synonym_en)
206 
207         if synonyms_en.startswith("⚠️"):
208             synonyms_text = synonyms_en
209         elif not synonyms_en or len(synonyms_en) < 5:
210             synonyms_text = f"⚠️ Gemini не смог найти синонимы или альтернативы для слова \"{word}\"."
211         else:
212             try:
213                 # Перевод с английского на узбекский
214                 translator.source = "en"
215                 translator.target = lang_code
216                 synonyms_text = await asyncio.to_thread(translator.translate, synonyms_en)
217             except Exception:
218                 synonyms_text = f"⚠️ Ошибка при переводе списка синонимов на {lang_code}. Вот английский оригинал:\n{synonyms_en}"
219             
220     else:
221         # Русский (ru) и Английский (en): Прямой запрос на целевом языке
222         
223         prompt_synonym_direct = (
224             f"Provide 5-7 synonyms or alternative phrases for the word '{word}' in the language with code '{lang_code}' and list them in a simple, unnumbered format."
225             f"Do not add extra explanations, only the list."
226         )
227         synonyms_text = await get_gemini_response(prompt_synonym_direct)
228         
229         if synonyms_text.startswith("⚠️"):
230              pass # Ошибка уже в тексте
231         elif not synonyms_text or len(synonyms_text) < 5:
232              # Если ответ пуст
233              synonyms_text = f"⚠️ Gemini не смог найти синонимы или альтернативы для слова \"{word}\"."
234 
235 
236     # --- Отправка результата ---
237     await bot.send_message(
238         callback_query.message.chat.id,
239         f"📚 <b>Синонимы/альтернативы для \"{word}\":</b>\n\n{synonyms_text}",
240         parse_mode="HTML"
241     )
242 
243     await callback_query.answer()
244 
245 
246 # ==================================
247 # 5. Асинхронный запуск бота (aiogram 3.x)
248 # ==================================
249 async def main():
250     print("Бот запущен. Ожидание сообщений...")
251     # Проверка на наличие ключа перед запуском polling
252     if BOT_TOKEN and GEMINI_API_KEY:
253         await dp.start_polling(bot, skip_updates=True)
254     else:
255         print("Ключи API не настроены. Бот не будет запущен.")
256 
257 
258 if __name__ == "__main__":
259     try:
260         asyncio.run(main())
261     except KeyboardInterrupt:
262         print("Бот остановлен вручную")
263     except Exception as e:
264         print(f"Критическая ошибка при запуске: {e}")