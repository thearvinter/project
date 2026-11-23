# Веб-интерфейс приложения. Запуск: streamlit run app.py

import plotly.express as px  # библиотека для красивых графиков
import streamlit as st  # библиотека для веб-интерфейса

import analyzer  # наш модуль с логикой анализа

st.set_page_config(page_title="Анализ расходов", page_icon="💸", layout="wide")  # заголовок вкладки
st.title("💸 Анализ личных расходов")  # большой заголовок на странице

st.sidebar.header("Выписка")  # заголовок боковой панели
uploaded = st.sidebar.file_uploader("Загрузите CSV или XLSX", type=["csv", "xlsx"])  # кнопка загрузки
st.sidebar.caption("Нужны колонки: дата, описание, сумма. Расходы — с минусом.")  # подсказка

if uploaded is None:  # если файл не загружен
    st.info("Файл не выбран, показываю демо-выписку")  # сообщаем об этом
    file = open("data/sample.csv", "rb")  # и открываем демо-файл из папки data
    filename = "sample.csv"  # запоминаем его имя
else:  # если пользователь загрузил файл
    file = uploaded  # работаем с ним
    filename = uploaded.name  # и запоминаем его имя

try:  # пробуем прочитать выписку
    df = analyzer.read_statement(file, filename)  # читаем и чистим таблицу
except ValueError as error:  # если в файле что-то не так
    st.error(f"Не получилось прочитать выписку: {error}")  # показываем понятную ошибку
    st.stop()  # и дальше ничего не делаем

df = analyzer.add_categories(df)  # добавляем категории к каждой операции

start = df["date"].min().date()  # первая дата в выписке
end = df["date"].max().date()  # последняя дата в выписке
period = st.sidebar.date_input("Период", value=(start, end))  # выбор периода в боковой панели
if len(period) == 2:  # если выбраны обе даты
    df = df[(df["date"].dt.date >= period[0]) & (df["date"].dt.date <= period[1])]  # фильтруем

if df.empty:  # если за выбранный период операций нет
    st.warning("За этот период нет операций")  # предупреждаем
    st.stop()  # и останавливаемся

summary = analyzer.get_summary(df)  # считаем главные цифры
col1, col2, col3, col4 = st.columns(4)  # делим строку на четыре колонки
col1.metric("Доходы", f"{summary['income']:,.0f} ₽".replace(",", " "))  # доходы
col2.metric("Расходы", f"{summary['expenses']:,.0f} ₽".replace(",", " "))  # расходы
col3.metric("Баланс", f"{summary['balance']:,.0f} ₽".replace(",", " "))  # баланс
col4.metric("В среднем в день", f"{summary['per_day']:,.0f} ₽".replace(",", " "))  # в день

tab1, tab2, tab3 = st.tabs(["Обзор", "Крупные траты", "Все операции"])  # три вкладки

with tab1:  # первая вкладка — графики
    left, right = st.columns(2)  # две колонки для двух графиков
    categories = analyzer.expenses_by_category(df)  # траты по категориям
    pie = px.pie(categories, names="category", values="amount", hole=0.4)  # круговая диаграмма
    left.subheader("Куда уходят деньги")  # подпись над диаграммой
    left.plotly_chart(pie)  # рисуем диаграмму
    months = analyzer.by_month(df)  # доходы и расходы по месяцам
    bars = px.bar(months, x="month", y=["income", "expenses"], barmode="group")  # столбцы
    right.subheader("Доходы и расходы по месяцам")  # подпись над графиком
    right.plotly_chart(bars)  # рисуем столбцы
    st.dataframe(categories, hide_index=True)  # таблица с суммами по категориям

with tab2:  # вторая вкладка — необычно крупные траты
    st.caption("Трата больше Q3 + 3·(Q3 − Q1) своей категории и не меньше 3 000 ₽")  # правило
    big = analyzer.find_big_spendings(df)  # ищем крупные траты
    if big.empty:  # если не нашли
        st.success("Необычно крупных трат нет")  # радуемся
    else:  # если нашли
        st.dataframe(big, hide_index=True)  # показываем таблицу

with tab3:  # третья вкладка — все операции
    search = st.text_input("Поиск по описанию")  # строка поиска
    shown = df[df["description"].str.contains(search, case=False, regex=False)] if search else df  # фильтр
    st.dataframe(shown, hide_index=True)  # показываем операции
    csv = shown.to_csv(index=False).encode("utf-8-sig")  # готовим CSV для скачивания
    st.download_button("Скачать CSV", csv, "operations.csv")  # кнопка скачивания
