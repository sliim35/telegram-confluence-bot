"""
Telegram RAG Bot — CDJ Documentation Assistant
"""

import chromadb
import json
import logging
import os
import re
import time

from collections import defaultdict
from functools import wraps
from typing import Any, cast

from dotenv import load_dotenv
load_dotenv()

from telegram import Update
from telegram.ext import Application, AIORateLimiter, CommandHandler, MessageHandler, filters, ContextTypes

from llama_index.core import VectorStoreIndex, Settings, PromptTemplate, SimpleDirectoryReader, StorageContext
from llama_index.core.response_synthesizers import ResponseMode
from llama_index.core.retrievers import QueryFusionRetriever
from llama_index.core.postprocessor import SentenceTransformerRerank
from llama_index.core.query_engine import RetrieverQueryEngine
from llama_index.core.node_parser import SentenceSplitter, MarkdownNodeParser
from llama_index.core.vector_stores import MetadataFilter, MetadataFilters

from llama_index.llms.openai import OpenAI
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.vector_stores.chroma import ChromaVectorStore
from llama_index.readers.confluence import ConfluenceReader
from llama_index.retrievers.bm25 import BM25Retriever

# ── Logging ──────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# ── Configuration ────────────────────────────────────────────────

def get_required_env(key: str) -> str:
    value = os.getenv(key)
    if not value:
        raise RuntimeError(f"Missing required env variable: {key}")
    return value


LLM_MODEL = os.getenv("LLM_MODEL", "gpt-5")
LLM_BASE_URL = get_required_env("LLM_BASE_URL")
LLM_API_KEY = get_required_env("LLM_API_KEY")
EMBEDDING_MODEL = "intfloat/multilingual-e5-small"
RANK_MODEL = "jeffwan/mmarco-mMiniLMv2-L12-H384-v1"
TEMPERATURE = 0.1
ADMIN_IDS = [378702519]

CONFLUENCE_BASE_URL = os.getenv("CONFLUENCE_BASE_URL")
CONFLUENCE_API_KEY = os.getenv("CONFLUENCE_API_KEY")
CONFLUENCE_PAGE_IDS = [
    "3853484973", "3922789088", "3921510449",
    "3911945763", "3922789572", "3922788912",
    "3921510598", "3853484975", "3853484980",
    "3853485001", "3853485008", "3853485053",
    "3853485070", "3853485077", "3864858736",
    "3853485080", "3853485120", "3853485134",
    "3853485193", "3853485200", "3864858026",
    "3278176293", "3268575246", "3864858018",
    "3853485382", "3853485385", "3853485409",
    "3853485411", "3853485507", "3911943677",
    "3922788579", "3922788865", "3922788889",
    "3922789108", "3922789202", "3895461029",
    "3922793174", "3922788958", "3922791099",

    "3864855113", "3853485524", "3853485531",
    "3853485536", "3853485538", "3853485548",
    "3853485552", "3853485556", "3853485575",
    "3853485596", "3853485599", "3853485605",
    "3862855691", "3864856033", "3864859052",
    "3911943525", "3911943940", "3922792946",
    "3922792767", "3934751277", "3934751287",

    "3853485615", "3853485619", "3853485621",
    "3853485623", "3853485638", "3853485640",
    "3853484566",

    "3904176500", "3904178024", "3911944761",
    "3934749207",

    "3853485042"
]
DMPQL_CONFLUENCE_PAGE_IDS = ["3864858736"]

# ── LlamaIndex Settings (global singleton) ──────────────────────
logger.info("Configuring LlamaIndex: model=%s, embeddings=%s", LLM_MODEL, EMBEDDING_MODEL)

Settings.llm = OpenAI(
    model=LLM_MODEL,
    api_key=LLM_API_KEY,
    api_base=LLM_BASE_URL,
    temperature=TEMPERATURE,
    max_retries=3,
    max_tokens=8192,
    timeout=120,
)
Settings.node_parser = SentenceSplitter(chunk_size=1024, chunk_overlap=200)
Settings.embed_model = HuggingFaceEmbedding(
    model_name=EMBEDDING_MODEL,
    query_instruction="query: ",
    text_instruction="passage: ",
)

# ── In-memory state ─────────────────────────────────────────────
chat_history: defaultdict[int, list[str]] = defaultdict(list)

# ── Prompts ──────────────────────────────────────────────────────
DOCS_QA_PROMPT = PromptTemplate(
    "Контекст из документов:\n"
    "-----\n"
    "{context_str}\n"
    "-----\n"
    "Отвечай ТОЛЬКО на основе контекста выше.\n"
    "НЕ используй знания из обучения модели.\n"
    "Если в контексте нет информации — скажи: "
    "'В документации этой информации нет.'\n\n"
    "## Формат ответа\n"
    "Адаптируй формат под тип вопроса:\n"
    "- Простой вопрос ('что такое X?') → 2-3 предложения прозой\n"
    "- Перечисление ('какие операторы есть?') → короткий список\n"
    "- Сравнение → таблица или пары 'A — ..., B — ...'\n"
    "- Сложная тема → абзац с ключевыми терминами **жирным**\n\n"
    "Правила:\n"
    "1. Начинай сразу с сути — без вводных фраз\n"
    "2. Списки — только для реальных перечислений (3+ однородных элементов)\n"
    "3. Никогда не делай вложенные списки глубже 1 уровня\n"
    "4. Предпочитай короткие абзацы длинным спискам\n"
    "5. Максимум 1 заголовок на ответ (только если тема сложная)\n\n"
    "Вопрос: {query_str}\n"
    "Ответ:\n"
)


# ═════════════════════════════════════════════════════════════════
# DMPQL AI PIPELINE
# ═════════════════════════════════════════════════════════════════

MAX_RETRIES = 2

# ── Full .g4 grammar (embedded as spec for LLM) ─────────────────

