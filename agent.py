#!/usr/bin/env python3
import os
import sys
import json
import requests
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

def query_api(method, path, body=None):
    """Отправить запрос к бэкенду"""
    load_dotenv(".env.docker.secret")
    api_key = os.getenv("LMS_API_KEY")
    base_url = os.getenv("AGENT_API_BASE_URL", "http://localhost:42002")
    
    if not api_key:
        return "Ошибка: LMS_API_KEY не найден"
    
    url = f"{base_url}{path}"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    
    try:
        if method.upper() == "GET":
            response = requests.get(url, headers=headers)
        elif method.upper() == "POST":
            data = json.loads(body) if body else {}
            response = requests.post(url, headers=headers, json=data)
        else:
            return f"Метод {method} не поддерживается"
        
        return json.dumps({
            "status_code": response.status_code,
            "body": response.text
        })
    except Exception as e:
        return f"Ошибка запроса: {str(e)}"

# ========== СХЕМЫ ИНСТРУМЕНТОВ ==========
tools = [
    {
        "type": "function",
        "function": {
            "name": "list_files",
            "description": "Показать список файлов в папке wiki. Используй чтобы узнать, какие файлы есть в документации.",
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
            "description": "Прочитать содержимое файла из wiki. Используй после list_files.",
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
    },
    {
        "type": "function",
        "function": {
            "name": "query_api",
            "description": "Отправить запрос к бэкенду. Используй для вопросов о данных (сколько предметов, статус коды, информация о пользователях).",
            "parameters": {
                "type": "object",
                "properties": {
                    "method": {
                        "type": "string",
                        "enum": ["GET", "POST"],
                        "description": "HTTP метод"
                    },
                    "path": {
                        "type": "string",
                        "description": "Путь к эндпоинту (например, '/items/')"
                    },
                    "body": {
                        "type": "string",
                        "description": "Тело запроса в JSON (только для POST)"
                    }
                },
                "required": ["method", "path"]
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

    # Загружаем настройки LLM
    load_dotenv(".env.agent.secret")
    api_key = os.getenv("LLM_API_KEY")
    api_base = os.getenv("LLM_API_BASE")
    model = os.getenv("LLM_MODEL")

    if not all([api_key, api_base, model]):
        print("❌ Нет конфига LLM", file=sys.stderr)
        sys.exit(1)

    client = OpenAI(api_key=api_key, base_url=api_base)

    # Системный промпт
    system_prompt = (
        "Ты — системный агент. У тебя есть три типа инструментов:\n"
        "1. list_files, read_file — для поиска информации в wiki/ (вопросы по документации)\n"
        "2. query_api — для получения данных из бэкенда (сколько предметов, статус, информация)\n\n"
        "Правила выбора инструмента:\n"
        "- Если вопрос про документацию (как что-то сделать) — используй wiki\n"
        "- Если вопрос про данные (сколько, какой статус) — используй query_api\n"
        "- Если вопрос про код (как реализована функция) — используй read_file для .py файлов\n\n"
        "После получения ответа, укажи source для wiki-вопросов."
    )

    messages = [
        {"role": "system", "content": system_prompt},
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
            # Пытаемся найти source
            source = ""
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
            elif func_name == "query_api":
                result = query_api(
                    method=args.get("method"),
                    path=args.get("path"),
                    body=args.get("body")
                )
            else:
                result = "Неизвестный инструмент"

            tool_calls_log.append({
                "tool": func_name,
                "args": args,
                "result": result
            })

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
