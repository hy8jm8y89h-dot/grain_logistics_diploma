import requests
import xml.etree.ElementTree as ET
from bs4 import BeautifulSoup
from urllib.parse import urlencode, quote_plus
from datetime import datetime


def get_cbr_usd_rate() -> dict:
    """
    Получает актуальный курс доллара США по данным Банка России.
    """
    url = "https://www.cbr.ru/scripts/XML_daily.asp"

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()

        root = ET.fromstring(response.content)
        date = root.attrib.get("Date", "")

        for currency in root.findall("Valute"):
            char_code = currency.find("CharCode").text

            if char_code == "USD":
                value_text = currency.find("Value").text
                nominal_text = currency.find("Nominal").text

                value = float(value_text.replace(",", "."))
                nominal = float(nominal_text.replace(",", "."))

                return {
                    "rate": round(value / nominal, 2),
                    "date": date,
                    "source": "Банк России",
                    "is_actual": True
                }

    except Exception as error:
        return {
            "rate": 90.0,
            "date": datetime.now().strftime("%d.%m.%Y"),
            "source": f"Резервное значение, ошибка: {error}",
            "is_actual": False
        }

    return {
        "rate": 90.0,
        "date": datetime.now().strftime("%d.%m.%Y"),
        "source": "Резервное значение",
        "is_actual": False
    }


def normalize_gdelt_query(query: str) -> str:
    """
    GDELT требует брать OR-запросы в скобки.
    """
    cleaned_query = query.strip()

    if " OR " in cleaned_query and not cleaned_query.startswith("("):
        cleaned_query = f"({cleaned_query})"

    return cleaned_query


def get_gdelt_news(query: str, max_records: int = 10) -> list:
    """
    Получает новости через GDELT DOC API.
    """
    base_url = "https://api.gdeltproject.org/api/v2/doc/doc"

    params = {
        "query": normalize_gdelt_query(query),
        "mode": "artlist",
        "format": "json",
        "maxrecords": max_records,
        "sort": "datedesc"
    }

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    try:
        response = requests.get(
            base_url,
            params=params,
            headers=headers,
            timeout=20
        )
        response.raise_for_status()

        data = response.json()
        articles = data.get("articles", [])

        result = []

        for article in articles:
            result.append(
                {
                    "title": article.get("title", "Без заголовка"),
                    "source": article.get("sourceCommonName", "Неизвестный источник"),
                    "url": article.get("url", ""),
                    "date": article.get("seendate", ""),
                    "language": article.get("language", ""),
                    "provider": "GDELT"
                }
            )

        return result

    except Exception:
        return []


def get_google_news_rss(query: str, max_records: int = 10) -> list:
    """
    Резервный источник: Google News RSS.
    """
    encoded_query = quote_plus(query)

    url = (
        "https://news.google.com/rss/search?"
        f"q={encoded_query}&hl=ru&gl=RU&ceid=RU:ru"
    )

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    try:
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()

        root = ET.fromstring(response.content)

        items = root.findall(".//item")

        result = []

        for item in items[:max_records]:
            title = item.findtext("title", default="Без заголовка")
            link = item.findtext("link", default="")
            pub_date = item.findtext("pubDate", default="")
            source = item.findtext("source", default="Google News")

            result.append(
                {
                    "title": title,
                    "source": source,
                    "url": link,
                    "date": pub_date,
                    "language": "ru",
                    "provider": "Google News RSS"
                }
            )

        return result

    except Exception:
        return []


def get_combined_news(query: str, max_records: int = 10) -> list:
    """
    Пытается получить новости из GDELT.
    Если GDELT ничего не дал — берет Google News RSS.
    """
    gdelt_articles = get_gdelt_news(query, max_records=max_records)

    if gdelt_articles:
        return gdelt_articles

    google_articles = get_google_news_rss(query, max_records=max_records)

    return google_articles