GRAMMAR_G4 = r"""
grammar SegmentRule;

segmentRule
    : AUDIENCE FROM (cj | cp) EOF
    ;

cj
    : CJ '(' cjPredicate ')' (cpjJoinPredicate cp)? (WITHIN globalPredicate)?
    ;

cp
    : CP '(' attrPredicate ')'
    ;

globalPredicate
    : duration
    ;

cpjJoinPredicate
    : OF   #OfCpjJoinPredicate
    | OR   #OrCpjJoinPredicate
    ;

cjPredicate
    : '(' cjPredicate ')'          #ParensCjPredicate
    | NOT cjPredicate              #NotCjPredicate
    | cjPredicate AND cjPredicate  #AndCjPredicate
    | cjPredicate OR cjPredicate   #OrCjPredicate
    | cjExpressionPredicate        #CjExpressionPredicateBody
    ;

cjExpressionPredicate
    : cjUnaryPredicate
    | cjBinaryPredicate
    ;

cjBinaryPredicate
    : cjBooleanExpression equalityOps cjBooleanExpression
    | cjValueExpression (equalityOps | relationalOps) cjValueExpression
    ;

cjUnaryPredicate
    : cjBooleanExpression
    ;

cjBooleanExpression
    : cjInOrderExpression
    | cjEventExpression
    | booleanExpression
    ;

cjValueExpression
    : cjSimpleValueExpression
    | cjArithmeticExpression
    ;

cjSimpleValueExpression
    : aggFunctionComputableExpression
    | primitiveExpression
    | timeExpression
    | durationExpression
    | stopWatchExpression
    | attrValueExpression
    ;

cjArithmeticExpression
    : '(' cjArithmeticExpression ')'
    | cjArithmeticExpression (MULT | DIV | PLUS | MINUS) cjArithmeticExpression
    | cjSimpleValueExpression
    ;

cjEventExpression : cjEventPredicate ;

cjValueComputableExpression
    : cjSimpleValueComputableExpression
    ;

cjSimpleValueComputableExpression
    : primitiveExpression
    | timeExpression
    | durationExpression
    | stopWatchExpression
    | attrValueExpression
    ;

aggFunctionComputableExpression
    : IDENTIFIER '(' cjEventPredicate (',' attrFieldExpression)? ')'
    | IDENTIFIER '(' cjValueComputableExpression ')'
    ;

existsComputableExpression
    : EXISTS '(' attrFieldExpression (',' cjValueComputableExpression)* ')'
    ;

cjInOrderExpression
    : IN_ORDER '(' cjEventPredicates (',' cjEventPredicates)* ')'
    ;

cjEventPredicates : cjEventPredicate ;

cjEventPredicate
    : IDENTIFIER '[' attrPredicate? ']'
    ;

attrPredicate
    : '(' attrPredicate ')'                 #ParensAttributePredicate
    | NOT attrPredicate                     #NotAttributePredicate
    | attrPredicate AND attrPredicate       #AndAttributePredicate
    | attrPredicate OR attrPredicate        #OrAttributePredicate
    | attrBinaryPredicate                   #AttrBinaryPredicateBody
    | attrUnaryPredicate                    #AttrUnaryPredicateBody
    ;

attrBinaryPredicate
    : attrBooleanExpression equalityOps attrBooleanExpression
    | attrValueExpression (equalityOps | relationalOps) attrValueExpression
    | attrValueExpression setOps attrCollectionExpression
    ;

attrCollectionExpression
    : '(' attrCollectionValue (',' attrCollectionValue)* ')'
    ;

attrCollectionValue : primitive ;

attrUnaryPredicate : attrBooleanExpression ;

attrBooleanExpression
    : attrFieldExpression
    | booleanExpression
    ;

attrValueExpression
    : attrSimpleValueExpression
    | attrArithmeticExpression
    ;

attrSimpleValueExpression
    : attrFieldExpression
    | timeExpression
    | durationExpression
    | primitiveExpression
    ;

attrArithmeticExpression
    : '(' attrArithmeticExpression ')'
    | attrArithmeticExpression (MULT | DIV | PLUS | MINUS) attrArithmeticExpression
    | attrSimpleValueExpression
    ;

attrFieldExpression
    : attrSimpleFieldExpression
    | attrFunctionExpression
    ;

attrFunctionExpression
    : dateFormatExpression
    | dateParseExpression
    | jsonExpression
    ;

attrSimpleFieldExpression
    : ATTR '(' idArg (',' keyArg)? ')'
    ;

idArg : signedInt ;
keyArg
    : signedInt     #IntValKeyArg
    | stringArg     #StringValKeyArg
    ;

jsonExpression
    : JSON '(' attrSimpleFieldExpression ',' stringArg (',' stringArg)? ')'
    ;
dateFormatExpression
    : DATE_FORMAT '(' attrValueExpression ',' stringArg ')'
    ;
dateParseExpression
    : DATE_PARSE '(' attrValueExpression ',' stringArg ')'
    ;

scenarioContextPredicate
    : '(' scenarioContextPredicate ')'                            #ParensScenarioContextPredicate
    | NOT scenarioContextPredicate                                #NotScenarioContextPredicate
    | scenarioContextPredicate AND scenarioContextPredicate       #AndScenarioContextPredicate
    | scenarioContextPredicate OR scenarioContextPredicate        #OrScenarioContextPredicate
    | scenarioContextBinaryPredicate                              #ScenarioContextBinaryPredicateBody
    | scenarioContextUnaryPredicate                               #ScenarioContextUnaryPredicateBody
    ;

scenarioContextUnaryPredicate
    : scenarioContextBooleanExpression
    ;

scenarioContextBinaryPredicate
    : scenarioContextBooleanExpression equalityOps scenarioContextBooleanExpression
    | scenarioContextBinaryPredicateExpression (equalityOps | relationalOps) scenarioContextBinaryPredicateExpression
    | scenarioContextBinaryPredicateExpression setOps attrCollectionExpression
    ;

scenarioContextBinaryPredicateExpression
    : scenarioContextValueExpression
    | scenarioContextArithmeticExpression
    | primitiveExpression
    ;

scenarioContextExpression
    : scenarioContextValueExpression
    | scenarioContextArithmeticExpression
    | scenarioContextConcatExpression
    ;

scenarioContextArithmeticExpression
    : '(' scenarioContextArithmeticExpression ')'
    | scenarioContextArithmeticExpression (MULT | DIV | PLUS | MINUS) scenarioContextArithmeticExpression
    | scenarioContextSimpleValueExpression
    ;

scenarioContextConcatExpression
    : CONCAT '(' scenarioContextComplexValueExpression ',' scenarioContextComplexValueExpression ')'
    ;

scenarioContextComplexValueExpression
    : scenarioContextArithmeticExpression
    | scenarioContextConcatExpression
    ;

scenarioContextBooleanExpression
    : scenarioContextValueExpression
    | booleanExpression
    ;

scenarioContextSimpleValueExpression
    : scenarioContextValueExpression
    | primitiveExpression
    ;

scenarioContextValueExpression
    : SCENARIO_CONTEXT '(' stringArg ')'
    ;

timeExpression : NOW ;
durationExpression : duration ;
duration : timeSpan timeUnit ;
timeSpan : unsignedInt ;

timeUnit
    : MINUTE | HOUR | DAY
    ;

primitive
    : booleanValue | signedInt | NUMBER | STRING
    ;

booleanValue : BOOL ;
primitiveExpression : primitive ;
booleanExpression : booleanValue ;

setOps
    : NOT? IN       #InOp
    | NOT? LIKEIN   #LikeInOp
    | NOT? ILIKEIN  #ILikeInOp
    ;

equalityOps : EQ | NOT_EQ ;
relationalOps
    : GT | LT | GT_EQ | LT_EQ
    | NOT? LIKE
    | NOT? ILIKE
    ;

stopWatchExpression
    : STOPWATCH '(' startPredicate (',' stopPredicate)? (',' FIRST_EVENT_MODE)? ')'
    ;
startPredicate : cjExpressionPredicate ;
stopPredicate : cjExpressionPredicate ;

signedInt : MINUS? unsignedInt ;
unsignedInt : INT ;
stringArg : STRING ;

// ── LEXER ──
CJ               : 'customer_journey';
CP               : 'customer_profiles';
SCENARIO_CONTEXT : 'scenario_context';
AUDIENCE         : 'audience';
FROM             : 'from';
ATTR             : 'attr';
STOPWATCH        : 'stopwatch';
FIRST_EVENT_MODE : 'first_event';
WITHIN           : 'within';
IN_ORDER         : 'in_order';
JSON             : 'json_extract';
CONCAT           : 'concat';
DATE_FORMAT      : 'date_format';
DATE_PARSE       : 'date_parse';
OF               : 'of';
AND              : 'and';
NOT              : 'not';
OR               : 'or';
SECOND           : 'second' | 'seconds';
MINUTE           : 'minute' | 'minutes';
HOUR             : 'hour'   | 'hours';
DAY              : 'day'    | 'days';
MONTH            : 'month'  | 'months';
YEAR             : 'year'   | 'years';
GT               : '>';
LT               : '<';
EQ               : '=';
NOT_EQ           : '!=';
GT_EQ            : '>=';
LT_EQ            : '<=';
LIKE             : 'like';
ILIKE            : 'ilike';
IN               : 'in';
LIKEIN           : 'likein';
ILIKEIN          : 'ilikein';
EXISTS           : 'exists';
NOW              : 'now';
BOOL             : 'true' | 'false';
INT              : [0-9]+;
IDENTIFIER       : [a-zA-Z][a-zA-Z0-9_]* ;
STRING           : '"' ~["\r\n]* '"' ;
NUMBER           : ('0' | [1-9][0-9]*)('.' [0-9]+ )? ;
MINUS            : '-';
PLUS             : '+';
MULT             : '*';
DIV              : '/';
WS               : [ \r\n\t\u00a0]+ -> channel(HIDDEN) ;
LINE_COMMENT     : '--' .*? '\r'? '\n' -> skip ;
"""


