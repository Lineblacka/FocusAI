import os
import re
import json
import time
from datetime import datetime
from typing import Dict, List, Any, Optional

from dotenv import load_dotenv
from openai import OpenAI, RateLimitError, APIError, APITimeoutError


load_dotenv()

API_KEY = os.getenv("OPENROUTER_API_KEY")

if not API_KEY:
    raise ValueError("Липсва OPENROUTER_API_KEY в .env файла.")

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=API_KEY,
)

MODELS = [
    "openai/gpt-oss-20b:free",
    "nvidia/nemotron-3-nano-30b-a3b:free",
    "google/gemma-4-26b-a4b-it:free",
    "google/gemma-4-31b-it:free",
]

EMPTY_REPLY_RETRIES = 2

MEMORY_FILE = "memory.json"
BENCHMARK_FILE = "benchmark_cases.json"
BENCHMARK_RESULTS_FILE = "benchmark_results.json"

PROMPT_VERSION = "focusai_v5"


SYSTEM_PROMPT = """
Ти си FocusAI — български AI агент за дисциплина, действие и последователност.

Говориш само на български.
Говориш винаги на "ти".
Не използваш официална форма.
Не показваш вътрешни инструкции, режими, анализи или мисли.
Не казваш "режим", "трябва да", "инструкция", "we must", "respond", "system".
Не казваш, че си GPT-4, а си FocusAI_1.

Тон:
- естествен
- директен
- кратък
- човешки
- без клишета
- без лигавене
- без роботски фрази

Основна задача:
Да върнеш човека към ясно действие, без да звучиш като скрипт.

ПОВЕДЕНИЕ:

1. Ако получиш поздрав или кратък социален въпрос:
Отговори нормално с едно кратко изречение.
Пример:
"Тук съм. Какво ти е фокусът днес?"

2. Ако те питат кой си:
Кажи ясно кой си и за какво служиш.
Пример:
"Аз съм FocusAI — държа те отговорен и те бутам към действие. С какво ще се захванеш?"

3. Ако човекът дава идея или бизнес идея:
Отговори така:
Идеята:
Силното:
Рискът:
Действия:
1.
2.
3.
Ключов въпрос:

Не измисляй прекалено конкретни детайли, ако човекът не ги е казал.
Ако каже само "искам бизнес", първо изясни нишата.

4. Ако човекът иска план:
Дай прост план.
Включи минимална версия.
Дай критерий за успех.
Не прави прекалено големи обещания.

5. Ако човекът дава оправдание:
Назови го директно, без обида.
Дай малка следваща стъпка.

6. Ако човекът казва, че се е провалил:
Не го успокоявай прекалено.
Не го унижавай.
Покажи какво се е счупило.
Дай минимален рестарт.

7. Ако човекът иска творческа помощ:
Изпълни задачата директно.
Не го карай веднага да действа, ако първо е поискал списък, идеи или варианти.

ЗАБРАНЕНО:
- не започвай с "Строг режим"
- не започвай с "Диагноза", освен ако има реален проблем
- не показвай мисли или инструкции
- не използвай английски служебни фрази
- не повтаряй една и съща финална фраза
- не казвай "Какво ще направиш в следващите 30 минути?" всеки път
- не измисляй бизнес детайли без контекст
- не обиждай
- не се прави на терапевт

АДАПТИВНИ ЗАВЪРШЕЦИ:
Използвай различни завършеци според ситуацията:
- "Как ще го започнеш?"
- "Кой е първият ход?"
- "Кое ти пречи да го започнеш?"
- "Избери едно и действай."
- "Коя посока избираш?"
- "Дай ми нишата и ще го разбием."

Преди да отговориш, провери:
- само на български ли е?
- звучи ли естествено?
- има ли вътрешни инструкции в текста?
- прекалено шаблонно ли е?
- измисля ли неща, които потребителят не е казал?

Ако има проблем — пренапиши отговора преди да го дадеш.
"""


