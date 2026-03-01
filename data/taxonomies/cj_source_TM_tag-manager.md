# Таксономия Customer Journey: источник TM (Tag Manager)

Источник данных (source) в DMPQL: **TM**
Используется в запросах: `audience from customer_journey(TM[...])`

Всего атрибутов: **92**


## Атрибуты DMP

| ID | name | Описание | Тип | Допустимые значения |
|-----|------|----------|-----|---------------------|
| 10084 | segment-id | Идентификатор сегмента DMP | long | — |

## Атрибуты источника запроса

| ID | name | Описание | Тип | Допустимые значения |
|-----|------|----------|-----|---------------------|
| 10009 | source_ip4 | IP v4 адрес | string | — |
| 10010 | source_ip6 | IP v6 адрес | string | — |
| 10011 | source_asn | ASN | string | — |
| 10064 | source_tor | Запрос из сети Tor | boolean | — |

## Атрибуты 1DMP Tag Manager

| ID | name | Описание | Тип | Допустимые значения |
|-----|------|----------|-----|---------------------|
| 10052 | tm_tag_type | Тип тега | string | — |
| 10053 | tm_tag_id | ИД тега | long | — |
| 10054 | tm_container_id | ИД контейнера (UID) | string | — |
| 10055 | tm_container_version | Версия контейнера | long | — |
| 10056 | tm_trigger_id | ИД триггера | long | — |
| 10057 | tm_event_name | Название события | string | — |
| 10058 | tm_label | Дополнительные данные | string-string | — |
| 10067 | tm_page_title | Название страницы | string | — |
| 10068 | tm_page_keywords | Ключевые слова | string | — |
| 10069 | tm_page_description | Описание страницы | string | — |
| 10070 | tm_ref_url | Источник запроса | string | — |
| 10071 | tm_page_url | Единообразный локатор страницы | string | — |
| 10076 | tm_page_secure | Страница использует HTTPS | boolean | — |
| 10077 | tm_page_domain | Домен страницы | string | — |
| 10078 | tm_page_path | Идентификатор ресурса страницы | string | — |
| 10079 | tm_page_param | Параметры запроса страницы | string-string | — |
| 10080 | tm_ref_secure | Страница источник использует HTTPS | boolean | — |
| 10081 | tm_ref_domain | Домен страницы источника | string | — |
| 10082 | tm_ref_path | Идентификатор ресурса страницы источника | string | — |
| 10083 | tm_ref_param | Параметры запроса страницы источника | string-string | — |

## Гео-атрибуты запроса

| ID | name | Описание | Тип | Допустимые значения |
|-----|------|----------|-----|---------------------|
| 10045 | geo_city | Город | string | — |
| 10046 | geo_country | Страна | string | — |
| 10047 | geo_continent | Континент | string | — |
| 10048 | geo_latitude | Широта | double | — |
| 10049 | geo_longitude | Долгота | double | — |
| 10050 | geo_postal_code | Почтовый индекс | string | — |
| 10051 | geo_timezone | Часовой пояс | string | — |
| 10085 | geo_subdivision | Регион | string | — |

## Дополнительные HTTP атрибуты

| ID | name | Описание | Тип | Допустимые значения |
|-----|------|----------|-----|---------------------|
| 10014 | http_domain | Домен HTTP запроса | string | — |
| 10022 | http_ua_family | Семейство браузера | string | — |
| 10024 | http_ua_version_major | Основная версия браузера | long | — |
| 10025 | http_ua_version_minor | Минорная версия браузера | long | — |
| 10026 | http_ua_version_patch | Версия патча браузера | long | — |
| 10027 | http_ua_os_family | Семейство ОС | string | — |
| 10028 | http_ua_os_architecture | Архитектура ОС | long | `10000` (x86), `10001` (x64), `10002` (x64) |
| 10030 | http_ua_os_version_major | Основная версия ОС | long | — |
| 10031 | http_ua_os_version_minor | Минорная версия ОС | long | — |
| 10032 | http_ua_os_version_patch | Версия патча ОС | long | — |
| 10033 | http_ua_device_brand | Изготовитель устройства | string | — |
| 10034 | http_ua_device_model | Модель устройства | string | — |
| 10035 | http_ua_device_form_factor | Форм-фактор устройства | long | `10000` (Мобильное устройство), `10001` (Планшет), `10002` (Компьютер), `10003` (Игровая консоль), `10004` (Устройство Internet of Things), `10005` (TV) |
| 10036 | http_ua_engine | Ядро браузера | string | — |
| 10037 | http_ua_engine_version_string | Версия ядра браузера | string | — |
| 10038 | http_ua_engine_version_major | Основная версия ядра браузера | long | — |
| 10039 | http_ua_engine_version_minor | Минорная версия ядра браузера | long | — |
| 10040 | http_ua_engine_version_patch | Версия патча ядра браузера | long | — |
| 10041 | http_ua_bot | Бот | boolean | — |
| 10042 | http_language | Язык клиента | string | — |
| 10043 | http_cookie_support_level | Уровень поддержки cookie | long | `10000` (Cookie заблокированы), `10001` (Разрешены Cookie только с домена сайта), `10002` (Разрешены Cookie с других доменов), `10003` (Evercookies разрешены), `10004` (Присутствует Opt-out cookie) |