# ── Helper: LLM call with logging ───────────────────────────────


async def llm_stream(prompt: str):
    """Returns an async stream instead of a string."""
    stream = await Settings.llm.astream_complete(prompt)
    return stream


def llm_call(prompt: str, step_name: str) -> str:
    """Call LLM with timing and logging."""
    t0 = time.time()
    logger.info("[%s] Calling LLM (%d chars prompt)...", step_name, len(prompt))
    result = str(Settings.llm.complete(prompt)).strip()
    elapsed = time.time() - t0
    logger.info("[%s] LLM responded in %.1fs (%d chars)", step_name, elapsed, len(result))
    logger.debug("[%s] LLM response:\n%s", step_name, result[:500])
    return result


def parse_json(raw: str, step_name: str) -> dict | None:
    """Parse JSON from LLM output, stripping markdown fences."""
    clean = re.sub(r'^```(?:json)?\s*', '', raw)
    clean = re.sub(r'\s*```$', '', clean)
    try:
        return json.loads(clean)
    except (json.JSONDecodeError, TypeError) as e:
        logger.warning("[%s] JSON parse failed: %s", step_name, e)
        logger.debug("[%s] Raw output was:\n%s", step_name, raw[:300])
        return None


# ═════════════════════════════════════════════════════════════════
# AI STEP 1: Analyze query (rewrite + route + extract in one call)
# ═════════════════════════════════════════════════════════════════