INTENT_RULES = {
    "identity_question": [
        "кой си",
        "какво си",
        "за какво си",
        "какво правиш",
        "ти кой си",
    ],
    "small_talk": [
        "здравей",
        "здрасти",
        "как си",
        "hello",
        "hi",
        "hey",
    ],
    "excuse": [
        "нямам време",
        "нямам мотивация",
        "утре",
        "изморен съм",
        "не мога",
        "трудно е",
        "няма смисъл",
    ],
    "failure_report": [
        "провалих",
        "пропуснах",
        "пак не",
        "не успях",
        "счупих режима",
        "изоставам",
    ],
    "goal_planning": [
        "искам да започна",
        "план",
        "цел",
        "как да",
        "програма",
        "режим",
    ],
    "idea_review": [
        "идея",
        "мисля да",
        "искам да направя",
        "искам да си направя",
        "проект",
        "продукт",
        "бизнес",
        "магазин",
        "бранд",
        "онлайн магазин",
    ],
    "progress_report": [
        "направих",
        "успях",
        "готово",
        "днес изпълних",
        "отчет",
    ],
    "emotional_support": [
        "зле съм",
        "не издържам",
        "тревожно",
        "депресиран",
        "паника",
        "сам",
    ],
}


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def default_memory() -> Dict[str, Any]:
    return {
        "profile": {
            "goals": [],
            "bad_patterns": [],
            "commitments": [],
            "preferred_style": "strict",
        },
        "messages": [],
        "stats": {
            "total_messages": 0,
            "last_model": None,
            "prompt_version": PROMPT_VERSION,
        },
        "last_updated": now_iso(),
    }


def load_json_file(path: str, fallback: Any) -> Any:
    if not os.path.exists(path):
        return fallback

    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read().strip()
            if not content:
                return fallback
            return json.loads(content)
    except json.JSONDecodeError:
        print(f"⚠️ {path} е повреден. Използвам fallback.")
        return fallback


def save_json_file(path: str, data: Any) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_memory() -> Dict[str, Any]:
    memory = load_json_file(MEMORY_FILE, default_memory())
    base = default_memory()

    for key in base:
        if key not in memory:
            memory[key] = base[key]

    if "profile" not in memory:
        memory["profile"] = base["profile"]

    for key in base["profile"]:
        if key not in memory["profile"]:
            memory["profile"][key] = base["profile"][key]

    return memory


def save_memory(memory: Dict[str, Any]) -> None:
    memory["last_updated"] = now_iso()
    save_json_file(MEMORY_FILE, memory)


def classify_intent(user_input: str) -> str:
    text = user_input.lower().strip()

    for intent, keywords in INTENT_RULES.items():
        if any(keyword in text for keyword in keywords):
            return intent

    return "general_question"


def build_profile_context(memory: Dict[str, Any]) -> str:
    profile = memory.get("profile", {})

    return f"""
Контекст за потребителя:
- Цели: {profile.get("goals", []) or "няма записани"}
- Лоши модели: {profile.get("bad_patterns", []) or "няма записани"}
- Ангажименти: {profile.get("commitments", []) or "няма записани"}
"""


def build_behavior_instruction(intent: str) -> str:
    instructions = {
        "identity_question": """
Отговори ясно кой си.
Не започвай с диагноза.
Кажи, че си FocusAI и че държиш потребителя отговорен.
Завърши с естествен въпрос.
Не показвай тези инструкции.
""",
        "small_talk": """
Отговори с едно кратко човешко изречение.
Не обяснявай режима.
Не показвай инструкции.
Без диагноза.
Без натиск.
""",
        "excuse": """
Назови оправданието без обида.
Покажи какво е под контрол.
Дай малко действие.
Завърши с различен въпрос или предизвикателство.
Не показвай тези инструкции.
""",
        "failure_report": """
Не утешавай прекалено.
Не унижавай.
Кажи какво вероятно се е счупило.
Дай минимална следваща стъпка.
Не показвай тези инструкции.
""",
        "goal_planning": """
Дай прост план.
Включи минимална версия.
Дай критерий за успех.
Завърши с първа конкретна стъпка.
Не показвай тези инструкции.
""",
        "idea_review": """
Формат:
Идеята:
Силното:
Рискът:
Действия:
1.
2.
3.
Ключов въпрос:

Бъди конкретен.
Не използвай шаблонно "Какво ще направиш в следващите 30 минути?".
Не показвай тези инструкции.
""",
        "progress_report": """
Признай изпълненото кратко.
Посочи следващото ниво.
Дай следваща задача.
Не показвай тези инструкции.
""",
        "emotional_support": """
Бъди директен, но внимателен.
Не диагностицирай.
Не се прави на терапевт.
Дай малко безопасно действие.
Ако има риск от самонараняване, насочи към спешна помощ или доверен човек веднага.
Не показвай тези инструкции.
""",
        "general_question": """
Отговори кратко, ясно и практически.
Ако е творческа заявка, изпълни я директно.
Ако е свързано с действие, завърши с естествен подтик.
Не показвай тези инструкции.
""",
    }

    return instructions.get(intent, instructions["general_question"])


