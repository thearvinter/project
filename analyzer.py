# Модуль с логикой анализа расходов: чтение выписки, категории, итоги, крупные траты

import io  # нужен, чтобы читать текст из памяти как из файла

import pandas as pd  # библиотека для работы с таблицами

# Словарь категорий: название категории -> слова, по которым её узнаём в описании операции
CATEGORIES = {
    "Продукты": ["пятёрочка", "перекрёсток", "магнит", "вкусвилл", "лента", "самокат"],  # магазины
    "Кафе": ["кофе", "кафе", "шоколадница", "вкусно и точка", "kfc"],  # кафе и фастфуд
    "Транспорт": ["метро", "такси", "яндекс go", "аэрофлот", "ржд", "азс"],  # поездки
    "Связь и подписки": ["мтс", "билайн", "мегафон", "яндекс плюс"],  # телефон и подписки
    "ЖКХ": ["жкх", "квартплата", "аренда"],  # жильё
    "Здоровье": ["аптека", "ригла", "клиника", "стоматология"],  # здоровье
    "Покупки": ["wildberries", "ozon", "м.видео", "dns"],  # маркетплейсы и техника
    "Развлечения": ["кино", "театр", "концерт"],  # досуг
    "Образование": ["литрес", "курс", "книжный"],  # учёба и книги
    "Переводы": ["перевод", "сбп"],  # переводы людям
}

# Как могут называться колонки в выписках разных банков -> как называем их мы
COLUMN_NAMES = {
    "дата": "date",  # короткое русское название даты
    "дата операции": "date",  # так пишет большинство банков
    "описание": "description",  # описание операции
    "назначение платежа": "description",  # другой вариант описания
    "сумма": "amount",  # короткое название суммы
    "сумма операции": "amount",  # полное название суммы
}


def to_number(value):
    """Превращает сумму из выписки в число, например '-1 234,56 ₽' -> -1234.56."""
    text = str(value)  # переводим значение в строку, даже если это уже число
    text = text.replace(" ", "")  # убираем обычные пробелы между разрядами
    text = text.replace("\xa0", "")  # убираем неразрывные пробелы, их любят банки
    text = text.replace("₽", "")  # убираем знак рубля
    text = text.replace("−", "-")  # заменяем длинный минус на обычный
    text = text.replace(",", ".")  # десятичную запятую меняем на точку
    try:  # пробуем превратить строку в число
        return float(text)  # если получилось, возвращаем число
    except ValueError:  # если в строке не число
        return None  # возвращаем пустое значение, такую строку потом выкинем


def read_statement(file, filename):
    """Читает выписку из CSV или Excel и возвращает таблицу с колонками date, description, amount."""
    if filename.endswith(".xlsx"):  # если это файл Excel
        df = pd.read_excel(file)  # читаем его сразу через pandas
    else:  # иначе считаем, что это CSV
        raw = file.read()  # читаем файл как набор байтов
        try:  # сначала пробуем самую частую кодировку
            text = raw.decode("utf-8-sig")  # убирает невидимый символ в начале
        except UnicodeDecodeError:  # если не получилось
            text = raw.decode("cp1251")  # пробуем старую кодировку Windows, её используют банки
        df = pd.read_csv(io.StringIO(text), sep=None, engine="python")  # pandas сам найдёт ; или ,

    df.columns = [str(c).strip().lower() for c in df.columns]  # приводим названия колонок к виду "дата"
    df = df.rename(columns=COLUMN_NAMES)  # переименовываем русские названия в наши
    for column in ["date", "description", "amount"]:  # проверяем каждую нужную колонку
        if column not in df.columns:  # если её нет в файле
            raise ValueError(f"В выписке нет колонки: {column}")  # сообщаем об ошибке

    df = df[["date", "description", "amount"]].copy()  # оставляем только нужные колонки
    df["date"] = pd.to_datetime(  # превращаем текст в дату
        df["date"], dayfirst=True, errors="coerce", format="mixed"  # день идёт первым, ошибки -> пусто
    )  # формат "mixed" понимает и 05.10.2026, и 2026-10-05
    df["amount"] = df["amount"].apply(to_number)  # текст -> число
    df["description"] = df["description"].astype(str).str.strip()  # описание -> строка без пробелов
    df = df.dropna(subset=["date", "amount"])  # выкидываем строки без даты или суммы
    df = df[df["amount"] != 0]  # выкидываем нулевые операции
    if df.empty:  # если после чистки ничего не осталось
        raise ValueError("В выписке нет ни одной правильной операции")  # сообщаем об ошибке
    return df.sort_values("date").reset_index(drop=True)  # сортируем по дате и отдаём