def ai_analyze_query(
    question: str,
    history: list[str],
    force_generate: bool = False,
) -> dict[str, str]:
    """Single LLM call: resolve pronouns, classify intent, extract search terms.

    Returns dict with keys:
      - intent: "GENERATE" or "DOCS"
      - query: rewritten question (pronouns resolved)
      - syntax_query: search terms for syntax docs (only for GENERATE)
      - taxonomy_query: search terms for taxonomy (only for GENERATE)
    """
    logger.info("[ANALYZE] Input: '%s', history=%d, force_generate=%s",
                question[:80], len(history), force_generate)

    # ── Build history section (only when needed) ──────────────────
    history_section = ""
    if history:
        history_str = "\n".join(history)
        history_section = (
            f"## История диалога\n{history_str}\n\n"
            "Используй историю, чтобы разрешить местоимения "
            "('это', 'тот', 'он', 'такой же') в вопросе пользователя.\n\n"
        )

    # ── Build intent section (skip when force_generate) ───────────
    if force_generate:
        intent_section = (
            "## Определи намерение\n"
            "Пользователь отправил команду /generate, НО проверь:\n"
            "- Если вопрос просит СОСТАВИТЬ, НАПИСАТЬ, ИСПРАВИТЬ конкретный DMPQL запрос → GENERATE\n"
            "- Если вопрос просит СПРАВКУ, ОПИСАНИЕ, ОБЗОР возможностей, "
            "объяснение синтаксиса, 'что такое', 'как работает' → DOCS\n"
            "Команда /generate НЕ перекрывает смысл вопроса.\n\n"
        )
    else:
        intent_section = (
            "## Определи намерение\n"
            "- GENERATE — пользователь даёт КОНКРЕТНОЕ ЗАДАНИЕ на составление, "
            "исправление или отладку DMPQL запроса. "
            "Ключевые маркеры: 'составь запрос', 'напиши DMPQL', "
            "'найди аудиторию где...', 'исправь этот запрос'\n"
            "- DOCS — всё остальное: объяснения, настройка платформы, "
            "'как создать', 'как настроить', 'что такое', 'как работает', "
            "'где в интерфейсе'. Вопрос о НАСТРОЙКЕ функции платформы — "
            "это DOCS, даже если в вопросе есть бизнес-термины "
            "(средний чек, покупки, склейка)\n\n"
        )

    prompt = (
        "Ты — помощник по DMPQL (язык запросов для CDP платформы).\n\n"
        f"{history_section}"
        f"{intent_section}"
        f"Вопрос пользователя: \"{question}\"\n\n"
        "## Задача\n"
        "Верни JSON (и НИЧЕГО больше, без markdown):\n"
        "{\n"
        '  "intent": "GENERATE" или "DOCS",\n'
        '  "query": "переписанный вопрос (местоимения заменены, '
        'разговорные слова убраны)",\n'
        '  "syntax_query": "ключевые слова для поиска синтаксиса DMPQL",\n'
        '  "taxonomy_query": "ключевые слова для поиска атрибутов и их ID"\n'
        "}\n\n"
        "Правила:\n"
        "1. query — уточнённый вопрос без местоимений и разговорных слов\n"
        "2. syntax_query и taxonomy_query заполняй ТОЛЬКО если intent=GENERATE, "
        "иначе оставь пустыми строками\n"
        "3. НЕ расширяй запрос — сужай и уточняй\n\n"
        "Примеры:\n"
        '"Составь запрос для выборки мужчин с покупками за 60 дней"\n'
        '→ {"intent": "GENERATE", '
        '"query": "сегмент мужчин с покупками за 60 дней", '
        '"syntax_query": "customer_journey customer_profiles event filter within", '
        '"taxonomy_query": "пол gender MALE purchase action ecomm"}\n\n'
        '"Что такое DMPQL?"\n'
        '→ {"intent": "DOCS", "query": "что такое DMPQL", '
        '"syntax_query": "", "taxonomy_query": ""}\n\n'
        '"Какие операторы сравнения есть?"\n'
        '→ {"intent": "DOCS", "query": "операторы сравнения DMPQL", '
        '"syntax_query": "", "taxonomy_query": ""}\n\n'
        '"Дай краткую справку о возможностях языка построения сегментов"\n'
        '→ {"intent": "DOCS", "query": "возможности языка DMPQL для сегментации", '
        '"syntax_query": "", "taxonomy_query": ""}\n\n'
        '"in_order: просмотр страницы, потом покупка"\n'
        '→ {"intent": "GENERATE", '
        '"query": "in_order просмотр страницы потом покупка", '
        '"syntax_query": "in_order customer_journey event sequence", '
        '"taxonomy_query": "page url просмотр purchase action ecomm событие"}\n\n'
        '"Как создать агрегатный атрибут _condition_?"\n'
        '→ {"intent": "DOCS", "query": "создание агрегатного атрибута _condition_", '
        '"syntax_query": "", "taxonomy_query": ""}\n\n'
        '"Как настроить склейку профилей?"\n'
        '→ {"intent": "DOCS", "query": "настройка склейки профилей", '
        '"syntax_query": "", "taxonomy_query": ""}\n\n'
        '"Где в интерфейсе создать новый сегмент?"\n'
        '→ {"intent": "DOCS", "query": "создание сегмента в интерфейсе", '
        '"syntax_query": "", "taxonomy_query": ""}\n\n'
    )

    raw = llm_call(prompt, "ANALYZE")
    parsed = parse_json(raw, "ANALYZE")

    if parsed:
        llm_intent = parsed.get("intent", "DOCS").upper()
        if force_generate and llm_intent == "GENERATE":
            intent = "GENERATE"
        elif force_generate and llm_intent == "DOCS":
            # LLM overrides /generate when question is clearly a docs question
            logger.info("[ANALYZE] /generate overridden → DOCS (LLM classified as DOCS)")
            intent = "DOCS"
        else:
            intent = llm_intent

        if "GENERATE" not in intent and "DOCS" not in intent:
            intent = "DOCS"

        result = {
            "intent": intent,
            "query": parsed.get("query", question),
            "syntax_query": parsed.get("syntax_query", question),
            "taxonomy_query": parsed.get("taxonomy_query", question),
        }
    else:
        logger.warning("[ANALYZE] JSON parse failed — fallback to DOCS")
        result = {
            "intent": "GENERATE" if force_generate else "DOCS",
            "query": question,
            "syntax_query": question,
            "taxonomy_query": question,
        }

    logger.info("[ANALYZE] intent=%s, query='%s'", result["intent"], result["query"][:80])
    if result["intent"] == "GENERATE":
        logger.info("[ANALYZE] syntax_query='%s'", result["syntax_query"][:100])
        logger.info("[ANALYZE] taxonomy_query='%s'", result["taxonomy_query"][:100])

    return result


# ═════════════════════════════════════════════════════════════════
# AI STEP 3: Compose DMPQL
# ═════════════════════════════════════════════════════════════════

def ai_compose(task: str, syntax_fragments: str, taxonomy_fragments: str) -> str:
    """LLM composes DMPQL with grammar + docs + taxonomy."""
    logger.info("[STEP 3 — COMPOSE] Task: '%s'", task[:100])
    logger.info(
        "[STEP 3 — COMPOSE] Context: syntax=%d chars, taxonomy=%d chars",
        len(syntax_fragments), len(taxonomy_fragments),
    )

    prompt = (
        "Ты — эксперт по DMPQL. Составь запрос по задаче пользователя.\n\n"
        f"## Задача\n{task}\n\n"
        f"## Грамматика DMPQL (ANTLR .g4)\n```\n{GRAMMAR_G4}\n```\n\n"
        f"## Фрагменты документации\n{syntax_fragments}\n\n"
        f"## Таксономия (реальные ID атрибутов)\n"
        f"{taxonomy_fragments if taxonomy_fragments else 'Таксономии не загружены.'}\n\n"
        "## Правила\n"
        "1. Используй ТОЛЬКО конструкции из грамматики выше\n"
        "2. `attr()` первый аргумент — ВСЕГДА числовой ID (idArg = signedInt)\n"
        "3. `attr()` второй аргумент (keyArg) — числовой ID или строка в двойных кавычках\n"
        "4. Строки — ТОЛЬКО в двойных кавычках\n"
        "5. Источники событий: TM, ECOMM, CALLTOUCH, BI, cm\n"
        "6. НЕ придумывай числовые ID — бери из таксономии\n"
        "7. Если ID нет в таксономии — используй условное обозначение: "
        "attr(«описание атрибута»)\n\n"
        "## Формат ответа\n"
        "Дай ДВА варианта:\n\n"
        "### Общий пример\n"
        "```dmpql блок с условными обозначениями в «ёлочками».\n"
        "Под блоком — список что нужно подставить.\n\n"
        "### Пример для вашей конфигурации\n"
        "```dmpql блок с РЕАЛЬНЫМИ числовыми ID из таксономии.\n"
        "Если таксономии нет — напиши: "
        "'Загрузите таксономии для персонализированного примера.'\n"
        "Пример сложного запроса: \n"
        "Найди мне людей в возрасте 30-50 лет, у которых средний чем за год > 120000 рублей, но при этом они не имеют низкой вероятности отклика по email. При этом всём, у этого человека должно быть больше 50 доставок за полгода.\n" \
        "Пример структуры сложного DMPQL для ответа:\n"
        "```dmpql\n"
        "audience from customer_journey(\n"
        "ECOMM[attr(20008) >= 50]\n"
        ") of customer_profiles(\n"
        "attr(10138, 10002) or attr(10138, 10003) ) and ( attr(10162, -1) > 120000  ) and not ( attr(10143, 10000) or attr(10143, 10001) )\n"
        "within 180 days\n"
        "```"
    )

    result = llm_call(prompt, "STEP 3 — COMPOSE")

    code_blocks = re.findall(r'```dmpql\s*(.*?)```', result, re.DOTALL)
    logger.info("[STEP 3 — COMPOSE] Generated %d code blocks", len(code_blocks))
    for i, block in enumerate(code_blocks):
        logger.info("[STEP 3 — COMPOSE] Block %d:\n%s", i + 1, block.strip()[:300])

    return result