def calculate_news_risk_from_articles(articles: list) -> dict:
    """
    Умная оценка новостного риска по тематическим категориям.

    Возвращает:
    - news_risk: общий риск 0-100
    - risk_comment: текстовый комментарий
    - triggered_keywords: найденные ключевые слова
    - category_scores: вклад категорий риска
    """
    if not articles:
        return {
            "news_risk": 30,
            "risk_comment": "Новости не получены, используется нейтральная оценка риска.",
            "triggered_keywords": [],
            "category_scores": {}
        }

    risk_categories = {
        "Санкции и ограничения": {
            "keywords": [
                "санкции", "санкция", "ограничения", "ограничение",
                "запрет", "эмбарго", "санкционный", "sanctions",
                "restriction", "export ban", "ban"
            ],
            "weight": 24
        },
        "Порты и перегрузка": {
            "keywords": [
                "порт", "порты", "перевалка", "перегрузка", "очередь",
                "затор", "простой", "терминал", "портовая инфраструктура",
                "port", "congestion", "terminal", "delay"
            ],
            "weight": 18
        },
        "Фрахт, тарифы и топливо": {
            "keywords": [
                "фрахт", "тариф", "тарифы", "топливо", "дизель",
                "ставка", "логистика", "freight", "tariff", "fuel", "rate"
            ],
            "weight": 16
        },
        "Экспортное регулирование": {
            "keywords": [
                "пошлина", "квота", "экспортная пошлина", "таможня",
                "минсельхоз", "россельхознадзор", "регулирование",
                "quota", "duty", "customs"
            ],
            "weight": 18
        },
        "Погодные и навигационные риски": {
            "keywords": [
                "шторм", "лед", "ледовая", "засуха", "обмеление",
                "паводок", "навигация", "storm", "ice", "drought"
            ],
            "weight": 14
        },
        "Судоходство и флот": {
            "keywords": [
                "судно", "суда", "флот", "сухогруз", "балкер",
                "рейдовая перевалка", "ais", "shipping", "vessel", "fleet", "bulk carrier"
            ],
            "weight": 12
        },
        "Рынок зерна": {
            "keywords": [
                "зерно", "пшеница", "ячмень", "кукуруза", "урожай",
                "экспорт зерна", "grain", "wheat", "barley", "corn"
            ],
            "weight": 6
        }
    }

    combined_text = " ".join(
        article.get("title", "") for article in articles
    ).lower()

    category_scores = {}
    triggered_keywords = []

    base_score = 15

    for category, config in risk_categories.items():
        found_words = []

        for keyword in config["keywords"]:
            if keyword.lower() in combined_text:
                found_words.append(keyword)

        if found_words:
            # Чем больше совпадений внутри категории, тем выше вклад,
            # но не больше веса категории.
            category_score = min(
                config["weight"],
                4 + len(set(found_words)) * 4
            )
            category_scores[category] = category_score
            triggered_keywords.extend(found_words)
        else:
            category_scores[category] = 0

    total_score = base_score + sum(category_scores.values())
    total_score = min(round(total_score, 1), 100)

    active_categories = [
        category for category, score in category_scores.items() if score > 0
    ]

    if total_score < 35:
        level_text = "низкий"
    elif total_score < 65:
        level_text = "умеренный"
    else:
        level_text = "высокий"

    if active_categories:
        risk_comment = (
            f"Новостной риск оценивается как {level_text}. "
            f"Основные факторы: {', '.join(active_categories)}."
        )
    else:
        risk_comment = (
            f"Новостной риск оценивается как {level_text}. "
            "Существенных негативных факторов в заголовках не выявлено."
        )

    return {
        "news_risk": total_score,
        "risk_comment": risk_comment,
        "triggered_keywords": sorted(set(triggered_keywords)),
        "category_scores": category_scores
    }


def generate_news_digest(articles: list, risk_result: dict) -> str:
    """
    Формирует короткую текстовую новостную сводку по реальным заголовкам.
    """
    if not articles:
        return (
            "Тематические новости по запросу не получены. "
            "Для расчета используется нейтральная оценка новостного риска."
        )

    digest = "Основная тематическая сводка:\n\n"

    for number, article in enumerate(articles[:7], start=1):
        title = article.get("title", "Без заголовка")
        source = article.get("source", "Источник не указан")
        provider = article.get("provider", "Источник данных не указан")

        digest += f"{number}. {title} ({source}, {provider}).\n"

    digest += "\n"
    digest += (
        f"Автоматическая оценка новостного риска: "
        f"{risk_result['news_risk']} из 100. "
        f"{risk_result['risk_comment']}"
    )

    return digest
