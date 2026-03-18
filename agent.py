#!/usr/bin/env python3
import os
import sys
import json
from openai import OpenAI
from dotenv import load_dotenv

# ========== НАСТРОЙКИ ==========
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))

# ========== ИНСТРУМЕНТЫ ==========
def list_files(path):
    """Вернуть список файлов в папке"""
    full_path = os.path.join(PROJECT_ROOT, path)
    if not full_path.startswith(PROJECT_ROOT):
        return "Ошибка: доступ запрещён"
    try:
        files = os.listdir(full_path)
        return "\n".join(files)
    except FileNotFoundError:
        return f"Ошибка: папка {path} не найдена"

def read_file(path):
    """Прочитать содержимое файла"""
    full_path = os.path.join(PROJECT_ROOT, path)
    if not full_path.startswith(PROJECT_ROOT):
        return "Ошибка: доступ запрещён"
    try:
        with open(full_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return f"Ошибка: файл {path} не найден"

# ========== СХЕМЫ ИНСТРУМЕНТОВ ДЛЯ QWEN ==========
tools = [
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "Показать список файлов в папке wiki. Используй это, чтобы узнать, какие файлы есть в документации.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Путь к папке (например, 'wiki')"
                    }
                },
                "required": ["path"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Прочитать содержимое файла из wiki. Используй после того, как узнал имя файла через list_files.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Путь к файлу (например, 'wiki/git-workflow.md')"
                    }
                },
                "required": ["path"]
            }
        }
    }
]

# ========== ОСНОВНАЯ ФУНКЦИЯ ==========
def main():
    if len(sys.argv) < 2:
        print("❌ Использование: python agent.py 'вопрос'")
        sys.exit(1)

    question = sys.argv[1]

    # Загружаем настройки
    load_dotenv(".env.agent.secret")
    api_key = os.getenv("LLM_API_KEY")
    api_base = os.getenv("LLM_API_BASE")
    model = os.getenv("LLM_MODEL")

    if not all([api_key, api_base, model]):
        print("❌ Нет конфига", file=sys.stderr)
        sys.exit(1)

    client = OpenAI(api_key=api_key, base_url=api_base)

    # История сообщений
    messages = [
        {
            "role": "system",
            "content": (
                "Ты — документационный агент. Используй list_files, чтобы узнать, "
                "какие файлы есть в папке wiki/, а read_file — чтобы читать их. "
                "После того как нашёл ответ, укажи source в формате wiki/файл.md#секция."
            )
        },
        {"role": "user", "content": question}
    ]

    tool_calls_log = []
    MAX_ITER = 10

    for _ in range(MAX_ITER):
        response = client.chat.completions.create(
            model=model,
            messages=messages,
            tools=tools,
            tool_choice="auto"
        )

        msg = response.choices[0].message

        # Если нет вызова инструментов — это ответ
        if not msg.tool_calls:
            answer = msg.content or ""
            # Пытаемся найти source в ответе
            source = "wiki/..."
            for line in answer.split('\n'):
                if 'wiki/' in line and '.md' in line:
                    parts = line.split('wiki/')
                    if len(parts) > 1:
                        source = 'wiki/' + parts[1].split()[0]
            break

        # Есть вызовы инструментов
        for tool_call in msg.tool_calls:
            func_name = tool_call.function.name
            args = json.loads(tool_call.function.arguments)

            if func_name == "list_files":
                result = list_files(args["path"])
            elif func_name == "read_file":
                result = read_file(args["path"])
            else:
                result = "Неизвестный инструмент"

            tool_calls_log.append({
                "tool": func_name,
                "args": args,
                "result": result
            })

            # Добавляем результат обратно в историю
            messages.append(msg)
            messages.append({
                "role": "tool",
                "tool_call_id": tool_call.id,
                "content": result
            })
    else:
        answer = "Достигнут лимит шагов"
        source = ""

    # Вывод
    output = {
        "answer": answer,
        "source": source,
        "tool_calls": tool_calls_log
    }
    print(json.dumps(output, ensure_ascii=False))

if __name__ == "__main__":
    main()
