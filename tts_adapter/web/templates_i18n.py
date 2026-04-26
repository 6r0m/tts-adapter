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
        "loading.hint": "Это может занять до 60 секунд. Подождите.",
        # Switch modal
        "modal.switch_title": "Сменить модель?",
        "modal.switch_msg": "Модель будет перезагружена. Сервер ненадолго станет недоступен.",
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
        "help.switch_hint": "Смена модели перезагружает сервер и может занять до 60 секунд.",
        # Advanced settings help
        "help.params_title": "Параметры генерации",
        "help.params_intro": "Эти параметры управляют генерацией аудио-токенов. Значения по умолчанию подходят для большинства случаев.",
        "help.close_params": "Закрыть справку по параметрам",
        "help.temp_desc": "Разнообразие голоса (0.01–2.0). Ниже (0.3–0.7) — стабильный ровный голос для озвучки и новостей. Выше (1.0–1.5) — живой выразительный для персонажей и рекламы. Выше 1.5 может звучать странно.",
        "help.topk_desc": "Варианты произношения (1–200). Ниже (10–30) — чёткий предсказуемый голос для объявлений. Выше (80–150) — богаче интонации для подкастов и художественного чтения.",
        "help.topp_desc": "Порог отбора (0.1–1.0). Ниже (0.7–0.9) — только лучшие варианты, чище звук для продакшна. При 1.0 — все варианты, максимум естественности для разговорного стиля.",
        "help.rep_desc": "Защита от повторов (1.0–2.0). При 1.0 — без защиты. 1.1–1.3 — убирает заикания, если слышите артефакты. Выше 1.5 может исказить речь.",
        "help.tokens_desc": "Макс. длина аудио (256–4096). 256 ≈ 5–10 сек, 2048 ≈ 1–2 мин. Увеличьте для длинных текстов, уменьшите для коротких фраз.",
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
        "cap.emotion": "Эмоция",
        "cap.simple_full": "Простой (стиль инструкцией)",
        "cap.design_full": "Дизайн голоса",
        "cap.clone_full": "Клонирование голоса",
        "cap.emotion_full": "Эмоциональное клонирование",
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
        "label.emotion_mode": "Эмоция",
        "label.emotion_audio": "Референс эмоции (WAV)",
        "label.emotion_text": "Текст эмоции",
        "label.emotion_vector": "Вектор эмоции",
        "label.emotion_alpha": "Сила эмоции",
        # Placeholders
        "ph.text": "Введите текст...",
        "ph.instruct": "напр., Говорите медленно и тепло",
        "ph.design_instruct": "напр., Взрослый женский голос, контральто, тёплый и уверенный",
        "ph.ref_text": "Что сказано в референсном аудио",
        "ph.emotion_text": "напр., радостно и тепло",
        # Tooltips
        "title.text": "Обязательный текст для синтеза",
        "title.language": "Язык выходной речи",
        "title.speaker": "Предустановленный диктор (модель CustomVoice)",
        "title.instruct": "Стиль инструкция (модель CustomVoice)",
        "title.design_instruct": "Описание голоса (модель VoiceDesign)",
        "title.ref_audio": "WAV файл, 3-10 секунд",
        "title.ref_text": "Транскрипт референсного аудио",
        "title.emotion_mode": "Дополнительное управление эмоцией для поддерживаемых моделей",
        "title.emotion_audio": "WAV файл для переноса эмоции",
        "title.emotion_text": "Описание эмоции свободным текстом",
        "title.emotion_alpha": "Сила смешивания эмоции от 0 до 1",
        # Emotion controls
        "emotion.none": "Без эмоции",
        "emotion.audio": "Аудио эмоции",
        "emotion.text": "Текст эмоции",
        "emotion.vector": "Вектор эмоции",
        "emotion.happy": "Радость",
        "emotion.angry": "Злость",
        "emotion.sad": "Грусть",
        "emotion.afraid": "Страх",
        "emotion.disgusted": "Отвращение",
        "emotion.melancholic": "Меланхолия",
        "emotion.surprised": "Удивление",
        "emotion.calm": "Спокойствие",
        # Language fallback (when active engine doesn't support preferred language)
        "lang.unsupported_hint": "{preferred} не поддерживается движком {engine}. Выбран {lang}. Переключите движок, чтобы использовать {preferred}.",
        # Hints
        "hint.instruct": "Управляйте тоном, эмоцией, скоростью. Только для модели CustomVoice.",
        "hint.design": "Опишите голос: пол, возраст, высота, тембр, эмоция, темп. Мы обрезаем тишину.",
        # Buttons
        "btn.generate": "Сгенерировать речь",
        "btn.generate_design": "Сгенерировать с дизайном голоса",
        "btn.generate_clone": "Сгенерировать с клоном голоса",
        "btn.generating": "Генерация...",
        "btn.switching": "Смена...",
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
        "param.temp_tip": "Разнообразие голоса (0.01–2.0, обычно 0.9). Ниже (0.3–0.7): стабильный, ровный голос — для озвучки книг, новостей, инструкций. Выше (1.0–1.5): живой, выразительный — для персонажей, рекламы. Выше 1.5 может звучать странно.",
        "param.topk_tip": "Сколько вариантов произношения рассматривать (1–200, обычно 50). Ниже (10–30): чёткий, предсказуемый голос — для официальных объявлений, навигации. Выше (80–150): разнообразнее интонации — для художественного чтения, подкастов.",
        "param.topp_tip": "Порог отбора вариантов (0.1–1.0, обычно 1.0). Ниже (0.7–0.9): только лучшие варианты, чище звук — для продакшн-озвучки. При 1.0: все варианты, максимум естественности — для разговорного стиля.",
        "param.rep_tip": "Защита от повторов (1.0–2.0, обычно 1.05). При 1.0: без защиты. 1.1–1.3: убирает заикания и повторяющиеся звуки — если слышите артефакты. Выше 1.5: может исказить речь, используйте осторожно.",
        "param.tokens_tip": "Макс. длина аудио (256–4096, обычно 2048). 256 ≈ 5–10 сек, 2048 ≈ 1–2 мин. Увеличьте (3072–4096) для длинных абзацев. Уменьшите для коротких фраз — быстрее генерация.",
        # Aliases keyed by the actual GenerationParam.key so localizedParamLabel()
        # finds them. The legacy *_tip keys above are kept for the static
        # Advanced Help popup that pre-dates per-engine generation_params.
        "param.repetition_penalty": "Штраф повтора",
        "param.repetition_penalty_tip": "Защита от повторов (1.0–2.0, обычно 1.05). При 1.0: без защиты. 1.1–1.3: убирает заикания и повторяющиеся звуки — если слышите артефакты. Выше 1.5: может исказить речь, используйте осторожно.",
        "param.max_new_tokens": "Макс. токенов",
        "param.max_new_tokens_tip": "Макс. длина аудио (256–4096, обычно 2048). 256 ≈ 5–10 сек, 2048 ≈ 1–2 мин. Увеличьте (3072–4096) для длинных абзацев. Уменьшите для коротких фраз — быстрее генерация.",
        # VoxCPM2-specific generation params (engine declares these)
        "param.cfg_value": "Сила следования стилю (CFG)",
        "param.cfg_value_tip": "Управление стилем/текстом (1.0–4.0, обычно 2.0). Ниже (1.2–1.8): более естественный голос, слабее реакция на тег эмоции. Выше (2.5–3.5): сильнее следует тегу эмоции, может звучать резче. Меняйте по чуть-чуть.",
        "param.inference_timesteps": "Шагов диффузии",
        "param.inference_timesteps_tip": "Шаги диффузии при генерации (4–30, по умолчанию 10 — рекомендация авторов VoxCPM2). 6–8: быстрее (~25%), приемлемое качество для черновиков. 10: оптимум качество/скорость. 15–20: чище звук для финальной озвучки, медленнее.",
        # IndexTTS2 has the same keys as qwen3 (temperature/top_k/top_p/rep_penalty/max_tokens),
        # so it reuses param.temp_tip etc. above. If IndexTTS2 needs distinct hints later,
        # add param.temperature_indextts2_tip / etc. and the UI lookup below will use them.
        # Empty-state for the popup when an engine has no exposed knobs:
        "help.no_params": "Эта модель не имеет настраиваемых параметров.",
        # Progress
        "progress.generating": "Генерация аудио...",
        "progress.designing": "Создание голоса...",
        "progress.cloning": "Клонирование голоса...",
        "progress.first_slow": "Первый запрос после загрузки модели может быть медленнее.",
        # Errors
        "error.prefix": "Ошибка",
        "error.generation_failed": "Генерация не удалась",
        "error.no_ref_audio": "Выберите файл референсного аудио",
        "error.no_emotion_audio": "Выберите WAV файл эмоции",
        "error.no_emotion_text": "Введите текст эмоции",
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
        "modal.switch_warn": "Модель TTS будет перезагружена. Сервер ненадолго станет недоступен.",
        "modal.switch_warn_engine": "Текущий движок будет выгружен, выбранный движок будет загружен. Это может занять до 60 секунд.",
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
        "loading.hint": "This can take up to 60 seconds. Please wait.",
        # Switch modal
        "modal.switch_title": "Switch Model?",
        "modal.switch_msg": "This will reload the TTS model. The server will be briefly unavailable.",
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
        "help.switch_hint": "Switching models reloads the server and can take up to 60 seconds.",
        # Advanced settings help
        "help.params_title": "Generation Parameters",
        "help.params_intro": "These parameters control how the model generates audio tokens. Defaults work well for most cases.",
        "help.no_params": "This model has no tunable parameters.",
        "param.cfg_value": "CFG Guidance",
        "param.cfg_value_tip": "Style/text adherence (1.0–4.0, default 2.0). Lower (1.2–1.8): more natural voice, weaker reaction to the emotion tag. Higher (2.5–3.5): follows the emotion tag more strongly, may sound harsher. Adjust in small steps.",
        "param.inference_timesteps": "Diffusion Steps",
        "param.inference_timesteps_tip": "Diffusion steps during generation (4–30, default 10 — VoxCPM2 authors' recommendation). 6–8: ~25% faster, acceptable for drafts. 10: best quality/speed tradeoff. 15–20: cleaner final audio, slower.",
        # Aliases keyed by GenerationParam.key for localizedParamLabel() lookup.
        "param.repetition_penalty": "Repetition Penalty",
        "param.repetition_penalty_tip": "Penalize repeated tokens (1.0–2.0, default 1.05). At 1.0: no penalty. 1.1–1.3: removes stutters / repeating sounds. Above 1.5: may distort speech.",
        "param.max_new_tokens": "Max Tokens",
        "param.max_new_tokens_tip": "Max audio length (256–4096, default 2048). 256 ≈ 5–10 sec, 2048 ≈ 1–2 min. Raise (3072–4096) for long paragraphs; lower for short phrases (faster generation).",
        "help.close_params": "Close parameter guide",
        "help.temp_desc": "Voice variety (0.01–2.0). Lower (0.3–0.7) — stable even voice for narration and news. Higher (1.0–1.5) — lively expressive for characters and ads. Above 1.5 may sound unnatural.",
        "help.topk_desc": "Pronunciation options (1–200). Lower (10–30) — clear predictable voice for announcements. Higher (80–150) — richer intonation for podcasts and storytelling.",
        "help.topp_desc": "Selection threshold (0.1–1.0). Lower (0.7–0.9) — only best options, cleaner sound for production. At 1.0 — all options, maximum naturalness for conversational style.",
        "help.rep_desc": "Repeat protection (1.0–2.0). At 1.0 — no protection. 1.1–1.3 — removes stuttering, use if you hear artifacts. Above 1.5 may distort speech.",
        "help.tokens_desc": "Max audio length (256–4096). 256 ≈ 5–10 sec, 2048 ≈ 1–2 min. Increase for long texts, decrease for short phrases.",
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
        "cap.emotion": "Emotion",
        "cap.simple_full": "Simple (style instruction)",
        "cap.design_full": "Voice Design",
        "cap.clone_full": "Voice Clone",
        "cap.emotion_full": "Emotional Voice Clone",
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
        "label.emotion_mode": "Emotion control",
        "label.emotion_audio": "Emotion reference audio (WAV)",
        "label.emotion_text": "Emotion text",
        "label.emotion_vector": "Emotion vector",
        "label.emotion_alpha": "Emotion strength",
        # Placeholders
        "ph.text": "Enter text here...",
        "ph.instruct": "e.g., Speak slowly and warmly",
        "ph.design_instruct": "e.g., Adult female voice, contralto range, warm and confident, expressive",
        "ph.ref_text": "What is said in the reference audio",
        "ph.emotion_text": "e.g., excited and warm",
        # Tooltips
        "title.text": "Required text to synthesize",
        "title.language": "Language for output speech",
        "title.speaker": "Preset speaker (CustomVoice model)",
        "title.instruct": "Optional style instruction (CustomVoice model)",
        "title.design_instruct": "Required voice description (VoiceDesign model)",
        "title.ref_audio": "Required WAV file, 3-10 seconds",
        "title.ref_text": "Optional transcript of the reference audio",
        "title.emotion_mode": "Optional emotion input for models that support emotional cloning",
        "title.emotion_audio": "Optional WAV file for emotion transfer",
        "title.emotion_text": "Free-form emotion description",
        "title.emotion_alpha": "Emotion blend strength from 0 to 1",
        # Emotion controls
        "emotion.none": "None",
        "emotion.audio": "Emotion audio",
        "emotion.text": "Emotion text",
        "emotion.vector": "Emotion vector",
        "emotion.happy": "Happy",
        "emotion.angry": "Angry",
        "emotion.sad": "Sad",
        "emotion.afraid": "Afraid",
        "emotion.disgusted": "Disgusted",
        "emotion.melancholic": "Melancholic",
        "emotion.surprised": "Surprised",
        "emotion.calm": "Calm",
        # Language fallback (when active engine doesn't support preferred language)
        "lang.unsupported_hint": "{preferred} is not supported by engine {engine}. Defaulted to {lang}. Switch engine to use {preferred}.",
        # Hints
        "hint.instruct": "Control tone, emotion, speed. Works with CustomVoice model only.",
        "hint.design": "Describe the voice: gender, age, pitch, timbre, emotion, pace. We trim trailing silence.",
        # Buttons
        "btn.generate": "Generate Speech",
        "btn.generate_design": "Generate with Designed Voice",
        "btn.generate_clone": "Generate with Cloned Voice",
        "btn.generating": "Generating...",
        "btn.switching": "Switching...",
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
        "param.temp_tip": "Voice variety (0.01–2.0, default 0.9). Lower (0.3–0.7): stable, even voice — for audiobooks, news, instructions. Higher (1.0–1.5): lively, expressive — for characters, ads. Above 1.5 may sound unnatural.",
        "param.topk_tip": "How many pronunciation options to consider (1–200, default 50). Lower (10–30): clear, predictable voice — for announcements, navigation. Higher (80–150): richer intonation — for storytelling, podcasts.",
        "param.topp_tip": "Selection threshold for options (0.1–1.0, default 1.0). Lower (0.7–0.9): only best options, cleaner sound — for production voiceover. At 1.0: all options, maximum naturalness — for conversational style.",
        "param.rep_tip": "Repeat protection (1.0–2.0, default 1.05). At 1.0: no protection. 1.1–1.3: removes stuttering and repeated sounds — use if you hear artifacts. Above 1.5: may distort speech, use carefully.",
        "param.tokens_tip": "Max audio length (256–4096, default 2048). 256 ≈ 5–10 sec, 2048 ≈ 1–2 min. Increase (3072–4096) for long paragraphs. Decrease for short phrases — faster generation.",
        # Progress
        "progress.generating": "Generating audio...",
        "progress.designing": "Designing voice...",
        "progress.cloning": "Cloning voice...",
        "progress.first_slow": "First request after model load can be slower.",
        # Errors
        "error.prefix": "Error",
        "error.generation_failed": "Generation failed",
        "error.no_ref_audio": "Please select a reference audio file",
        "error.no_emotion_audio": "Please select an emotion WAV file",
        "error.no_emotion_text": "Please enter emotion text",
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
        "modal.switch_warn": "This will reload the TTS model. The server will be briefly unavailable.",
        "modal.switch_warn_engine": "This will unload the current engine and load the selected engine. This can take up to 60 seconds.",
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
    const val = t(el.dataset.i18nTitle);
    el.title = val;
    if (el.hasAttribute('aria-label')) el.setAttribute('aria-label', val);
  }});
  document.documentElement.lang = currentLang;
}}

function switchUiLang(lang) {{
  currentLang = lang;
  localStorage.setItem('ui-lang', lang);
  applyTranslations();
  updateLangToggle();
  if (typeof rerenderDynamicTexts === 'function') rerenderDynamicTexts();
}}

function updateLangToggle() {{
  const ru = document.getElementById('lang-btn-ru');
  const en = document.getElementById('lang-btn-en');
  if (!ru || !en) return;
  ru.classList.toggle('lang-active', currentLang === 'ru');
  en.classList.toggle('lang-active', currentLang === 'en');
}}
"""