def get_category(description, amount):
    """Определяет категорию одной операции по её описанию."""
    if amount > 0:  # любая положительная сумма — это поступление денег
        return "Доходы"  # значит категория «Доходы»
    text = description.lower()  # переводим описание в маленькие буквы для сравнения
    for category, words in CATEGORIES.items():  # перебираем все категории по очереди
        for word in words:  # перебираем слова этой категории
            if word in text:  # если слово встречается в описании
                return category  # нашли категорию
    return "Прочее"  # если ничего не подошло


def add_categories(df):
    """Добавляет в таблицу колонку category."""
    df = df.copy()  # делаем копию, чтобы не менять исходную таблицу
    df["category"] = df.apply(  # для каждой строки таблицы
        lambda row: get_category(row["description"], row["amount"]), axis=1  # считаем категорию
    )  # и записываем результат в новую колонку
    return df  # возвращаем таблицу с категориями


def get_summary(df):
    """Считает главные цифры: доходы, расходы, баланс и средний расход в день."""
    income = float(df[df["amount"] > 0]["amount"].sum())  # сумма всех поступлений
    expenses = float(-df[df["amount"] < 0]["amount"].sum())  # сумма всех трат со знаком плюс
    days = (df["date"].max() - df["date"].min()).days + 1  # сколько дней в выписке
    return {  # возвращаем словарь с результатами
        "income": round(income, 2),  # доходы, округленные до копеек
        "expenses": round(expenses, 2),  # расходы
        "balance": round(income - expenses, 2),  # что осталось
        "per_day": round(expenses / days, 2),  # средний расход в день
    }


def expenses_by_category(df):
    """Считает, сколько потрачено в каждой категории."""
    spent = df[df["amount"] < 0].copy()  # берем только траты
    spent["amount"] = -spent["amount"]  # делаем суммы положительными
    result = spent.groupby("category")["amount"].sum().reset_index()  # складываем по категориям
    result["share"] = (result["amount"] / result["amount"].sum() * 100).round(1)  # доля в %
    return result.sort_values("amount", ascending=False).reset_index(drop=True)  # от больших к малым


def by_month(df):
    """Считает доходы и расходы по каждому месяцу."""
    df = df.copy()  # копия, чтобы не портить исходную таблицу
    df["month"] = df["date"].dt.strftime("%Y-%m")  # месяц в виде "2026-05"
    df["income"] = df["amount"].where(df["amount"] > 0, 0)  # доходы, остальное заменяем нулём
    df["expenses"] = -df["amount"].where(df["amount"] < 0, 0)  # расходы, тоже положительные
    return df.groupby("month")[["income", "expenses"]].sum().reset_index()  # суммы по месяцам


def find_big_spendings(df, min_amount=3000):
    """Ищет необычно крупные траты внутри каждой категории.

    Правило: трата необычная, если она больше Q3 + 3 * (Q3 - Q1) своей категории
    и при этом не меньше min_amount рублей. Q1 и Q3 — это квартили (25% и 75% трат).
    """
    spent = df[df["amount"] < 0].copy()  # берем только траты
    spent["amount"] = -spent["amount"]  # делаем суммы положительными
    found = []  # сюда будем складывать найденные траты
    for category, group in spent.groupby("category"):  # перебираем категории
        if len(group) < 4:  # если трат в категории меньше четырёх
            continue  # то не понять, что для неё обычно, пропускаем
        q1 = group["amount"].quantile(0.25)  # четверть трат меньше этого значения
        q3 = group["amount"].quantile(0.75)  # три четверти трат меньше этого значения
        limit = q3 + 3 * (q3 - q1)  # граница, выше которой трата необычная
        big = group[(group["amount"] > limit) & (group["amount"] >= min_amount)]  # отбираем
        found.append(big)  # добавляем найденное в общий список
    if not found:  # если ни одной подходящей категории не было
        return spent.head(0)  # возвращаем пустую таблицу
    result = pd.concat(found)  # склеиваем найденное в одну таблицу
    return result.sort_values("amount", ascending=False).reset_index(drop=True)  # крупные сверху