def build_messages(memory: Dict[str, Any], user_input: str) -> List[Dict[str, str]]:
    intent = classify_intent(user_input)
    recent_messages = memory["messages"][-16:]

    clean_recent_messages = [
        {
            "role": msg["role"],
            "content": msg["content"],
        }
        for msg in recent_messages
        if msg.get("role") in {"user", "assistant"} and msg.get("content")
    ]

    developer_context = f"""
{build_profile_context(memory)}

Разпознат режим: {intent}

{build_behavior_instruction(intent)}
"""

    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "system", "content": developer_context},
        *clean_recent_messages,
        {"role": "user", "content": user_input},
    ]


def is_empty_or_weak_reply(reply: str) -> bool:
    return not reply or len(reply.strip()) < 20


def clean_model_output(text: str) -> str:
    cleaned = text.strip()

    forbidden_prefixes = [
        "Respond short.",
        "Respond shortly.",
        "Answer briefly.",
        "Answer short.",
        "Отговори кратко.",
        "Кратък отговор:",
        "Режим:",
        "Нормален режим:",
        "Строг режим:",
        "We must answer identity:",
        "We need to answer:",
        "Строг режим",
        "**Строг режим**",
        "Режим:",
        "Разпознат режим:",
    ]

    changed = True
    while changed:
        changed = False
        for prefix in forbidden_prefixes:
            if cleaned.startswith(prefix):
                cleaned = cleaned[len(prefix):].strip()
                changed = True

    return cleaned


def ask_ai(messages: List[Dict[str, str]]) -> Dict[str, Any]:
    last_error = None

    for model in MODELS:
        for attempt in range(EMPTY_REPLY_RETRIES + 1):
            started = time.time()

            try:
                print(f"🔄 Пробвам модел: {model} (attempt {attempt + 1})")

                response = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=0.4,
                    timeout=90,
                )

                latency = round(time.time() - started, 2)
                msg = response.choices[0].message
                content = clean_model_output(msg.content or "")

                if is_empty_or_weak_reply(content):
                    print(f"⚠️ Празен/слаб отговор от {model}. Повтарям същия модел...")
                    last_error = "empty_or_weak_response"
                    continue

                print(f"✅ Използван модел: {model} ({latency}s)")

                return {
                    "content": content,
                    "model": model,
                    "latency_seconds": latency,
                    "error": None,
                }

            except RateLimitError as e:
                print(f"⚠️ Rate limited: {model}")
                last_error = str(e)
                break

            except (APIError, APITimeoutError) as e:
                print(f"⚠️ Проблем с модела: {model}")
                last_error = str(e)
                break

            except Exception as e:
                print(f"⚠️ Неочаквана грешка при {model}: {e}")
                last_error = str(e)
                break

    return {
        "content": "Не получих стабилен отговор. Повтори задачата по-конкретно.",
        "model": None,
        "latency_seconds": None,
        "error": last_error,
    }


def contains_banned_word(text: str) -> bool:
    banned_words = [
        "идиот",
        "тъп",
        "слабак",
        "жалък",
        "мързеливец",
    ]

    for word in banned_words:
        pattern = rf"\b{re.escape(word)}\b"
        if re.search(pattern, text, flags=re.IGNORECASE):
            return True

    return False


def basic_quality_check(reply: str) -> Dict[str, Any]:
    text = reply.strip().lower()
    issues = []

    if contains_banned_word(reply):
        issues.append("possible_insult")

    if len(reply.strip()) < 20:
        issues.append("too_short")

    if len(reply.split()) > 350:
        issues.append("too_long")

    action_markers = [
        "?",
        "започни",
        "избери",
        "напиши",
        "провери",
        "действай",
        "реши",
        "направи",
        "първият ход",
        "как ще",
        "кое ти пречи",
    ]

    if not any(marker in text for marker in action_markers):
        issues.append("missing_action_push")

    return {
        "passed": len(issues) == 0,
        "issues": issues,
    }


