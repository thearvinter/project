# Тесты для analyzer.py. Запуск: pytest

import io  # чтобы подсовывать функциям «файлы» прямо из памяти
import sys  # чтобы добавить папку проекта в путь поиска модулей
from pathlib import Path  # удобная работа с путями

import pandas as pd  # таблицы
import pytest  # библиотека для тестов

ROOT = Path(__file__).parent.parent  # папка проекта (на уровень выше папки tests)
sys.path.insert(0, str(ROOT))  # теперь можно импортировать analyzer
import analyzer  # noqa: E402 — наш модуль, импорт после настройки пути


def make_table():
    """Маленькая выписка, итоги по которой посчитаны вручную."""
    return pd.DataFrame(  # создаём таблицу
        {
            "date": pd.to_datetime(["2026-01-05", "2026-01-06", "2026-01-10", "2026-02-01"]),  # даты
            "description": ["Зарплата", "Пятёрочка", "Метро", "Пятёрочка"],  # описания
            "amount": [50000, -1000, -70, -2000],  # суммы: доход и три траты
            "category": ["Доходы", "Продукты", "Транспорт", "Продукты"],  # категории
        }
    )


@pytest.mark.parametrize(  # один тест, много вариантов входных данных
    "text, expected",  # что подаём и что ждём
    [
        ("-1 234,56", -1234.56),  # пробел между разрядами и запятая
        ("-1\xa0234,56 ₽", -1234.56),  # неразрывный пробел и знак рубля
        ("−300", -300.0),  # длинный минус
        (500, 500.0),  # уже число
    ],
)
def test_to_number(text, expected):
    assert analyzer.to_number(text) == expected  # сумма разобрана правильно


def test_to_number_not_a_number():
    assert analyzer.to_number("нет суммы") is None  # мусор превращается в None


def test_read_csv_with_russian_columns():
    text = "Дата операции;Описание;Сумма операции\n01.02.2026;Магнит;-1 200,00\n"  # как у банка
    df = analyzer.read_statement(io.BytesIO(text.encode("utf-8")), "bank.csv")  # читаем
    assert df.loc[0, "amount"] == -1200  # сумма стала числом
    assert df.loc[0, "date"] == pd.Timestamp("2026-02-01")  # дата прочитана как 1 февраля


def test_read_csv_in_windows_encoding():
    text = "Дата;Описание;Сумма\n01.02.2026;Магнит;-300\n"  # маленькая выписка
    df = analyzer.read_statement(io.BytesIO(text.encode("cp1251")), "bank.csv")  # кодировка Windows
    assert df.loc[0, "description"] == "Магнит"  # русские буквы не сломались


def test_read_excel(tmp_path):
    path = tmp_path / "bank.xlsx"  # временный файл Excel
    table = pd.DataFrame({"Дата": ["01.03.2026"], "Описание": ["Метро"], "Сумма": [-70]})  # данные
    table.to_excel(path, index=False)  # сохраняем в Excel
    df = analyzer.read_statement(path, "bank.xlsx")  # читаем обратно
    assert df.loc[0, "amount"] == -70  # всё прочиталось


def test_missing_column_gives_error():
    text = "Дата;Описание\n01.02.2026;Магнит\n"  # нет колонки с суммой
    with pytest.raises(ValueError):  # ждём ошибку
        analyzer.read_statement(io.BytesIO(text.encode("utf-8")), "bank.csv")  # пробуем прочитать


def test_bad_rows_are_removed():
    text = "Дата;Описание;Сумма\nне дата;А;-1\n05.01.2026;Б;0\n06.01.2026;В;-5\n"  # 2 плохие строки
    df = analyzer.read_statement(io.BytesIO(text.encode("utf-8")), "bank.csv")  # читаем
    assert list(df["description"]) == ["В"]  # осталась только правильная строка


def test_get_category():
    assert analyzer.get_category("Зарплата", 50000) == "Доходы"  # поступление
    assert analyzer.get_category("ПЯТЁРОЧКА 123", -500) == "Продукты"  # регистр не важен
    assert analyzer.get_category("Непонятный магазин", -100) == "Прочее"  # ничего не подошло


def test_summary():
    summary = analyzer.get_summary(make_table())  # считаем итоги
    assert summary["income"] == 50000  # доход
    assert summary["expenses"] == 3070  # 1000 + 70 + 2000
    assert summary["balance"] == 46930  # 50000 - 3070
    assert summary["per_day"] == round(3070 / 28, 2)  # с 5 января по 1 февраля — 28 дней


def test_expenses_by_category():
    result = analyzer.expenses_by_category(make_table())  # траты по категориям
    assert list(result["category"]) == ["Продукты", "Транспорт"]  # от больших к малым
    assert result.loc[0, "amount"] == 3000  # 1000 + 2000
    assert "Доходы" not in list(result["category"])  # доходы сюда не попадают


def test_by_month():
    result = analyzer.by_month(make_table()).set_index("month")  # итоги по месяцам
    assert result.loc["2026-01", "income"] == 50000  # доход в январе
    assert result.loc["2026-02", "expenses"] == 2000  # расход в феврале


def test_find_big_spendings():
    amounts = [-500, -600, -550, -700, -650, -40000]  # обычные траты и одна огромная
    df = pd.DataFrame(  # таблица из одной категории
        {
            "date": pd.date_range("2026-01-01", periods=6),  # шесть дней подряд
            "description": ["Магазин"] * 6,  # одинаковое описание
            "amount": amounts,  # суммы
            "category": ["Продукты"] * 6,  # одна категория
        }
    )
    big = analyzer.find_big_spendings(df)  # ищем крупные траты
    assert list(big["amount"]) == [40000]  # нашлась только огромная трата


def test_demo_file_works():
    with open(ROOT / "data" / "sample.csv", "rb") as file:  # открываем демо-выписку
        df = analyzer.read_statement(file, "sample.csv")  # читаем её
    assert len(df) > 300  # в ней больше 300 операций
    assert len(analyzer.find_big_spendings(analyzer.add_categories(df))) == 4  # 4 крупные покупки