# ═════════════════════════════════════════════════════════════════
# AI STEP 4: Validate DMPQL against grammar
# ═════════════════════════════════════════════════════════════════

def ai_validate(dmpql_code: str, block_num: int) -> dict[str, Any]:
    """LLM validates code against .g4 grammar. Returns structured result."""
    logger.info("[STEP 4 — VALIDATE] Block %d (%d chars)", block_num, len(dmpql_code))
    logger.info("[STEP 4 — VALIDATE] Code:\n%s", dmpql_code[:300])

    prompt = (
        "Ты — строгий валидатор DMPQL. Проверь код на соответствие грамматике.\n\n"
        f"## Грамматика DMPQL (ANTLR .g4)\n```\n{GRAMMAR_G4}\n```\n\n"
        f"## Код для проверки\n```\n{dmpql_code}\n```\n\n"
        "## Инструкция\n"
        "Пройди по коду токен за токеном и проверь:\n"
        "1. Начинается с `audience from` → `segmentRule`\n"
        "2. Источник: `customer_journey(...)` и/или `customer_profiles(...)`\n"
        "3. Между CJ и CP — `of` или `or` (cpjJoinPredicate)\n"
        "4. Events: `IDENTIFIER[...]` — IDENTIFIER ∈ {TM, ECOMM, CALLTOUCH, BI, cm}\n"
        "5. `attr(idArg, keyArg?)` — idArg = signedInt, keyArg = signedInt | STRING\n"
        "6. Скобки сбалансированы: (), []\n"
        "7. Операторы допустимые: =, !=, >, <, >=, <=, like, ilike, in, likein, ilikein\n"
        "8. Временные единицы: minute(s), hour(s), day(s)\n"
        "9. STRING = двойные кавычки \"...\"\n"
        "10. in_order() — минимум 2 события\n"
        "11. Нет SQL (SELECT, WHERE, GROUP BY)\n"
        "12. Нет незаменённых плейсхолдеров <...> или «...» в attr()\n\n"
        "Код с «ёлочками» в attr() — это ОБЩИЙ пример (шаблон), он допустим. "
        "Помечай их как warning, не error.\n\n"
        "Верни ТОЛЬКО JSON (без markdown, без пояснений):\n"
        "{\n"
        '  "valid": true/false,\n'
        '  "errors": [\n'
        '    {"rule": "название правила из .g4", '
        '"message": "описание ошибки", '
        '"fix": "как исправить"}\n'
        "  ],\n"
        '  "warnings": [\n'
        '    {"message": "описание предупреждения"}\n'
        "  ]\n"
        "}\n\n"
        "Если ошибок нет → valid: true, errors: []\n"
        "JSON:"
    )

    raw = llm_call(prompt, f"STEP 4 — VALIDATE block {block_num}")
    parsed = parse_json(raw, f"STEP 4 — VALIDATE block {block_num}")

    if parsed:
        result = {
            "valid": bool(parsed.get("valid", False)),
            "errors": parsed.get("errors", []),
            "warnings": parsed.get("warnings", []),
        }
    else:
        logger.warning("[STEP 4 — VALIDATE] JSON parse failed — treating as invalid")
        result = {
            "valid": False,
            "errors": [{"rule": "json_parse", "message": "Валидатор не вернул корректный JSON", "fix": "Повторить"}],
            "warnings": [],
        }

    logger.info(
        "[STEP 4 — VALIDATE] Block %d result: valid=%s, errors=%d, warnings=%d",
        block_num, result["valid"], len(result["errors"]), len(result["warnings"]),
    )
    for e in result["errors"]:
        logger.info("[STEP 4 — VALIDATE]   ❌ [%s] %s → %s", e.get("rule", "?"), e.get("message", "?"), e.get("fix", "?"))
    for w in result["warnings"]:
        logger.info("[STEP 4 — VALIDATE]   ⚠️ %s", w.get("message", "?"))

    return result


# ═════════════════════════════════════════════════════════════════
# AI STEP 5: Fix DMPQL based on validation errors
# ═════════════════════════════════════════════════════════════════