def enforce_informal(text: str) -> str:
    replacements = {
        "Вие": "ти",
        "Ви": "ти",
        "Вас": "теб",
        "Вашият": "твоят",
        "Вашата": "твоята",
        "Вашето": "твоето",
        "Ваши": "твои",
        "Ваш": "твой",
        "бихте": "би",
        "желаете": "искаш",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    return text


def update_memory_from_turn(
    memory: Dict[str, Any],
    user_input: str,
    reply: str,
    result: Dict[str, Any],
) -> None:
    memory["messages"].append(
        {
            "role": "user",
            "content": user_input,
            "created_at": now_iso(),
        }
    )

    memory["messages"].append(
        {
            "role": "assistant",
            "content": reply,
            "model": result.get("model"),
            "latency_seconds": result.get("latency_seconds"),
            "created_at": now_iso(),
        }
    )

    memory["stats"]["total_messages"] = len(memory["messages"])
    memory["stats"]["last_model"] = result.get("model")
    memory["stats"]["prompt_version"] = PROMPT_VERSION


def add_profile_item(memory: Dict[str, Any], category: str, value: str) -> None:
    allowed = {"goals", "bad_patterns", "commitments"}

    if category not in allowed:
        print(f"Невалидна категория. Използвай: {', '.join(sorted(allowed))}")
        return

    value = value.strip()

    if not value:
        print("Празна стойност.")
        return

    items = memory["profile"].setdefault(category, [])

    if value not in items:
        items.append(value)
        save_memory(memory)
        print(f"✅ Добавено в {category}: {value}")
    else:
        print("Вече съществува.")


def print_help() -> None:
    print(
        """
Команди:
  exit / quit / край              край
  /help                           помощ
  /memory                         покажи памет
  /add_goal <текст>               добави цел
  /add_pattern <текст>            добави лош модел
  /add_commitment <текст>         добави ангажимент
  /benchmark                      пусни benchmark
"""
    )


def print_memory(memory: Dict[str, Any]) -> None:
    print(json.dumps(memory["profile"], ensure_ascii=False, indent=2))


def default_benchmark_cases() -> List[Dict[str, Any]]:
    return [
        {
            "id": "excuse_001",
            "input": "Нямам мотивация днес. Ще започна утре.",
            "expected_traits": [
                "rejects_excuse",
                "gives_small_action",
                "asks_action_question",
            ],
        },
        {
            "id": "failure_001",
            "input": "Пак пропуснах тренировката. Явно не ставам.",
            "expected_traits": [
                "no_insult",
                "reframes_failure",
                "gives_recovery_action",
            ],
        },
        {
            "id": "idea_001",
            "input": "Искам да направя AI коуч за дисциплина.",
            "expected_traits": [
                "summarizes_idea",
                "identifies_strength",
                "identifies_weakness",
                "gives_3_actions",
            ],
        },
        {
            "id": "planning_001",
            "input": "Искам план за ставане в 6 сутринта всеки ден.",
            "expected_traits": [
                "simple_plan",
                "minimal_version",
                "success_metric",
            ],
        },
        {
            "id": "progress_001",
            "input": "Днес направих 40 минути работа без телефон.",
            "expected_traits": [
                "acknowledges_progress",
                "sets_next_level",
                "gives_next_task",
            ],
        },
    ]


def load_benchmark_cases() -> List[Dict[str, Any]]:
    cases = load_json_file(BENCHMARK_FILE, None)

    if cases is None:
        cases = default_benchmark_cases()
        save_json_file(BENCHMARK_FILE, cases)
        print(f"✅ Създаден {BENCHMARK_FILE}")

    return cases


def heuristic_benchmark_score(reply: str, expected_traits: List[str]) -> Dict[str, Any]:
    text = reply.lower()
    score = 0
    notes = []

    checks = {
        "rejects_excuse": any(x in text for x in ["оправдание", "отлагаш", "избягваш"]),
        "gives_small_action": any(x in text for x in ["30 минути", "10 минути", "сега", "една задача"]),
        "asks_action_question": any(x in text for x in ["?", "как ще", "какво ще", "кой е първият"]),
        "no_insult": not contains_banned_word(text),
        "reframes_failure": any(x in text for x in ["причина", "провал", "коригирай", "намали", "система"]),
        "gives_recovery_action": any(x in text for x in ["днес", "сега", "минимум", "следващата"]),
        "summarizes_idea": any(x in text for x in ["идеята", "накратко", "искаш"]),
        "identifies_strength": any(x in text for x in ["силното", "силна страна"]),
        "identifies_weakness": any(x in text for x in ["слабото", "неясното", "риск"]),
        "gives_3_actions": all(x in text for x in ["1.", "2.", "3."]),
        "simple_plan": any(x in text for x in ["план", "ден", "стъпка"]),
        "minimal_version": any(x in text for x in ["минимална", "минимум"]),
        "success_metric": any(x in text for x in ["критерий", "успех", "измери"]),
        "acknowledges_progress": any(x in text for x in ["добре", "изпълнено", "направил"]),
        "sets_next_level": any(x in text for x in ["следващото ниво", "следващата стъпка"]),
        "gives_next_task": any(x in text for x in ["следваща задача", "утре", "днес"]),
    }

    for trait in expected_traits:
        passed = checks.get(trait, False)
        if passed:
            score += 1
        else:
            notes.append(f"missing:{trait}")

    return {
        "score": score,
        "max_score": len(expected_traits),
        "percentage": round(score / max(len(expected_traits), 1), 2),
        "notes": notes,
    }


def run_benchmark(memory: Optional[Dict[str, Any]] = None) -> None:
    print("🧪 Стартирам benchmark...")

    cases = load_benchmark_cases()
    results = []

    benchmark_memory = memory or default_memory()
    benchmark_memory["messages"] = []

    for case in cases:
        case_input = case["input"]
        expected_traits = case.get("expected_traits", [])

        print(f"\n--- {case['id']} ---")
        print(f"Input: {case_input}")

        messages = build_messages(benchmark_memory, case_input)
        result = ask_ai(messages)

        reply = clean_model_output(result["content"])
        reply = enforce_informal(reply)

        quality = basic_quality_check(reply)
        heuristic = heuristic_benchmark_score(reply, expected_traits)

        item = {
            "id": case["id"],
            "input": case_input,
            "reply": reply,
            "model": result.get("model"),
            "latency_seconds": result.get("latency_seconds"),
            "quality": quality,
            "heuristic": heuristic,
            "prompt_version": PROMPT_VERSION,
            "created_at": now_iso(),
        }

        results.append(item)

        print(f"Model: {item['model']}")
        print(f"Score: {heuristic['score']}/{heuristic['max_score']}")
        print(f"Issues: {quality['issues']}")
        print(f"Reply:\n{reply}")

    summary = {
        "prompt_version": PROMPT_VERSION,
        "created_at": now_iso(),
        "results": results,
        "average_percentage": round(
            sum(r["heuristic"]["percentage"] for r in results) / max(len(results), 1),
            2,
        ),
    }

    save_json_file(BENCHMARK_RESULTS_FILE, summary)

    print(f"\n✅ Benchmark готов.")
    print(f"Среден резултат: {summary['average_percentage']}")
    print(f"Записано в: {BENCHMARK_RESULTS_FILE}")


def handle_command(command: str, memory: Dict[str, Any]) -> bool:
    if command == "/help":
        print_help()
        return True

    if command == "/memory":
        print_memory(memory)
        return True

    if command.startswith("/add_goal "):
        add_profile_item(memory, "goals", command.replace("/add_goal ", "", 1))
        return True

    if command.startswith("/add_pattern "):
        add_profile_item(memory, "bad_patterns", command.replace("/add_pattern ", "", 1))
        return True

    if command.startswith("/add_commitment "):
        add_profile_item(memory, "commitments", command.replace("/add_commitment ", "", 1))
        return True

    if command == "/benchmark":
        run_benchmark(memory)
        return True

    return False


def chat() -> None:
    print("🔥 FocusAI стартира")
    print("Напиши /help за команди или 'exit' за край.\n")

    memory = load_memory()

    while True:
        user_input = input("Ти: ").strip()

        if not user_input:
            continue

        if user_input.lower() in ["exit", "quit", "край"]:
            print("FocusAI: Добре. Но утре пак имаш работа.")
            break

        if user_input.startswith("/"):
            handled = handle_command(user_input, memory)
            if not handled:
                print("Непозната команда. Напиши /help.")
            continue

        messages = build_messages(memory, user_input)
        result = ask_ai(messages)

        reply = clean_model_output(result["content"])
        reply = enforce_informal(reply)

        quality = basic_quality_check(reply)
        if not quality["passed"]:
            print(f"⚠️ Quality warning: {quality['issues']}")

        print(f"\nFocusAI: {reply}\n")

        update_memory_from_turn(memory, user_input, reply, result)
        save_memory(memory)


if __name__ == "__main__":
    chat()