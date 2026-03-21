"""Internationalization for web UI. RU/EN translations + JS helpers."""

import json

TRANSLATIONS = {
    "ru": {
        # App
        "app.title": "TTS Адаптер",
        "app.subtitle": "Генерация речи из текста",
        # Status
        "status.checking": "Проверка сервера...",
        "status.ok": "Сервер ОК",
        "status.engine": "Движок",
        "status.model": "Модель",
        "status.caps": "Режимы",
        "status.error": "Сервер не отвечает. Запустите: make serve",
        # Model selector
        "model.label": "Модель:",
        "model.loading": "Загрузка...",
        "model.switch_title": "Сменить модель (перезагрузка)",
        "model.guide": "Справка по моделям",
        "model.features_title": "Возможности выбранной модели",
        # Loading overlay
        "loading.text": "Смена модели...",
        "loading.hint": "Это может занять 1-2 минуты. Подождите.",
        # Switch modal
        "modal.switch_title": "Сменить модель?",
        "modal.switch_msg": "Модель будет перезагружена. Сервер недоступен ~2 минуты.",
        "modal.cancel": "Отмена",
        "modal.confirm_switch": "Сменить",
        "modal.cancel_title": "Отменить смену модели",
        "modal.confirm_title": "Подтвердить смену модели",
        # Model help modal
        "help.model_title": "Справка по моделям",
        "help.model_loading": "Загрузка информации о моделях...",
        "help.got_it": "Понятно",
        "help.close_model": "Закрыть справку",
        "help.current_model": "Текущая модель",
        "help.pick_model": "Выберите модель по нужной функции:",
        "help.use_for": "Для:",
        "help.low_vram": "Меньше VRAM.",
        "help.switch_hint": "Смена модели перезагружает сервер и занимает 1-2 минуты.",
        # Advanced settings help
        "help.params_title": "Параметры генерации",
        "help.params_intro": "Эти параметры управляют генерацией аудио-токенов. Значения по умолчанию подходят для большинства случаев.",
        "help.close_params": "Закрыть справку по параметрам",
        "help.temp_desc": "Управляет случайностью. Низкие значения (0.3-0.7) дают более стабильный результат. Высокие (1.0-1.5) добавляют разнообразие, но могут снизить качество.",
        "help.topk_desc": "Ограничивает выборку K наиболее вероятными токенами. Меньше (10-30) — более сфокусированно. Больше — разнообразнее.",
        "help.topp_desc": "Nucleus sampling: учитываются только токены, чья совокупная вероятность достигает P. Меньше (0.7-0.9) отсекает маловероятные. При 1.0 учитываются все.",
        "help.rep_desc": "Штрафует уже появившиеся токены. Увеличьте (1.1-1.3) при повторах или артефактах. Слишком высокое значение исказит речь.",
        "help.tokens_desc": "Максимум аудио-кодек токенов. Увеличьте для длинных текстов. ~256 токенов ≈ 5-10 секунд аудио.",
        # Tabs
        "tab.simple": "Простой",
        "tab.design": "Дизайн голоса",
        "tab.clone": "Клонирование",
        "tab.simple_title": "Простой TTS (модель CustomVoice)",
        "tab.design_title": "Дизайн голоса (модель VoiceDesign)",
        "tab.clone_title": "Клонирование голоса (модель Base)",
        "tab.requires_customvoice": "Нужна модель CustomVoice",
        "tab.requires_design": "Нужна модель VoiceDesign",
        "tab.requires_base": "Нужна модель Base",
        # Capabilities
        "cap.simple": "Простой",
        "cap.design": "Дизайн",
        "cap.clone": "Клон",
        "cap.simple_full": "Простой (стиль инструкцией)",
        "cap.design_full": "Дизайн голоса",
        "cap.clone_full": "Клонирование голоса",
        "cap.mode": "Режим",
        "cap.modes": "Режимы",
        "cap.caps": "Возможности",
        "cap.unavailable": "Нет данных о возможностях",
        # Labels
        "label.text": "Текст для озвучки",
        "label.language": "Язык",
        "label.speaker": "Диктор",
        "label.instruct": "Стиль (необязательно)",
        "label.design_instruct": "Описание голоса (обязательно)",
        "label.ref_audio": "Референс аудио (WAV, 3-10 сек)",
        "label.ref_text": "Транскрипт референса (необязательно, улучшает качество)",
        # Placeholders
        "ph.text": "Введите текст...",
        "ph.instruct": "напр., Говорите медленно и тепло",
        "ph.design_instruct": "напр., Взрослый женский голос, контральто, тёплый и уверенный",
        "ph.ref_text": "Что сказано в референсном аудио",
        # Tooltips
        "title.text": "Обязательный текст для синтеза",
        "title.language": "Язык выходной речи",
        "title.speaker": "Предустановленный диктор (модель CustomVoice)",
        "title.instruct": "Стиль инструкция (модель CustomVoice)",
        "title.design_instruct": "Описание голоса (модель VoiceDesign)",
        "title.ref_audio": "WAV файл, 3-10 секунд",
        "title.ref_text": "Транскрипт референсного аудио",
        # Hints
        "hint.instruct": "Управляйте тоном, эмоцией, скоростью. Только для модели CustomVoice.",
        "hint.design": "Опишите голос: пол, возраст, высота, тембр, эмоция, темп. Мы обрезаем тишину.",
        # Buttons
        "btn.generate": "Сгенерировать речь",
        "btn.generate_design": "Сгенерировать с дизайном голоса",
        "btn.generate_clone": "Сгенерировать с клоном голоса",
        "btn.generating": "Генерация...",
        "btn.generate_title": "Сгенерировать речь с текущими настройками",
        "btn.design_title": "Сгенерировать речь с дизайном голоса",
        "btn.clone_title": "Сгенерировать речь с клоном голоса",
        # Advanced settings
        "advanced.title": "Расширенные настройки",
        "advanced.guide": "Справка по параметрам",
        "param.temperature": "Температура",
        "param.top_k": "Top-K",
        "param.top_p": "Top-P",
        "param.rep_penalty": "Штраф повтора",
        "param.max_tokens": "Макс. токенов",
        "param.temp_tip": "Случайность. Ниже (0.3-0.7) = стабильнее. Выше (1.0+) = разнообразнее. По умолч.: 0.9",
        "param.topk_tip": "Ограничение выборки K токенами. Ниже (10-30) = сфокусированнее. По умолч.: 50",
        "param.topp_tip": "Nucleus sampling: учитываются токены до порога P. Ниже (0.7-0.9) отсекает маловероятные. По умолч.: 1.0",
        "param.rep_tip": "Штраф за повторы. Увеличьте (1.1-1.3) при артефактах. По умолч.: 1.05",
        "param.tokens_tip": "Максимум аудио-токенов. Для длинных текстов увеличьте. ~256 ≈ 5-10 сек. По умолч.: 2048",
        # Progress
        "progress.generating": "Генерация аудио...",
        "progress.designing": "Создание голоса...",
        "progress.cloning": "Клонирование голоса...",
        "progress.first_slow": "Первый запрос после загрузки модели может быть медленнее.",
        # Errors
        "error.prefix": "Ошибка",
        "error.generation_failed": "Генерация не удалась",
        "error.no_ref_audio": "Выберите файл референсного аудио",
        "error.switch_failed": "Не удалось сменить модель",
        "error.model_info": "Информация о моделях недоступна.",
        # Result
        "misc.result": "Результат:",
        "misc.download": "Скачать WAV",
        "misc.download_title": "Скачать сгенерированный WAV",
        # Footer
        "footer.api_docs": "Документация API",
        "footer.health": "Проверка здоровья",
        # Speakers (descriptions only, names stay)
        "speaker.serena": "Serena (Жен., тёплый)",
        "speaker.sohee": "Sohee (Жен., эмоциональный)",
        "speaker.vivian": "Vivian (Жен., яркий)",
        "speaker.ono_anna": "Ono_Anna (Жен., игривый)",
        "speaker.ryan": "Ryan (Муж., динамичный)",
        "speaker.aiden": "Aiden (Муж., чистый)",
        "speaker.uncle_fu": "Uncle_Fu (Муж., мягкий)",
        "speaker.dylan": "Dylan (Муж., молодёжный)",
        "speaker.eric": "Eric (Муж., живой)",
        # Dynamic: switch modal
        "modal.switch_to": "Сменить на",
        "modal.switch_warn": "Модель TTS будет перезагружена. Сервер недоступен ~2 минуты.",
    },
    "en": {
        # App
        "app.title": "TTS Adapter",
        "app.subtitle": "Text-to-Speech Generation",
        # Status
        "status.checking": "Checking server status...",
        "status.ok": "Server OK",
        "status.engine": "Engine",
        "status.model": "Model",
        "status.caps": "Caps",
        "status.error": "Server not responding. Start with: make serve",
        # Model selector
        "model.label": "Model:",
        "model.loading": "Loading...",
        "model.switch_title": "Switch TTS model (reloads server)",
        "model.guide": "Model guide",
        "model.features_title": "Capabilities for selected model",
        # Loading overlay
        "loading.text": "Switching model...",
        "loading.hint": "This may take 1-2 minutes. Please wait.",
        # Switch modal
        "modal.switch_title": "Switch Model?",
        "modal.switch_msg": "This will reload the TTS model. Server unavailable for ~2 minutes.",
        "modal.cancel": "Cancel",
        "modal.confirm_switch": "Switch Model",
        "modal.cancel_title": "Cancel model switch",
        "modal.confirm_title": "Confirm model switch",
        # Model help modal
        "help.model_title": "Model Guide",
        "help.model_loading": "Loading model info...",
        "help.got_it": "Got it",
        "help.close_model": "Close model guide",
        "help.current_model": "Current model",
        "help.pick_model": "Pick a model based on the feature you need:",
        "help.use_for": "Use for:",
        "help.low_vram": "Low VRAM option.",
        "help.switch_hint": "Switching models reloads the server and takes about 1-2 minutes.",
        # Advanced settings help
        "help.params_title": "Generation Parameters",
        "help.params_intro": "These parameters control how the model generates audio tokens. Defaults work well for most cases.",
        "help.close_params": "Close parameter guide",
        "help.temp_desc": "Controls randomness. Lower values (0.3-0.7) produce more consistent, deterministic output. Higher values (1.0-1.5) add variety but may reduce quality.",
        "help.topk_desc": "Limits sampling to the K most likely tokens at each step. Lower values (10-30) make output more focused. Higher values allow more diversity.",
        "help.topp_desc": "Nucleus sampling: only considers tokens whose cumulative probability reaches P. Lower values (0.7-0.9) cut unlikely tokens. At 1.0 all tokens are considered.",
        "help.rep_desc": "Penalizes tokens that already appeared. Increase (1.1-1.3) if you hear repeated sounds or artifacts. Too high may distort speech.",
        "help.tokens_desc": "Maximum number of audio codec tokens to generate. Increase for very long texts. Each ~256 tokens is roughly 5-10 seconds of audio.",
        # Tabs
        "tab.simple": "Simple",
        "tab.design": "Voice Design",
        "tab.clone": "Voice Clone",
        "tab.simple_title": "Simple TTS (CustomVoice model)",
        "tab.design_title": "Voice Design (VoiceDesign model)",
        "tab.clone_title": "Voice Clone (Base model)",
        "tab.requires_customvoice": "Requires CustomVoice model",
        "tab.requires_design": "Requires VoiceDesign model",
        "tab.requires_base": "Requires Base model",
        # Capabilities
        "cap.simple": "Simple",
        "cap.design": "Design",
        "cap.clone": "Clone",
        "cap.simple_full": "Simple (style instruction)",
        "cap.design_full": "Voice Design",
        "cap.clone_full": "Voice Clone",
        "cap.mode": "Mode",
        "cap.modes": "Modes",
        "cap.caps": "Capabilities",
        "cap.unavailable": "Capabilities unavailable",
        # Labels
        "label.text": "Text to speak",
        "label.language": "Language",
        "label.speaker": "Speaker",
        "label.instruct": "Style instruction (optional)",
        "label.design_instruct": "Voice description (required)",
        "label.ref_audio": "Reference audio (WAV, 3-10 sec)",
        "label.ref_text": "Reference transcript (optional, improves quality)",
        # Placeholders
        "ph.text": "Enter text here...",
        "ph.instruct": "e.g., Speak slowly and warmly",
        "ph.design_instruct": "e.g., Adult female voice, contralto range, warm and confident, expressive",
        "ph.ref_text": "What is said in the reference audio",
        # Tooltips
        "title.text": "Required text to synthesize",
        "title.language": "Language for output speech",
        "title.speaker": "Preset speaker (CustomVoice model)",
        "title.instruct": "Optional style instruction (CustomVoice model)",
        "title.design_instruct": "Required voice description (VoiceDesign model)",
        "title.ref_audio": "Required WAV file, 3-10 seconds",
        "title.ref_text": "Optional transcript of the reference audio",
        # Hints
        "hint.instruct": "Control tone, emotion, speed. Works with CustomVoice model only.",
        "hint.design": "Describe the voice: gender, age, pitch, timbre, emotion, pace. We trim trailing silence.",
        # Buttons
        "btn.generate": "Generate Speech",
        "btn.generate_design": "Generate with Designed Voice",
        "btn.generate_clone": "Generate with Cloned Voice",
        "btn.generating": "Generating...",
        "btn.generate_title": "Generate speech with current settings",
        "btn.design_title": "Generate speech with designed voice",
        "btn.clone_title": "Generate speech with cloned voice",
        # Advanced settings
        "advanced.title": "Advanced Settings",
        "advanced.guide": "Parameter guide",
        "param.temperature": "Temperature",
        "param.top_k": "Top-K",
        "param.top_p": "Top-P",
        "param.rep_penalty": "Repetition Penalty",
        "param.max_tokens": "Max Tokens",
        "param.temp_tip": "Controls randomness. Lower (0.3-0.7) = more consistent output. Higher (1.0+) = more varied but may reduce quality. Default: 0.9",
        "param.topk_tip": "Limits sampling to top K most likely tokens. Lower (10-30) = more focused, predictable. Higher = more diverse. Default: 50",
        "param.topp_tip": "Nucleus sampling: only tokens whose cumulative probability reaches P are considered. Lower (0.7-0.9) cuts unlikely tokens. Default: 1.0",
        "param.rep_tip": "Penalizes repeated tokens. Increase (1.1-1.3) if you hear repeated sounds or artifacts. Too high may distort speech. Default: 1.05",
        "param.tokens_tip": "Maximum audio codec tokens to generate. Increase for very long texts. ~256 tokens = ~5-10 seconds of audio. Default: 2048",
        # Progress
        "progress.generating": "Generating audio...",
        "progress.designing": "Designing voice...",
        "progress.cloning": "Cloning voice...",
        "progress.first_slow": "First request after model load can be slower.",
        # Errors
        "error.prefix": "Error",
        "error.generation_failed": "Generation failed",
        "error.no_ref_audio": "Please select a reference audio file",
        "error.switch_failed": "Failed to switch model",
        "error.model_info": "Model info unavailable.",
        # Result
        "misc.result": "Result:",
        "misc.download": "Download WAV",
        "misc.download_title": "Download generated WAV",
        # Footer
        "footer.api_docs": "API Documentation",
        "footer.health": "Health Check",
        # Speakers (descriptions only, names stay)
        "speaker.serena": "Serena (Female, warm)",
        "speaker.sohee": "Sohee (Female, emotional)",
        "speaker.vivian": "Vivian (Female, bright)",
        "speaker.ono_anna": "Ono_Anna (Female, playful)",
        "speaker.ryan": "Ryan (Male, dynamic)",
        "speaker.aiden": "Aiden (Male, clear)",
        "speaker.uncle_fu": "Uncle_Fu (Male, mellow)",
        "speaker.dylan": "Dylan (Male, youthful)",
        "speaker.eric": "Eric (Male, lively)",
        # Dynamic: switch modal
        "modal.switch_to": "Switch to",
        "modal.switch_warn": "This will reload the TTS model. Server unavailable for ~2 minutes.",
    },
}