def ai_fix(
    original_code: str,
    errors: list[dict[str, str]],
    task: str,
    taxonomy_fragments: str,
    block_num: int,
    attempt: int,
) -> str:
    """LLM fixes code based on validation errors."""
    errors_text = "\n".join(
        f"- Правило: {e.get('rule', '?')}, Ошибка: {e.get('message', '?')}, "
        f"Исправление: {e.get('fix', '?')}"
        for e in errors
    )

    logger.info("[STEP 5 — FIX] Block %d, attempt %d", block_num, attempt)
    logger.info("[STEP 5 — FIX] Errors to fix:\n%s", errors_text)

    prompt = (
        "Ты — эксперт по DMPQL. Исправь запрос.\n\n"
        f"## Исходный запрос\n```dmpql\n{original_code}\n```\n\n"
        f"## Ошибки валидации\n{errors_text}\n\n"
        f"## Задача пользователя\n{task}\n\n"
        f"## Грамматика DMPQL\n```\n{GRAMMAR_G4}\n```\n\n"
        f"## Таксономия\n{taxonomy_fragments or 'Не предоставлена'}\n\n"
        "## Правила исправления\n"
        "1. Исправь КОНКРЕТНЫЕ ошибки из списка выше\n"
        "2. Не меняй то, что было правильно\n"
        "3. attr() первый аргумент — ТОЛЬКО числовой ID\n"
        "4. Если нет числового ID в таксономии — используй attr(«описание»)\n"
        "5. Строки — только в двойных кавычках\n\n"
        "Верни ТОЛЬКО исправленный DMPQL код, без markdown, без пояснений:\n"
    )

    raw = llm_call(prompt, f"STEP 5 — FIX block {block_num} attempt {attempt}")

    # Strip markdown fences if LLM wrapped them
    fixed = re.sub(r'^```(?:dmpql)?\s*', '', raw)
    fixed = re.sub(r'\s*```$', '', fixed)
    fixed = fixed.strip()

    logger.info("[STEP 5 — FIX] Fixed code:\n%s", fixed[:300])
    return fixed

# ═════════════════════════════════════════════════════════════════
# AI STEP 6: Explain DMPQL
# ═════════════════════════════════════════════════════════════════

def ai_explain(code_blocks: list[str]) -> str:
    """LLM explains DMPQL code. Skips template blocks with «placeholders»."""

    # Filter: only explain blocks with real IDs, skip templates
    concrete_blocks = [
        block for block in code_blocks
        if block.strip() and '«' not in block and '»' not in block
    ]

    if not concrete_blocks:
        # All blocks are templates — explain the first one as fallback
        concrete_blocks = [b for b in code_blocks if b.strip()][:1]

    all_blocks = "\n\n".join(
        f"```dmpql\n{block.strip()}\n```"
        for block in concrete_blocks
    )

    prompt = (
        "Ты — эксперт по DMPQL. Объясни запрос простым языком.\n\n"
        f"{all_blocks}\n\n"
        "## Формат\n"
        "Объясни каждую строку кратко:\n"
        "```\n"
        "строка кода → что она делает\n"
        "```\n"
        "Объясняй коротко и по делу. Упоминай числовые ID атрибутов "
        "и что они означают (если понятно из контекста).\n"
        "НЕ объясняй шаблонные блоки с «ёлочками» — они уже описаны выше.\n"
    )

    return llm_call(prompt, "EXPLAIN")


# ═════════════════════════════════════════════════════════════════
# ORCHESTRATOR: Full pipeline
# ═════════════════════════════════════════════════════════════════

def _format_validation_result(validation: dict[str, Any], block_num: int) -> str:
    """Format validation result for user output."""
    parts: list[str] = []
    if validation["errors"]:
        parts.append(f"❌ Блок {block_num}:")
        for e in validation["errors"]:
            parts.append(f"  • [{e.get('rule', '?')}] {e.get('message', '?')}")
            if e.get("fix"):
                parts.append(f"    → {e['fix']}")
    if validation["warnings"]:
        parts.append(f"⚠️ Блок {block_num} предупреждения:")
        for w in validation["warnings"]:
            parts.append(f"  • {w.get('message', '?')}")
    return "\n".join(parts)


async def generate_dmpql(
    query: str,
    search_terms: dict[str, str],
    index: VectorStoreIndex,
) -> str:
    """
    Full AI-driven pipeline:
      Step 1: search_terms provided by ai_analyze_query() (already done)
      Step 2: RAG retrieves syntax + taxonomy
      Step 3: AI composes DMPQL
      Step 4: AI validates each block
      Step 5: If invalid → AI fixes → back to Step 4 (max retries)
    """
    pipeline_start = time.time()
    logger.info("=" * 60)
    logger.info("DMPQL PIPELINE START: '%s'", query[:100])
    logger.info("=" * 60)

    # ── Step 2: RAG retrieval ────────────────────────────────────
    logger.info("[STEP 2 — RETRIEVE] Searching syntax index...")
    t0 = time.time()

    syntax_filters = MetadataFilters(filters=[
        MetadataFilter(key="category", value="syntax")
    ])
    syntax_retriever = index.as_retriever(
        similarity_top_k=10, filters=syntax_filters
    )
    syntax_nodes = syntax_retriever.retrieve(search_terms["syntax_query"])
    syntax_text = "\n---\n".join(
        f"[{n.metadata.get('title', '?')}]\n{n.text}" for n in syntax_nodes
    )
    logger.info(
        "[STEP 2 — RETRIEVE] Syntax: %d nodes, %d chars (%.1fs)",
        len(syntax_nodes), len(syntax_text), time.time() - t0,
    )
    for n in syntax_nodes[:3]:
        logger.info("[STEP 2 — RETRIEVE]   • score=%.3f title='%s'", n.score, n.metadata.get("title", "?"))

    logger.info("[STEP 2 — RETRIEVE] Searching taxonomy index...")
    t0 = time.time()

    tax_filters = MetadataFilters(filters=[
        MetadataFilter(key="category", value="taxonomy")
    ])
    tax_retriever = index.as_retriever(
        similarity_top_k=10, filters=tax_filters
    )
    tax_nodes = tax_retriever.retrieve(search_terms["taxonomy_query"])
    taxonomy_text = "\n---\n".join(n.text for n in tax_nodes)
    logger.info(
        "[STEP 2 — RETRIEVE] Taxonomy: %d nodes, %d chars (%.1fs)",
        len(tax_nodes), len(taxonomy_text), time.time() - t0,
    )
    for n in tax_nodes[:3]:
        logger.info("[STEP 2 — RETRIEVE]   • score=%.3f text='%s'", n.score, n.text[:80])

    # ── Step 3: AI composes ──────────────────────────────────────
    result = ai_compose(query, syntax_text, taxonomy_text)

    # ── Steps 4+5: Validate + Fix loop ───────────────────────────
    code_blocks = re.findall(r'```dmpql\s*(.*?)```', result, re.DOTALL)

    if not code_blocks:
        logger.warning("[PIPELINE] No ```dmpql blocks found in compose output")
        elapsed = time.time() - pipeline_start
        logger.info("DMPQL PIPELINE END: %.1fs total, 0 blocks", elapsed)
        return result + "\n\n⚠️ Не найдены блоки кода DMPQL в ответе."

    logger.info("[PIPELINE] Found %d code blocks to validate", len(code_blocks))

    all_valid = True
    all_results: list[str] = []
    total_llm_calls = 2

    for i, block in enumerate(code_blocks):
        block_clean = block.strip()
        if not block_clean:
            continue

        block_num = i + 1
        current_code = block_clean

        # Skip validation for template blocks with «placeholder» markers
        if '«' in current_code or '»' in current_code:
            logger.info("[PIPELINE] ⏭️ Block %d has «placeholders» — skipping validation", block_num)
            all_results.append(f"⏭️ Блок {block_num}: шаблон (валидация пропущена)")
            continue

        for attempt in range(1, MAX_RETRIES + 2):
            total_llm_calls += 1
            validation = ai_validate(current_code, block_num)

            if validation["valid"]:
                logger.info("[PIPELINE] ✅ Block %d valid on attempt %d", block_num, attempt)

                # Replace block in result if it was fixed
                if current_code != block_clean:
                    result = result.replace(
                        f"```dmpql\n{block}```",
                        f"```dmpql\n{current_code}\n```",
                    )

                all_results.append(f"✅ Блок {block_num}: синтаксис корректен")
                if validation["warnings"]:
                    all_results.append(
                        _format_validation_result(
                            {"errors": [], "warnings": validation["warnings"]},
                            block_num,
                        )
                    )
                break

            if attempt <= MAX_RETRIES:
                logger.info(
                    "[PIPELINE] Block %d failed validation, fixing (attempt %d/%d)...",
                    block_num, attempt, MAX_RETRIES,
                )
                total_llm_calls += 1
                current_code = ai_fix(
                    current_code, validation["errors"],
                    query, taxonomy_text,
                    block_num, attempt,
                )
            else:
                logger.warning(
                    "[PIPELINE] ❌ Block %d still invalid after %d attempts",
                    block_num, MAX_RETRIES + 1,
                )
                all_valid = False
                all_results.append(_format_validation_result(validation, block_num))

    # ── Log validation results (silent — not shown to user) ──────
    for line in all_results:
        logger.info("[PIPELINE] %s", line)

    # ── Step 6: Explain each block ───────────────────────────────
    final_blocks = re.findall(r'```dmpql\s*(.*?)```', result, re.DOTALL)
    if final_blocks:
        total_llm_calls += 1
        explanation = ai_explain(final_blocks)
        result += f"\n\n---\n📖 **Разбор запроса:**\n{explanation}"

    elapsed = time.time() - pipeline_start

    logger.info("=" * 60)
    logger.info(
        "DMPQL PIPELINE END: %.1fs total, %d LLM calls, %d blocks, all_valid=%s",
        elapsed, total_llm_calls, len(code_blocks), all_valid,
    )
    logger.info("=" * 60)

    return result