def get_zol_news(max_records: int = 10) -> list:
    """
    Получает новости с сайта Зерно Он-Лайн.
    """
    url = "https://www.zol.ru/"

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    try:
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        result = []
        seen_titles = set()

        for link in soup.find_all("a", href=True):
            title = " ".join(link.get_text(" ", strip=True).split())
            href = link["href"]

            if not title:
                continue

            title_lower = title.lower()
            banned_titles = [
                "зерновой еженедельник",
                "новости рынка зерна",
                "российский рынок",
                "мировой рынок",
                "зерностат",
                "цены",
                "доска объявлений",
                "справочник",
                "форум",
                "карта сайта",
                "реклама",
                "контакты"
            ]

            if any(banned in title_lower for banned in banned_titles):
                continue

            is_relevant = any(
                word in title_lower
                for word in [
                    "зерн", "пшениц", "экспорт", "урожай",
                    "пошлин", "котиров", "минсельхоз", "рынок"
                ]
            )

            if not is_relevant:
                continue

            if len(title) < 35:
                continue

            if title in seen_titles:
                continue

            if href.startswith("/"):
                href = "https://www.zol.ru" + href

            result.append(
                {
                    "title": title,
                    "source": "Зерно Он-Лайн",
                    "url": href,
                    "date": "",
                    "language": "ru",
                    "provider": "ZOL.ru"
                }
            )

            seen_titles.add(title)

            if len(result) >= max_records:
                break

        return result

    except Exception:
        return []


def get_portnews_grain_news(max_records: int = 10) -> list:
    """
    Получает новости PortNews по тематике зерна.
    """
    url = "https://portnews.ru/news/tags/109/"

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    try:
        response = requests.get(url, headers=headers, timeout=20)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        result = []
        seen_titles = set()

        for link in soup.find_all("a", href=True):
            title = " ".join(link.get_text(" ", strip=True).split())
            href = link["href"]

            if not title:
                continue

            title_lower = title.lower()

            is_relevant = any(
                word in title_lower
                for word in [
                    "зерн", "пшениц", "порт", "перевал",
                    "суд", "экспорт", "терминал", "фрахт"
                ]
            )

            if not is_relevant:
                continue

            if len(title) < 20:
                continue

            if title in seen_titles:
                continue

            if href.startswith("/"):
                href = "https://portnews.ru" + href

            result.append(
                {
                    "title": title,
                    "source": "PortNews",
                    "url": href,
                    "date": "",
                    "language": "ru",
                    "provider": "PortNews"
                }
            )

            seen_titles.add(title)

            if len(result) >= max_records:
                break

        return result

    except Exception:
        return []


def get_fallback_digest_news() -> list:
    """
    Резервная демонстрационная сводка.
    Используется только если внешние сайты не отдали новости.
    """
    return [
        {
            "title": "Мониторинг рынка: экспорт зерна зависит от тарифов, курса валют и загрузки портовой инфраструктуры",
            "source": "Резервная аналитическая сводка",
            "url": "",
            "date": datetime.now().strftime("%d.%m.%Y"),
            "language": "ru",
            "provider": "Локальный резерв"
        },
        {
            "title": "Ключевые факторы риска: стоимость топлива, фрахт, ограничения перевалки и очереди в морских портах",
            "source": "Резервная аналитическая сводка",
            "url": "",
            "date": datetime.now().strftime("%d.%m.%Y"),
            "language": "ru",
            "provider": "Локальный резерв"
        },
        {
            "title": "Для устойчивости экспортной логистики рекомендуется сравнивать прямые и мультимодальные маршруты",
            "source": "Резервная аналитическая сводка",
            "url": "",
            "date": datetime.now().strftime("%d.%m.%Y"),
            "language": "ru",
            "provider": "Локальный резерв"
        },
        {
            "title": "Рост перевозок речным транспортом требует оценки загрузки зерновых терминалов и флота",
            "source": "Резервная аналитическая сводка",
            "url": "",
            "date": datetime.now().strftime("%d.%m.%Y"),
            "language": "ru",
            "provider": "Локальный резерв"
        },
        {
            "title": "Сценарный анализ позволяет учитывать изменение железнодорожных, автомобильных и речных тарифов",
            "source": "Резервная аналитическая сводка",
            "url": "",
            "date": datetime.now().strftime("%d.%m.%Y"),
            "language": "ru",
            "provider": "Локальный резерв"
        }
    ]