# Safe JSON serialization into JS
_T_JSON = json.dumps(TRANSLATIONS, ensure_ascii=False)

I18N_SCRIPT = f"""
const T = {_T_JSON};
let currentLang = localStorage.getItem('ui-lang') || 'ru';

function t(key) {{
  return T[currentLang]?.[key] ?? T.en?.[key] ?? key;
}}

function applyTranslations(root) {{
  (root || document).querySelectorAll('[data-i18n]').forEach(el => {{
    el.textContent = t(el.dataset.i18n);
  }});
  (root || document).querySelectorAll('[data-i18n-placeholder]').forEach(el => {{
    el.placeholder = t(el.dataset.i18nPlaceholder);
  }});
  (root || document).querySelectorAll('[data-i18n-title]').forEach(el => {{
    el.title = t(el.dataset.i18nTitle);
  }});
  document.documentElement.lang = currentLang;
}}

function switchUiLang(lang) {{
  currentLang = lang;
  localStorage.setItem('ui-lang', lang);
  applyTranslations();
  updateLangToggle();
}}

function updateLangToggle() {{
  const btn = document.getElementById('lang-toggle');
  if (!btn) return;
  btn.textContent = currentLang === 'ru' ? 'EN' : 'РУ';
  btn.setAttribute('aria-label',
    currentLang === 'ru' ? 'Switch to English' : 'Переключить на русский');
}}
"""