# ═════════════════════════════════════════════════════════════════
# ROUTER, REWRITER, ACCESS CONTROL
# ═════════════════════════════════════════════════════════════════


def subscribers_only(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if update.effective_user is None:
            return
        user_id = update.effective_user.id
        logger.info("[ACCESS] User ID: %d", user_id)
        if user_id not in ADMIN_IDS:
            logger.warning("[ACCESS] Denied for user %d", user_id)
            if update.message:
                await update.message.reply_text("У вас нет доступа.")
            return
        await func(update, context)
    return wrapper


# ═════════════════════════════════════════════════════════════════
# INDEX BUILDER
# ═════════════════════════════════════════════════════════════════

def build_engine() -> tuple[RetrieverQueryEngine, VectorStoreIndex] | None:
    """Load documents, store in ChromaDB, return query engine + index."""
    logger.info("[INDEX] Building engine...")
    t0 = time.time()

    if not CONFLUENCE_BASE_URL:
        logger.error("[INDEX] CONFLUENCE_BASE_URL not set")
        return None

    PERSIST_DIR = "./storage"
    db = chromadb.PersistentClient(path="./chroma_db")
    collection = db.get_or_create_collection("my_docs")
    vector_store = ChromaVectorStore(chroma_collection=collection)

    if collection.count() == 0 or not os.path.exists(PERSIST_DIR):
        logger.info("[INDEX] Empty collection — loading from sources...")

        reader = ConfluenceReader(
            cloud=False,
            base_url=CONFLUENCE_BASE_URL,
            api_token=CONFLUENCE_API_KEY,
        )
        confluence_documents = reader.load_data(page_ids=CONFLUENCE_PAGE_IDS)
        logger.info("[INDEX] Loaded %d confluence pages", len(confluence_documents))

        dmpql_documents = SimpleDirectoryReader("data/documents").load_data()
        logger.info("[INDEX] Loaded %d DMPQL docs", len(dmpql_documents))

        taxonomy_path = "data/taxonomies"
        if os.path.exists(taxonomy_path):
            taxonomy_documents = SimpleDirectoryReader(taxonomy_path).load_data()
            logger.info("[INDEX] Loaded %d taxonomy docs", len(taxonomy_documents))
        else:
            logger.warning("[INDEX] No taxonomy folder at %s — skipping", taxonomy_path)
            taxonomy_documents = []

        # Tag by category
        for doc in confluence_documents:
            page_id = doc.metadata.get("page_id", "")
            if page_id in DMPQL_CONFLUENCE_PAGE_IDS:
                doc.metadata["category"] = "syntax"
            else:
                doc.metadata["category"] = "general"

        for doc in dmpql_documents:
            doc.metadata["category"] = "syntax"

        for doc in taxonomy_documents:
            doc.metadata["category"] = "taxonomy"

        # Parse taxonomy
        md_parser = MarkdownNodeParser()
        taxonomy_nodes = md_parser.get_nodes_from_documents(taxonomy_documents)
        for n in taxonomy_nodes:
            n.metadata["category"] = "taxonomy"
        logger.info("[INDEX] Taxonomy split into %d nodes", len(taxonomy_nodes))

        # Clean confluence docs
        documents = confluence_documents + dmpql_documents
        for doc in documents:
            cleaned = re.sub(r'!\[.*?\]\(.*?\)', '', doc.get_content())
            cleaned = re.sub(r'\[]\(.*?\)', '', cleaned)
            doc.set_content(cleaned)

        # Build index
        logger.info("[INDEX] Indexing %d pages + %d taxonomy nodes...", len(documents), len(taxonomy_nodes))
        storage_context = StorageContext.from_defaults(vector_store=vector_store)
        index = VectorStoreIndex.from_documents(
            documents,
            storage_context=storage_context,
            store_nodes_override=True,  # force docstore population (ChromaVectorStore.stores_text=True skips it otherwise)
        )
        index.insert_nodes(taxonomy_nodes)

        tax_count = sum(
            1 for doc in index.docstore.docs.values()
            if doc.metadata.get("category") == "taxonomy"
        )
        logger.info("[INDEX] Taxonomy nodes in docstore: %d", tax_count)

        # Persist docstore so warm restarts can rebuild BM25
        index.storage_context.persist(persist_dir=PERSIST_DIR)
        logger.info("[INDEX] Docstore persisted to %s", PERSIST_DIR)
    else:
        logger.info("[INDEX] Using existing index (%d chunks)", collection.count())
        # Load persisted docstore alongside ChromaDB vector store
        storage_context = StorageContext.from_defaults(
            vector_store=vector_store,
            persist_dir=PERSIST_DIR,
        )
        index = VectorStoreIndex(
            nodes=[],
            storage_context=storage_context,
            store_nodes_override=True,
        )

    # Build retriever — always hybrid (docstore is always available now)
    vector_retriever = index.as_retriever(similarity_top_k=30)

    all_nodes = list(index.docstore.docs.values())
    logger.info("[INDEX] Docstore has %d nodes for BM25", len(all_nodes))
    bm25_retriever = BM25Retriever.from_defaults(nodes=all_nodes, similarity_top_k=30)
    hybrid_retriever = QueryFusionRetriever(
        retrievers=[vector_retriever, bm25_retriever],
        num_queries=2,
        similarity_top_k=30,
    )
    logger.info("[INDEX] Hybrid retriever (vector + BM25) ready")

    reranker = SentenceTransformerRerank(top_n=8, model=RANK_MODEL)

    engine = RetrieverQueryEngine.from_args(
        retriever=hybrid_retriever,
        node_postprocessors=[reranker],
        response_mode=ResponseMode.COMPACT,
        text_qa_template=DOCS_QA_PROMPT,
    )

    # List ALL collections
    collections = db.list_collections()
    for c in collections:
        col = db.get_collection(c.name)
        print(f"'{c.name}': {col.count()} docs")
        data = col.get(limit=5, include=["documents", "embeddings"])
        print(f"Docs in ChromaDB: {len(data['ids'])}")

    elapsed = time.time() - t0
    logger.info("[INDEX] Engine ready in %.1fs ✅", elapsed)
    return engine, index


# ═════════════════════════════════════════════════════════════════
# TELEGRAM HANDLERS
# ═════════════════════════════════════════════════════════════════

async def on_post_init(app: Application) -> None:
    """Called once at startup. Builds the RAG engine."""
    result = build_engine()
    if result is None:
        logger.error("[INIT] Engine build failed — check env variables")
        return
    engine, index = result
    app.bot_data["engine"] = engine
    app.bot_data["index"] = index
    logger.info("[INIT] Bot ready ✅")


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.message is None:
        return
    await update.message.reply_text(
        "Привет! Я помощник по документации CDJ.\n\n"
        "Задай вопрос текстом — я найду ответ в документации.\n"
        "Команда /generate — составить DMPQL запрос."
    )


async def on_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handles all text messages and /generate command."""
    if update.message is None or update.effective_user is None:
        return

    engine = cast(RetrieverQueryEngine, context.bot_data.get("engine"))
    index = cast(VectorStoreIndex, context.bot_data.get("index"))

    if engine is None or index is None:
        await update.message.reply_text("⏳ Загружается, попробуйте через минуту.")
        return

    question = update.message.text
    if not question:
        return

    user_id = update.effective_user.id
    msg_start = time.time()
    logger.info("[MESSAGE] User %d: '%s'", user_id, question[:100])

    # Strip /generate prefix
    is_generate_command = question.startswith("/generate")
    if is_generate_command:
        question = question[len("/generate"):].strip()
        if not question:
            await update.message.reply_text(
                "Напишите задачу после /generate.\n"
                "Пример: /generate сегмент мужчин с покупками за 60 дней"
            )
            return

    try:
        await update.message.chat.send_action("typing")
    except Exception:
        pass

    try:
        # Single LLM call: rewrite + route + extract search terms
        history = chat_history[user_id][-5:]
        analysis = ai_analyze_query(question, history, force_generate=is_generate_command)

        if analysis["intent"] == "GENERATE":
            logger.info("[MESSAGE] → DMPQL AI Pipeline")
            answer = await generate_dmpql(analysis["query"], analysis, index)
        else:
            logger.info("[MESSAGE] → Docs RAG Engine")
            t0 = time.time()
            response = engine.query(analysis["query"])
            logger.info("[MESSAGE] Engine query: %.1fs", time.time() - t0)

            answer = str(response).strip()

            if not answer:
                answer = "В документации этой информации нет."
            else:
                sources = set()
                for node in response.source_nodes:
                    name = node.metadata.get("title", "unknown")
                    sources.add(name)
                if sources:
                    sources_str = "📎 " + ", ".join(sources)
                    answer = f"{answer}\n\n{sources_str}"

        # Save to history
        clean_answer = answer.split("📎")[0].strip().replace("\n", " ")[:500]

        # Telegram 4096 char limit
        if len(answer) > 4000:
            for i in range(0, len(answer), 4000):
                await update.message.reply_text(answer[i : i + 4000])
        else:
            await update.message.reply_text(answer)

        chat_history[user_id].append(f"User: {question}")
        chat_history[user_id].append(f"Bot: {clean_answer}")

        elapsed = time.time() - msg_start
        logger.info("[MESSAGE] Reply sent (%d chars, %.1fs total)", len(answer), elapsed)

    except Exception as e:
        logger.error("[MESSAGE] Error: %s", e, exc_info=True)
        await update.message.reply_text("Что-то пошло не так. Попробуйте позже.")


# ═════════════════════════════════════════════════════════════════
# MAIN
# ═════════════════════════════════════════════════════════════════

def main() -> None:
    logger.info("Starting Telegram RAG Bot...")
    token = os.getenv("TELEGRAM_BOT_TOKEN")

    if not token:
        logger.error("TELEGRAM_BOT_TOKEN not set")
        return

    application = (
        Application
        .builder()
        .token(token)
        .post_init(on_post_init)
        .read_timeout(120)       # waiting for Telegram's response
        .write_timeout(120)      # sending data to Telegram
        .connect_timeout(30)    # establishing connection
        .pool_timeout(30)       # waiting for a connection from the pool
        .rate_limiter(AIORateLimiter())
        .build()
    )

    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("generate", on_message))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_message))

    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
