import subprocess
import json
import sys

def run_agent(question):
    result = subprocess.run(
        [sys.executable, "agent.py", question],
        capture_output=True,
        text=True
    )
    assert result.returncode == 0, f"Ошибка: {result.stderr}"
    return json.loads(result.stdout)

def test_merge_conflict():
    """Тест на вопрос про merge conflict"""
    data = run_agent("How do you resolve a merge conflict?")
    assert "source" in data, "Нет поля source"
    # Проверяем, что был вызов read_file
    tools = [t["tool"] for t in data["tool_calls"]]
    assert "read_file" in tools, "Не вызван read_file"
    print("✅ test_merge_conflict пройден")

def test_list_wiki():
    """Тест на вопрос про список файлов"""
    data = run_agent("What files are in the wiki?")
    tools = [t["tool"] for t in data["tool_calls"]]
    assert "list_files" in tools, "Не вызван list_files"
    print("✅ test_list_wiki пройден")

def test_basic():
    """Базовый тест из Task 1"""
    data = run_agent("What is 2+2?")
    assert "answer" in data, "Нет поля answer"
    assert "tool_calls" in data, "Нет поля tool_calls"
    print("✅ test_basic пройден")

if __name__ == "__main__":
    test_basic()
    test_list_wiki()
    test_merge_conflict()
    print("\n🎉 Все тесты прошли успешно!")
def test_framework_question():
    """Тест на вопрос про фреймворк (должен читать файлы)"""
    data = run_agent("What Python web framework does this project use?")
    tools = [t["tool"] for t in data["tool_calls"]]
    assert "read_file" in tools, "Должен быть вызван read_file"
    print("✅ test_framework_question пройден")

def test_items_count():
    """Тест на вопрос про количество предметов (должен вызывать API)"""
    data = run_agent("How many items are in the database?")
    tools = [t["tool"] for t in data["tool_calls"]]
    assert "query_api" in tools, "Должен быть вызван query_api"
    print("✅ test_items_count пройден")
