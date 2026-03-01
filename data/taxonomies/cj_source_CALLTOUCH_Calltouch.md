# Таксономия Customer Journey: источник CALLTOUCH (Calltouch)

Источник данных (source) в DMPQL: **CALLTOUCH**
Используется в запросах: `audience from customer_journey(CALLTOUCH[...])`

Всего атрибутов: **60**


## Атрибуты Calltouch

| ID | name | Описание | Тип | Допустимые значения |
|-----|------|----------|-----|---------------------|
| 30001 | id | ID звонка | string | — |
| 30002 | leadtype | Тип обращения | string | `call` (call), `request` (request on call) |
| 30003 | callphase | Фаза звонка | string | `callconnected` (start call), `calldisconnected` (end call) |
| 30004 | requestId | ID заявки в Calltouch | string | — |
| 30005 | requestNumber | Внешний ID заявки | string | — |
| 30006 | subject | Название формы | string | — |
| 30007 | fio | ФИО клиента | string | — |
| 30008 | phonenumber | Отслеживаемый номер | string | — |
| 30009 | redirectNumber | Номер переадресации | string | — |
| 30010 | duration | Длительность разговора | long | — |
| 30011 | waiting_time | Длительность ожидания | long | — |
| 30012 | calltime | Дата и время звонка, (YYYY-MM-DD hh:mm:ss) | string | — |
| 30013 | timestamp | Дата и время звонка, (Unix Timestamp, seconds) | long | — |
| 30014 | requestDate | Дата и время заявки, (YYYY-MM-DD hh:mm:ss) | string | — |
| 30015 | status | Статус звонка | string | `successful` (удачный звонок), `unsuccessful` (неудачный звонок) |
| 30016 | unique | Уникальная заявка | boolean | — |
| 30017 | targetcall | Целевая заявка | string | `target` (целевая заявка), `non-target` (нецелевая заявка) |
| 30018 | uniqtargetcall | Уникально-целевая заявка | string | `uniqtarget` (уникально-целевая заявка), `non-uniqtarget` (не уникально-целевая заявка) |
| 30019 | callback | Обратный звонок | string | `callback` (обратный звонок), `non-callback` (прямой звонок на отслеживаемый номер) |
| 30020 | uniquerequest | Уникальная заявка | boolean | — |
| 30021 | targetrequest | Целевая заявка | string | `target` (target request), `целевая заявка` (нецелевая заявка) |
| 30022 | uniqtargetrequest | Уникально-целевая заявка | string | `uniqtarget` (уникально-целевая заявка), `non-uniqtarget` (не уникально-целевая заявка) |
| 30023 | worktime | Звонок в рабочее время | string | `worktime` (рабочее время), `non-worktime` (нерабочее время) |
| 30024 | pool | Пул входящего номера звонка | string | `staticOffline` (звонок на статический оффлайн номер), `staticOnline` (звонок на статический онлайн номер), `null` (звонок с формы обратного звонка) |
| 30025 | rating | Рейтинг звонка | long | `0` (0), `1` (1), `2` (2), `3` (3), `4` (4), `5` (5) |
| 30026 | tags_auto_pr | Теги Calltouch Predict | string | — |
| 30027 | tags_auto_af | Теги Calltouch Антифрод | string | — |
| 30028 | tags_auto_ct | Теги по добавочным | string | — |
| 30029 | tags_auto_pn | Теги по номерам | string | — |
| 30030 | tags_manual | Вручную проставленные теги | string | — |
| 30031 | tags_request | Теги заявок | string | — |
| 30032 | attribution | Модель атрибуции | long | `0` (последний непрямой), `1` (последнее взаимодействие) |
| 30033 | source | Источник | string | — |
| 30034 | medium | Канал | string | — |
| 30035 | utm_source | Метка utm_source | string | — |
| 30036 | utm_medium | Метка utm_medium | string | — |
| 30037 | utm_campaign | Метка utm_campaign | string | — |
| 30038 | utm_content | Метка utm_content | string | — |
| 30039 | utm_term | Метка utm_term | string | — |
| 30040 | sessionId | ID сессии Calltouch | string | — |
| 30041 | hostname | Отслеживаемый сайт | string | — |
| 30042 | url | Страница входа на сайт | string | — |
| 30043 | callUrl | Страница звонка | string | — |
| 30044 | callback_request_id | Идентификатор заявки на обратный звонок | string | — |
| 30045 | callback_final_attempt | Флаг завершения цепочки вызовов | string | — |
| 30046 | ref | Источник реферального перехода | string | — |
| 30047 | city | Город | string | — |
| 30048 | browser | Браузер | string | — |
| 30049 | os | Операционная система | string | — |
| 30050 | device | Устройство | string | — |
| 30051 | ip | IP-адрес | string | — |
| 30052 | sip_call_id | ID сеанса SIP | string | — |
| 30053 | callReferenceNumber | ID звонка с АТС | string | — |
| 30054 | reclink | Ссылка на запись разговора | string | — |
| 30055 | orderId | ID  сделки | string | — |
| 30056 | siteId | ID  сайта | string | — |
| 30057 | siteName | Название сайта | string | — |
| 30058 | userAgent | User agent | string | — |
| 30059 | manager | Менеджер | string | — |
| 30060 | attrs | Cookie | string-string | — |
