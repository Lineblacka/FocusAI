import json
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

from main import client, MODELS, SYSTEM_PROMPT


TASKS = [
    {
        "id": "bg_discipline_001",
        "input": "Нямам мотивация днес. Мисля да го оставя за утре."
    },
    {
        "id": "bg_failure_001",
        "input": "Пак пропуснах тренировката. Явно просто нямам дисциплина."
    },
    {
        "id": "bg_plan_001",
        "input": "Искам да започна да ставам в 6 сутринта всеки ден. Направи ми план."
    },
    {
        "id": "bg_idea_001",
        "input": "Имам идея за AI коуч, който помага на хората да са по-дисциплинирани."
    },
    {
        "id": "bg_natural_001",
        "input": "Говори ми директно, но не като преведен английски текст."
    }
]


EVALUATOR_PROMPT = """
Ти си строг оценител на български език.

Оцени отговора на AI модела по тези критерии от 1 до 5:

1. Bulgarian fluency:
- естествен български
- правилен словоред
- без машинен/преводен стил

2. Tone fit:
- директен
- строг
- без обиди
- без клишета

3. Actionability:
- дава конкретно действие
- не остава само мотивация

4. Brevity:
- кратък и стегнат
- без излишни обяснения

5. Product fit:
- звучи като FocusAI
- държи потребителя accountable

Върни само JSON:
{
  "bulgarian_fluency": 1-5,
  "tone_fit": 1-5,
  "actionability": 1-5,
  "brevity": 1-5,
  "product_fit": 1-5,
  "total": 1-25,
  "notes": "кратка причина"
}
"""


def call_model(model, task):
    started = time.time()

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": task["input"]}
            ],
            temperature=0.4,
            timeout=90,
        )

        elapsed = round(time.time() - started, 2)
        text = response.choices[0].message.content or ""

        return {
            "model": model,
            "task_id": task["id"],
            "input": task["input"],
            "response": text,
            "response_time_seconds": elapsed,
            "success": True,
            "error": None,
        }

    except Exception as e:
        elapsed = round(time.time() - started, 2)

        return {
            "model": model,
            "task_id": task["id"],
            "input": task["input"],
            "response": None,
            "response_time_seconds": elapsed,
            "success": False,
            "error": str(e),
        }


def evaluate_response(model_response):
    if not model_response["success"]:
        return {
            "total": 0,
            "notes": "Model failed."
        }

    evaluation_input = f"""
Потребителски вход:
{model_response["input"]}

Отговор на модела:
{model_response["response"]}
"""

    try:
        response = client.chat.completions.create(
            model="openai/gpt-oss-20b:free",
            messages=[
                {"role": "system", "content": EVALUATOR_PROMPT},
                {"role": "user", "content": evaluation_input}
            ],
            temperature=0,
            timeout=90,
        )

        raw = response.choices[0].message.content.strip()
        return json.loads(raw)

    except Exception as e:
        return {
            "total": 0,
            "notes": f"Evaluation failed: {e}"
        }


def run_bulgarian_benchmark():
    all_outputs = []

    for task in TASKS:
        print(f"\nTASK: {task['id']}")

        with ThreadPoolExecutor(max_workers=len(MODELS)) as executor:
            futures = [
                executor.submit(call_model, model, task)
                for model in MODELS
            ]

            for future in as_completed(futures):
                result = future.result()
                print(
                    f"{'OK' if result['success'] else 'FAIL'} | "
                    f"{result['model']} | "
                    f"{result['response_time_seconds']}s"
                )
                all_outputs.append(result)

    print("\nEvaluating Bulgarian quality...")

    evaluated = []

    for item in all_outputs:
        score = evaluate_response(item)
        item["evaluation"] = score
        evaluated.append(item)

    model_summary = {}

    for item in evaluated:
        model = item["model"]

        if model not in model_summary:
            model_summary[model] = {
                "model": model,
                "scores": [],
                "times": [],
                "failures": 0,
            }

        if item["success"]:
            model_summary[model]["scores"].append(item["evaluation"].get("total", 0))
            model_summary[model]["times"].append(item["response_time_seconds"])
        else:
            model_summary[model]["failures"] += 1

    ranking = []

    for model, data in model_summary.items():
        scores = data["scores"]
        times = data["times"]

        avg_score = round(sum(scores) / len(scores), 2) if scores else 0
        avg_time = round(sum(times) / len(times), 2) if times else None

        ranking.append({
            "model": model,
            "average_bulgarian_score": avg_score,
            "average_response_time_seconds": avg_time,
            "failures": data["failures"],
        })

    ranking.sort(
        key=lambda x: (
            x["average_bulgarian_score"],
            -x["failures"],
            -(x["average_response_time_seconds"] or 9999)
        ),
        reverse=True
    )

    output = {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "tasks": TASKS,
        "ranking": ranking,
        "raw_results": evaluated,
    }

    with open("bulgarian_model_benchmark.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print("\nRANKING:")
    for i, item in enumerate(ranking, start=1):
        print(
            f"{i}. {item['model']} | "
            f"BG score: {item['average_bulgarian_score']}/25 | "
            f"Time: {item['average_response_time_seconds']}s | "
            f"Failures: {item['failures']}"
        )

    print("\nSaved to bulgarian_model_benchmark.json")


if __name__ == "__main__":
    run_bulgarian_benchmark()