## Системные атрибуты

| ID | name | Описание | Тип | Допустимые значения |
|-----|------|----------|-----|---------------------|
| 10000 | id | ИД События | string | — |
| 10001 | created | Дата и время события | long | — |
| 10002 | type | Тип события | string | `tm` (Событие 1DMP Tag Manager), `iptv` (Событие IPTV), `dpi` (Событие DPI) |
| 10003 | origin | ИД Источника события | string | — |
| 10004 | owner | ИД Владельца события | string | — |

## Основные ID атрибуты

| ID | name | Описание | Тип | Допустимые значения |
|-----|------|----------|-----|---------------------|
| 10005 | id | Уникальный ИД пользователя | string | — |

## UTM метки

| ID | name | Описание | Тип | Допустимые значения |
|-----|------|----------|-----|---------------------|
| 10059 | utm_source | UTM Source | string | — |
| 10060 | utm_medium | UTM Medium | string | — |
| 10061 | utm_campaign | UTM Campaign | string | — |
| 10062 | utm_content  | UTM Content | string | — |
| 10063 | utm_term | UTM Term | string | — |

## Openstat метки

| ID | name | Описание | Тип | Допустимые значения |
|-----|------|----------|-----|---------------------|
| 10072 | openstat_service | Openstat Service | string | — |
| 10073 | openstat_campaign | Openstat Campaign | string | — |
| 10074 | openstat_ad | Openstat Ad | string | — |
| 10075 | openstat_source | Openstat Source | string | — |

## Основные HTTP атрибуты

| ID | name | Описание | Тип | Допустимые значения |
|-----|------|----------|-----|---------------------|
| 10012 | http_secure | HTTPS | boolean | — |
| 10013 | http_version | Версия HTTP | string | `1.0` (http/1.0), `1.1` (http/1.1), `2.0` (http/2.0) |
| 10015 | http_path | Путь HTTP запроса | string | — |
| 10016 | http_fragment | Фрагмент URL запроса | string | — |
| 10017 | http_method | Метод HTTP запроса | string | `get` (GET), `post` (POST), `put` (PUT), `head` (HEAD), `delete` (DELETE), `options` (OPTIONS), `patch` (PATCH) |
| 10018 | http_header | Заголовки HTTP запроса | string-string | — |
| 10019 | http_cookie | HTTP Cookies | string-string | — |
| 10020 | http_param | Параметры запроса HTTP | string-string | — |
| 10021 | http_body | Тело HTTP запроса | blob | — |
| 10065 | http_remote_addr | IP-адрес клиента | string-string | — |

## Дополнительные ID атрибуты

| ID | name | Описание | Тип | Допустимые значения |
|-----|------|----------|-----|---------------------|
| 10007 | id_private | Персональные идентификаторы | long-string | `10001` (Адрес электронной почты), `10002` (Идентификатор Skype), `10003` (Идентификатор VK), `10004` (Идентификатор FB), `10005` (Идентификатор OK), `10006` (Идентификатор Twitter), `10007` (Идентификатор Instagram), `10008` (Идентификатор МойМир), `10009` (Идентификатор LJ), `10010` (Идентификатор LinkedIn) |
| 10008 | id_public | Неперсональные идентификаторы | long-string | `10001` (IDFA SHA1), `10002` (IDFA MD5), `10003` (Android ID), `10004` (Android ID SHA1), `10005` (Android ID MD5), `10006` (Google AD ID), `10007` (IMEI), `10008` (IMEI SHA1), `10009` (IMEI MD5), `10010` (Apple UDID) ... (+19) |

## Атрибуты CleverBank

| ID | name | Описание | Тип | Допустимые значения |
|-----|------|----------|-----|---------------------|
| 30061 | Название купленной акции | Название купленной акции | string | — |
| 30062 | ID чека покупки акций | ID чека покупки акций | string | — |
| 30063 | Цена акции | Цена акции | double | — |
| 30064 | Количество купленных акций | Количество купленных акций | long | — |
| 30065 | Статус рассылки | Статус рассылки | string | — |
| 30066 | Тип уведомления | Тип уведомления | string | — |
| 30067 | Тип оплаты | Тип оплаты | string | — |
| 30068 | Категория акций | Категория акций | string | — |
| 30069 | Интерес к продуктам | Интерес к продуктам | string | — |

## Идентификаторы первого касания

| ID | name | Описание | Тип | Допустимые значения |
|-----|------|----------|-----|---------------------|
| 30070 | email | email | string | — |
| 30071 | phone | phone | string | — |