def get_main_thematic_news(query: str, max_records: int = 10) -> list:
    """
    Основная тематическая сводка:
    1. Зерно Он-Лайн
    2. PortNews
    3. GDELT / Google News
    4. локальный резерв
    """
    articles = []

    articles.extend(get_zol_news(max_records=max_records))
    articles.extend(get_portnews_grain_news(max_records=max_records))

    if len(articles) < max_records:
        external_articles = get_combined_news(query, max_records=max_records)
        articles.extend(external_articles)

    unique_articles = []
    seen_titles = set()

    for article in articles:
        title = article.get("title", "")

        if not title:
            continue

        if title in seen_titles:
            continue

        unique_articles.append(article)
        seen_titles.add(title)

        if len(unique_articles) >= max_records:
            break

    if not unique_articles:
        unique_articles = get_fallback_digest_news()

    return unique_articles
def get_stooq_quote(symbol: str) -> dict:
    """
    Получает котировку с Stooq по тикеру.

    Примеры:
    ZW.F — wheat futures
    CL.F — crude oil futures
    """
    url = "https://stooq.com/q/l/"

    params = {
        "s": symbol.lower(),
        "f": "sd2t2ohlcv",
        "h": "",
        "e": "csv"
    }

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    try:
        response = requests.get(
            url,
            params=params,
            headers=headers,
            timeout=15
        )
        response.raise_for_status()

        lines = response.text.strip().splitlines()

        if len(lines) < 2:
            raise ValueError("Пустой ответ Stooq")

        header = lines[0].split(",")
        values = lines[1].split(",")

        data = dict(zip(header, values))

        close_text = data.get("Close", "N/D")

        if close_text in ["N/D", "", None]:
            raise ValueError("Нет значения Close")

        close = float(close_text)

        return {
            "symbol": symbol,
            "value": close,
            "date": data.get("Date", ""),
            "time": data.get("Time", ""),
            "source": "Stooq",
            "is_actual": True
        }

    except Exception as error:
        return {
            "symbol": symbol,
            "value": None,
            "date": "",
            "time": "",
            "source": f"Резервное значение, ошибка: {error}",
            "is_actual": False
        }


def convert_wheat_cents_bushel_to_usd_t(value_cents_per_bushel: float) -> float:
    """
    Переводит котировку пшеницы CBOT из центов за бушель в долл./т.

    1 бушель пшеницы ≈ 27.2155 кг.
    """
    usd_per_bushel = value_cents_per_bushel / 100
    usd_per_ton = usd_per_bushel / 0.0272155

    return round(usd_per_ton, 2)


def get_auto_market_indicators() -> dict:
    """
    Получает автоматические рыночные индикаторы:
    - мировая цена пшеницы;
    - цена нефти как прокси для стоимости топлива;
    - расчетное изменение топлива относительно базового уровня.
    """
    wheat_quote = get_stooq_quote("ZW.F")
    oil_quote = get_stooq_quote("CL.F")

    # Резервные значения, если источник не ответил
    wheat_price_usd_t = 230.0
    oil_price_usd_bbl = 80.0

    wheat_source = wheat_quote["source"]
    oil_source = oil_quote["source"]

    if wheat_quote["value"] is not None:
        wheat_price_usd_t = convert_wheat_cents_bushel_to_usd_t(
            wheat_quote["value"]
        )

    if oil_quote["value"] is not None:
        oil_price_usd_bbl = float(oil_quote["value"])

    # Базовый уровень нефти для сценария — 80 долл./барр.
    # Если нефть выше базы, считаем, что давление на топливо растет.
    fuel_change = ((oil_price_usd_bbl - 80) / 80 * 100)
    fuel_change = round(max(min(fuel_change, 80), -30), 1)

    return {
        "wheat_price_usd_t": wheat_price_usd_t,
        "wheat_source": wheat_source,
        "wheat_date": wheat_quote.get("date", ""),
        "oil_price_usd_bbl": round(oil_price_usd_bbl, 2),
        "oil_source": oil_source,
        "oil_date": oil_quote.get("date", ""),
        "fuel_change_percent": fuel_change
    }
def get_stooq_quote(symbol: str) -> dict:
    """
    Получает котировку с Stooq по тикеру.

    Примеры:
    ZW.F — wheat futures
    CL.F — crude oil futures
    """
    url = "https://stooq.com/q/l/"

    params = {
        "s": symbol.lower(),
        "f": "sd2t2ohlcv",
        "h": "",
        "e": "csv"
    }

    headers = {
        "User-Agent": "Mozilla/5.0"
    }

    try:
        response = requests.get(
            url,
            params=params,
            headers=headers,
            timeout=15
        )
        response.raise_for_status()

        lines = response.text.strip().splitlines()

        if len(lines) < 2:
            raise ValueError("Пустой ответ Stooq")

        header = lines[0].split(",")
        values = lines[1].split(",")

        data = dict(zip(header, values))

        close_text = data.get("Close", "N/D")

        if close_text in ["N/D", "", None]:
            raise ValueError("Нет значения Close")

        close = float(close_text)

        return {
            "symbol": symbol,
            "value": close,
            "date": data.get("Date", ""),
            "time": data.get("Time", ""),
            "source": "Stooq",
            "is_actual": True
        }

    except Exception as error:
        return {
            "symbol": symbol,
            "value": None,
            "date": "",
            "time": "",
            "source": f"Резервное значение, ошибка: {error}",
            "is_actual": False
        }


def convert_wheat_cents_bushel_to_usd_t(value_cents_per_bushel: float) -> float:
    """
    Переводит котировку пшеницы из центов за бушель в долл./т.
    """
    usd_per_bushel = value_cents_per_bushel / 100
    usd_per_ton = usd_per_bushel / 0.0272155

    return round(usd_per_ton, 2)


def get_auto_market_indicators() -> dict:
    """
    Получает автоматические рыночные индикаторы:
    - мировая цена пшеницы;
    - цена нефти как прокси стоимости топлива;
    - расчетное изменение топлива.
    """
    wheat_quote = get_stooq_quote("ZW.F")
    oil_quote = get_stooq_quote("CL.F")

    wheat_price_usd_t = 230.0
    oil_price_usd_bbl = 80.0

    wheat_source = wheat_quote["source"]
    oil_source = oil_quote["source"]

    if wheat_quote["value"] is not None:
        wheat_price_usd_t = convert_wheat_cents_bushel_to_usd_t(
            wheat_quote["value"]
        )

    if oil_quote["value"] is not None:
        oil_price_usd_bbl = float(oil_quote["value"])

    fuel_change = ((oil_price_usd_bbl - 80) / 80 * 100)
    fuel_change = round(max(min(fuel_change, 80), -30), 1)

    return {
        "wheat_price_usd_t": wheat_price_usd_t,
        "wheat_source": wheat_source,
        "wheat_date": wheat_quote.get("date", ""),
        "oil_price_usd_bbl": round(oil_price_usd_bbl, 2),
        "oil_source": oil_source,
        "oil_date": oil_quote.get("date", ""),
        "fuel_change_percent": fuel_change
    }
def get_auto_market_indicators() -> dict:
    """
    Получает автоматические рыночные индикаторы.
    Если внешний источник недоступен, возвращает резервные значения.
    """

    wheat_price_usd_t = 230.0
    oil_price_usd_bbl = 80.0

    fuel_change = ((oil_price_usd_bbl - 80) / 80 * 100)
    fuel_change = round(max(min(fuel_change, 80), -30), 1)

    return {
        "wheat_price_usd_t": wheat_price_usd_t,
        "wheat_source": "Резервное значение",
        "wheat_date": "",
        "oil_price_usd_bbl": oil_price_usd_bbl,
        "oil_source": "Резервное значение",
        "oil_date": "",
        "fuel_change_percent": fuel_change
    }