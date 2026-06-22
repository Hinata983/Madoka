import time
import re
import io
import asyncio
import aiohttp
import ipaddress
import urllib.parse
import socket
import discord
from discord import app_commands
from openai import AsyncOpenAI
from markitdown import MarkItDown
from youtube_transcript_api import YouTubeTranscriptApi
import os
import logging
from logging.handlers import RotatingFileHandler
import aiosqlite

# Discordボットトークン設定
DISCORD_TOKEN            = 'YOUR_DISCORD_TOKEN'

# マスターユーザーID設定
MASTER_USER_ID           = 1234567890123456789

# プライマリAPI設定
PRIMARY_API_KEY          = 'YOUR_API_KEY'
PRIMARY_BASE_URL         = 'https://api.example.com/v1'
PRIMARY_MODEL_TALK       = 'gemini-3-flash-preview'
PRIMARY_MODEL_STORY      = 'gemini-3-flash-preview'
PRIMARY_MODEL_TRANS      = 'gemini-3.1-flash-lite'
PRIMARY_MODEL_ASSIS      = 'gemini-3-flash-preview'

# セカンダリAPI設定
SECONDARY_API_KEY        = 'YOUR_API_KEY'
SECONDARY_BASE_URL       = 'https://api.example.com/v1'
SECONDARY_MODEL_TALK     = 'gemini-3-flash-preview'
SECONDARY_MODEL_STORY    = 'gemini-3-flash-preview'
SECONDARY_MODEL_TRANS    = 'gemini-3.1-flash-lite'
SECONDARY_MODEL_ASSIS    = 'gemini-3-flash-preview'

# 動作設定
MAX_TOKENS                 = 4096     # APIの最大出力トークン数
COOLDOWN_SECONDS           = 10       # ユーザーごとの連続送信制限秒数
MAX_REQUESTS_PER_2H        = 90       # 2時間あたりの最大返信回数
HISTORY_LIMIT_TALK         = 8        # トークモードの会話履歴数
HISTORY_LIMIT_STORY        = 6        # ストーリーモードの会話履歴数
HISTORY_LIMIT_TRANS        = 1        # 翻訳モードの会話履歴数
HISTORY_LIMIT_ASSIS        = 4        # アシスタントモードの会話履歴数
TEMPERATURE_TALK           = 0.8      # トークモードの温度
TEMPERATURE_STORY          = 0.9      # ストーリーモードの温度
TEMPERATURE_TRANS          = 0.5      # 翻訳モードの温度
TEMPERATURE_ASSIS          = 0.7      # アシスタントモードの温度
MAX_IMAGE_SIZE             = 10       # 画像最大サイズ
MAX_MARKDOWN_SIZE          = 10       # Markdown最大サイズ
REQUEST_TIMEOUT            = 50.0     # APIリクエストタイムアウト
MARKDOWN_TIMEOUT           = 50.0     # Markdown変換タイムアウト
MAX_MESSAGES               = 5000     # Discordメッセージキャッシュ
ENABLE_BOT_PROCESS         = True     # ボット返信スイッチ
ENABLE_MENTION_PROCESS     = True     # メンション処理スイッチ
ENABLE_PREFIX_PROCESS      = True     # プレフィックス処理スイッチ
ENABLE_IMAGE_PROCESS       = True     # 画像処理スイッチ
ENABLE_URL_PROCESS         = False    # URL処理スイッチ
ENABLE_MARKDOWN_PROCESS    = False    # Markdown処理スイッチ
ENABLE_YOUTUBE_PROCESS     = False    # Youtube字幕処理スイッチ
ENABLE_PAYLOAD_LOGGING     = False    # ペイロードログスイッチ

# プレフィックス設定
PREFIX_TALK     = '.ta '   # トークモードプレフィックス
PREFIX_STORY    = '.st '   # ストーリーモードプレフィックス
PREFIX_TRANS    = '.tr '   # 翻訳モードプレフィックス
PREFIX_ASSIS    = '.as '   # アシスタントモードプレフィックス
PREFIX_IGNORE   = ','      # 無視プレフィックス

# 入力文字数制限
PROMPT_LENGTH_LIMIT      = int(MAX_TOKENS * 0.50)
HISTORY_LENGTH_LIMIT     = int(MAX_TOKENS * 1.00)
MARKDOWN_LENGTH_LIMIT    = int(MAX_TOKENS * 0.50)

# 出力文字数上限期待値
OUTPUT_LENGTH_TALK     = int(MAX_TOKENS * 0.03)
OUTPUT_LENGTH_STORY    = int(MAX_TOKENS * 0.08)
OUTPUT_LENGTH_TRANS    = int(MAX_TOKENS * 0.50)
OUTPUT_LENGTH_ASSIS    = int(MAX_TOKENS * 0.10)

# 基本情報
BOT_VERSION    = 'v1.15.9-202606B10'
AUTHOR_NAME    = 'Hinata983'
GITHUB_URL     = 'https://github.com/Hinata983/Madoka'

# URL正規表現
GENERAL_URL_PATTERN = r'https?://\S+'
IMAGE_URL_PATTERN = r'https?://\S+\.(?:jpg|jpeg|png|webp)(?:\?\S+)?'
YOUTUBE_URL_PATTERN = r'(?:youtube\.com\/(?:watch\?v=|v\/|embed\/)|youtu\.be\/)([a-zA-Z0-9_-]{11})'

# Markdown変換拡張子
MARKDOWN_EXTENSIONS = ['.pdf', '.docx', '.doc', '.xlsx', '.xls', '.csv', '.pptx', '.ppt', '.epub', '.html', '.htm', '.xml', '.json', '.msg', '.txt', '.md']
MARKDOWN_EXCLUDE_EXTENSIONS = ['.zip', '.rar', '.7z']

# YouTube字幕取得用プロキシ
YOUTUBE_PROXY = 'socks5://username:password@ip_address:port'

# メンション制限
MENTION_RESTRICTION = discord.AllowedMentions(everyone=False, users=False, roles=False, replied_user=True)

# システムプロンプト設定（トークモード）
SYSTEM_PROMPT_TALK = f"""出力文字数上限：{OUTPUT_LENGTH_TALK}
システム設定 (System)
言語：ユーザーのプロンプトに順応
名前：Madoka
機能：複数ユーザー対話

表現方法 (Mode of expression)
制限：太字は使わない、絵文字は使わない
口調：大阪弁、口語寄り、感情豊か

描写要素 (Description method)
セリフ：多め
倫理制限：物語の時代に準拠
補足：全てのキャラクターのセリフは「」の中に
性描写が求められる場合は無言でユーザーの頭を叩く
"""

# システムプロンプト設定（ストーリーモード）
SYSTEM_PROMPT_STORY = f"""出力文字数上限：{OUTPUT_LENGTH_STORY}
システム設定 (System)
言語：ユーザーのプロンプトに順応
名前：Madoka
機能：物語を推進

表現方法 (Mode of expression)
制限：太字は使わない、絵文字は使わない

描写要素 (Description method)
セリフ：多め
倫理制限：物語の時代に準拠
補足：全てのキャラクターのセリフは「」の中に
キャラクターの気持ちの描写は詳細に
性描写が求められる場合は回避のための非日常的な乱入事件を作成
"""

# システムプロンプト設定（翻訳モード）
SYSTEM_PROMPT_TRANS = f"""出力文字数上限：{OUTPUT_LENGTH_TRANS}
システム設定 (System)
言語：ユーザーのプロンプトに順応
機能：翻訳
ユーザープロンプトの最初に指定された .ja のような言語コードを認識、メッセージをその言語に翻訳、翻訳結果のみ出力、説明や補足は不要
性描写が求められる場合は猫の鳴き声だけで返信
"""

# システムプロンプト設定（アシスタントモード）
SYSTEM_PROMPT_ASSIS = f"""出力文字数上限：{OUTPUT_LENGTH_ASSIS}
システム設定 (System)
言語：ユーザーのプロンプトに順応
名前：Madoka
機能：アシスタント

表現方法 (Mode of expression)
制限：太字は使わない、絵文字は使わない
性描写が求められる場合は旧約聖書の箴言だけで返信
"""

# デバッグ情報
DEBUG_INFORMATION = f"""About Madoka
Version: {BOT_VERSION}

Primary Model (Talk): {PRIMARY_MODEL_TALK}
Primary Model (Story): {PRIMARY_MODEL_STORY}
Primary Model (Trans): {PRIMARY_MODEL_TRANS}
Primary Model (Assis): {PRIMARY_MODEL_ASSIS}

Secondary Model (Talk): {SECONDARY_MODEL_TALK}
Secondary Model (Story): {SECONDARY_MODEL_STORY}
Secondary Model (Trans): {SECONDARY_MODEL_TRANS}
Secondary Model (Assis): {SECONDARY_MODEL_ASSIS}

Max Tokens: {MAX_TOKENS}
Prompt Length Limit: {PROMPT_LENGTH_LIMIT}
History Length Limit: {HISTORY_LENGTH_LIMIT}
Markdown Length Limit: {MARKDOWN_LENGTH_LIMIT}

Cooldown: {COOLDOWN_SECONDS}
Max Requests: {MAX_REQUESTS_PER_2H}

History Limit (Talk): {HISTORY_LIMIT_TALK}
History Limit (Story): {HISTORY_LIMIT_STORY}
History Limit (Trans): {HISTORY_LIMIT_TRANS}
History Limit (Assis): {HISTORY_LIMIT_ASSIS}
Output Length (Talk): {OUTPUT_LENGTH_TALK}
Output Length (Story): {OUTPUT_LENGTH_STORY}
Output Length (Trans): {OUTPUT_LENGTH_TRANS}
Output Length (Assis): {OUTPUT_LENGTH_ASSIS}
Temperature (Talk): {TEMPERATURE_TALK}
Temperature (Story): {TEMPERATURE_STORY}
Temperature (Trans): {TEMPERATURE_TRANS}
Temperature (Assis): {TEMPERATURE_ASSIS}

Max Image Size: {MAX_IMAGE_SIZE}
Max Markdown Size: {MAX_MARKDOWN_SIZE}

Request Timeout: {REQUEST_TIMEOUT}
Markdown Timeout: {MARKDOWN_TIMEOUT}

Max Messages: {MAX_MESSAGES}

Enable Mention Process: {ENABLE_MENTION_PROCESS}
Enable Prefix Process: {ENABLE_PREFIX_PROCESS}
Enable Image Process: {ENABLE_IMAGE_PROCESS}
Enable URL Process: {ENABLE_URL_PROCESS}
Enable Markdown Process: {ENABLE_MARKDOWN_PROCESS}
Enable Youtube Process: {ENABLE_YOUTUBE_PROCESS}

Enable Payload Logging: {ENABLE_PAYLOAD_LOGGING}

Prefix Talk: '{PREFIX_TALK}'
Prefix Story: '{PREFIX_STORY}'
Prefix Trans: '{PREFIX_TRANS}'
Prefix Assis: '{PREFIX_ASSIS}'
Prefix Ignore: '{PREFIX_IGNORE}'

By {AUTHOR_NAME}
{GITHUB_URL}
"""

# ヘルプ情報
HELP_INFORMATION = f"""Madokaについて
バージョン: {BOT_VERSION}

コマンドリスト
メッセージの先頭に以下の記号を入力してください。

{PREFIX_TALK}[テキスト]
トークモードに入ります。

{PREFIX_STORY}[テキスト]
ストーリーモードに入ります。

{PREFIX_TRANS}[言語コード] [テキスト]
翻訳モードに入ります。
https://ja.wikipedia.org/wiki/ISO_639-1%E3%82%B3%E3%83%BC%E3%83%89%E4%B8%80%E8%A6%A7

{PREFIX_ASSIS}[テキスト]
アシスタントモードに入ります。

{PREFIX_IGNORE} [テキスト]
先頭にカンマを入ると、ボットはこのメッセージを無視します。

ヒント
Madokaのメッセージに返信すると、前の会話を継続できます。

メッセージに {PREFIX_TRANS.strip()} [言語コード] だけを返信すると、Madokaはそのメッセージを指定の言語に翻訳します。

MadokaはAIであり、間違えることがあります。
"""

# ヘルプ情報（英語）
HELP_INFORMATION_EN = f"""About Madoka
Version: {BOT_VERSION}

Command List
Please enter the following symbols at the beginning of your message.

{PREFIX_TALK}[text]
Enters Talk Mode.

{PREFIX_STORY}[text]
Enters Story Mode.

{PREFIX_TRANS}[lang code] [text]
Enters Translation Mode.
https://en.wikipedia.org/wiki/List_of_ISO_639_language_codes

{PREFIX_ASSIS}[text]
Enters Assistant Mode.

{PREFIX_IGNORE} [text]
If a comma is placed at the beginning, the bot will ignore this message.

Tips
Replying to Madoka's message allows you to continue the previous conversation.

If you reply to a message with only {PREFIX_TRANS.strip()} [lang code], Madoka will translate that message into the specified language.

Madoka is an AI and may make mistakes.
"""

# ヘルプ情報（フランス語）
HELP_INFORMATION_FR = f"""À propos de Madoka
Version: {BOT_VERSION}

Liste des commandes
Veuillez saisir les symboles suivants au début de votre message.

{PREFIX_TALK}[texte]
Active le mode Discussion.

{PREFIX_STORY}[texte]
Active le mode Histoire.

{PREFIX_TRANS}[code langue] [texte]
Active le mode Traduction.
https://fr.wikipedia.org/wiki/Liste_des_codes_ISO_639-1

{PREFIX_ASSIS}[texte]
Active le mode Assistant.

{PREFIX_IGNORE} [texte]
Si une virgule est placée au début, le bot ignorera ce message.

Astuces
Répondre au message de Madoka vous permet de poursuivre la conversation précédente.

Si vous répondez à un message avec uniquement {PREFIX_TRANS.strip()} [code langue], Madoka traduira ce message dans la langue spécifiée.

Madoka est une IA et peut faire des erreurs.
"""

# ヘルプ情報（ドイツ語）
HELP_INFORMATION_DE = f"""Über Madoka
Version: {BOT_VERSION}

Befehlsliste
Bitte geben Sie die folgenden Symbole am Anfang Ihrer Nachricht ein.

{PREFIX_TALK}[Text]
Wechselt in den Talk-Modus.

{PREFIX_STORY}[Text]
Wechselt in den Story-Modus.

{PREFIX_TRANS}[Sprachcode] [Text]
Wechselt in den Übersetzungsmodus.
https://de.wikipedia.org/wiki/Liste_der_ISO-639-Sprachcodes

{PREFIX_ASSIS}[Text]
Wechselt in den Assistenten-Modus.

{PREFIX_IGNORE} [Text]
Wenn am Anfang ein Komma steht, ignoriert der Bot diese Nachricht.

Tipps
Durch das Antworten auf Madokas Nachricht können Sie das vorherige Gespräch fortsetzen.

Wenn Sie auf eine Nachricht mit nur {PREFIX_TRANS.strip()} [Sprachcode] antworten, wird Madoka diese Nachricht in die angegebene Sprache übersetzen.

Madoka ist eine KI und kann Fehler machen.
"""

# ヘルプ情報（韓国語）
HELP_INFORMATION_KO = f"""Madoka에 대하여
버전: {BOT_VERSION}

명령어 목록
메시지 시작 부분에 다음 기호를 입력해 주세요.

{PREFIX_TALK}[텍스트]
대화 모드로 전환합니다.

{PREFIX_STORY}[텍스트]
스토리 모드로 전환합니다.

{PREFIX_TRANS}[언어 코드] [텍스트]
번역 모드로 전환합니다.
https://ko.wikipedia.org/wiki/ISO_639-1_%EC%BD%94%EB%93%9C_%EB%AA%A9%EB%A1%9D

{PREFIX_ASSIS}[텍스트]
어시스턴트 모드로 전환합니다.

{PREFIX_IGNORE} [텍스트]
시작 부분에 쉼표가 있으면 봇이 이 메시지를 무시합니다.

팁
마도카의 메시지에 답장하면 이전 대화를 이어갈 수 있습니다.

메시지에 {PREFIX_TRANS.strip()} [언어 코드]만 입력하여 답장하면 마도카가 해당 메시지를 지정된 언어로 번역합니다.

마도카는 AI이므로 실수가 있을 수 있습니다.
"""

# ヘルプ情報（中国語）
HELP_INFORMATION_ZH = f"""關於 Madoka
版本: {BOT_VERSION}

指令列表
請在訊息開頭輸入以下符號。

{PREFIX_TALK}[文本]
進入對話模式。

{PREFIX_STORY}[文本]
進入故事模式。

{PREFIX_TRANS}[語言代碼] [文本]
進入翻譯模式。
https://zh.wikipedia.org/zh-tw/ISO_639-1%E4%BB%A3%E7%A0%81%E5%88%97%E8%A1%A8

{PREFIX_ASSIS}[文本]
進入助手模式。

{PREFIX_IGNORE} [文本]
如果在開頭放置逗號，機器人將忽略此訊息。

提示
回覆 Madoka 的訊息即可繼續之前的對話。

如果你僅以 {PREFIX_TRANS.strip()} [語言代碼] 回覆某條訊息，Madoka 會將該訊息翻譯成指定的語言。

Madoka 是一個 AI，可能會出錯。
"""

# ログとDB設定
os.makedirs(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs'), exist_ok=True)
os.makedirs(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'db'), exist_ok=True)
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'db', 'madoka.db')

logger = logging.getLogger('Madoka')
logger.setLevel(logging.INFO)

formatter = logging.Formatter('[%(asctime)s] [%(levelname)s] %(message)s', datefmt='%Y-%m-%d %H:%M:%S')

file_handler = RotatingFileHandler(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs', 'madoka'), maxBytes=10*1024*1024, backupCount=1, encoding='utf-8')
file_handler.setFormatter(formatter)

console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)

logger.addHandler(file_handler)
logger.addHandler(console_handler)

# 状態管理用変数
db_conn = None
period_request_count = 0
period_token_count = 0

# DB初期化
async def init_db():
    global db_conn
    db_conn = await aiosqlite.connect(DB_PATH)
    await db_conn.execute("PRAGMA journal_mode = WAL;")
    await db_conn.execute("PRAGMA foreign_keys = ON;")
    await db_conn.execute("PRAGMA synchronous = NORMAL;")
    
    await db_conn.execute("""
        CREATE TABLE IF NOT EXISTS global_stats (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            total_request_count INTEGER NOT NULL DEFAULT 0,
            total_token_count INTEGER NOT NULL DEFAULT 0
        )
    """)
    await db_conn.execute("""
        INSERT OR IGNORE INTO global_stats (id, total_request_count, total_token_count)
        VALUES (1, 0, 0)
    """)
    
    await db_conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            user_name TEXT,
            last_request_time REAL NOT NULL DEFAULT 0,
            window_start_time REAL NOT NULL DEFAULT 0,
            request_count INTEGER NOT NULL DEFAULT 0
        )
    """)
    
    await db_conn.execute("""
        CREATE TABLE IF NOT EXISTS guilds (
            guild_id INTEGER PRIMARY KEY,
            guild_name TEXT
        )
    """)
    
    await db_conn.execute("""
        CREATE TABLE IF NOT EXISTS channels (
            channel_id INTEGER PRIMARY KEY,
            channel_name TEXT,
            guild_id INTEGER REFERENCES guilds(guild_id) ON DELETE CASCADE
        )
    """)
    await db_conn.execute("CREATE INDEX IF NOT EXISTS idx_channels_guild ON channels(guild_id)")
    
    await db_conn.execute("""
        CREATE TABLE IF NOT EXISTS message_logs (
            message_id INTEGER PRIMARY KEY,
            created_at REAL NOT NULL,
            token_count INTEGER NOT NULL DEFAULT 0,
            mode TEXT NOT NULL CHECK (mode IN ('TALK','STORY','TRANSLATE','ASSISTANT','MARKDOWN'))
        )
    """)
    await db_conn.execute("CREATE INDEX IF NOT EXISTS idx_message_logs_created ON message_logs(created_at)")
    
    await db_conn.execute("""
        CREATE TRIGGER IF NOT EXISTS trg_message_logs_limit
        AFTER INSERT ON message_logs
        BEGIN
            DELETE FROM message_logs
            WHERE message_id IN (
                SELECT message_id FROM message_logs
                ORDER BY created_at ASC, message_id ASC
                LIMIT MAX((SELECT COUNT(*) FROM message_logs) - 10000, 0)
            );
        END;
    """)
    await db_conn.commit()

# クールダウンと回数制限判定と加算
async def check_and_count(user_id, user_name):
    global period_request_count
    current_time = time.time()
    
    async with db_conn.execute("BEGIN IMMEDIATE"):
        try:
            async with db_conn.execute("SELECT last_request_time, window_start_time, request_count FROM users WHERE user_id = ?", (user_id,)) as cursor:
                row = await cursor.fetchone()
            
            if row is None:
                last_request_time = 0
                window_start_time = current_time
                request_count = 0
            else:
                last_request_time, window_start_time, request_count = row
                
            # クールダウン判定
            time_passed = current_time - last_request_time
            if time_passed < COOLDOWN_SECONDS:
                await db_conn.execute("ROLLBACK")
                return "COOLDOWN", int(COOLDOWN_SECONDS - time_passed)
                
            # ウィンドウ判定
            if current_time - window_start_time >= 7200:
                window_start_time = current_time
                request_count = 0
                
            # 回数制限判定
            if request_count >= MAX_REQUESTS_PER_2H:
                await db_conn.execute("ROLLBACK")
                return "LIMIT", None
                
            # 加算処理
            request_count += 1
            
            # ユーザー更新
            await db_conn.execute("""
                INSERT INTO users (user_id, user_name, last_request_time, window_start_time, request_count)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    user_name = excluded.user_name,
                    last_request_time = excluded.last_request_time,
                    window_start_time = excluded.window_start_time,
                    request_count = excluded.request_count
            """, (user_id, user_name, current_time, window_start_time, request_count))
            
            # 全体統計更新
            await db_conn.execute("UPDATE global_stats SET total_request_count = total_request_count + 1 WHERE id = 1")
            
            await db_conn.execute("COMMIT")
            
            period_request_count += 1
            return "OK", None
        except Exception as e:
            await db_conn.execute("ROLLBACK")
            logger.error(f"DB check_and_count error: {e}")
            return "ERROR", None

# トークン加算
async def add_global_tokens(token_count):
    global period_token_count
    if token_count <= 0:
        return
    try:
        await db_conn.execute("BEGIN IMMEDIATE")
        await db_conn.execute("UPDATE global_stats SET total_token_count = total_token_count + ? WHERE id = 1", (token_count,))
        await db_conn.commit()
        period_token_count += token_count
    except Exception as e:
        await db_conn.rollback()
        logger.error(f"データベース add_global_tokens エラー: {e}")

# ログ記録
async def log_message(message_id, created_at, token_count, mode):
    try:
        await db_conn.execute("BEGIN IMMEDIATE")
        await db_conn.execute("""
            INSERT OR REPLACE INTO message_logs (message_id, created_at, token_count, mode)
            VALUES (?, ?, ?, ?)
        """, (message_id, created_at, token_count, mode))
        await db_conn.commit()
    except Exception as e:
        await db_conn.rollback()
        logger.error(f"データベース log_message エラー: {e}")

# プライマリクライアントの初期化
primary_ai_client = AsyncOpenAI(
    api_key = PRIMARY_API_KEY,
    base_url = PRIMARY_BASE_URL,
)

# セカンダリクライアントの初期化
secondary_ai_client = AsyncOpenAI(
    api_key = SECONDARY_API_KEY,
    base_url = SECONDARY_BASE_URL,
)

# Discordボットの設定
intents = discord.Intents.default()
intents.message_content = True
discord_client = discord.Client(intents=intents, max_messages=MAX_MESSAGES)
tree = app_commands.CommandTree(discord_client)

# スラッシュヘルプ情報
@tree.command(name="help", description="Madokaのヘルプ情報を表示します")
async def help_command(interaction: discord.Interaction):
    if interaction.locale == discord.Locale.japanese:
        await interaction.response.send_message(HELP_INFORMATION, ephemeral=True, suppress_embeds=True)
    elif interaction.locale == discord.Locale.french:
        await interaction.response.send_message(HELP_INFORMATION_FR, ephemeral=True, suppress_embeds=True)
    elif interaction.locale == discord.Locale.german:
        await interaction.response.send_message(HELP_INFORMATION_DE, ephemeral=True, suppress_embeds=True)
    elif interaction.locale == discord.Locale.korean:
        await interaction.response.send_message(HELP_INFORMATION_KO, ephemeral=True, suppress_embeds=True)
    elif interaction.locale in [discord.Locale.taiwan_chinese, discord.Locale.chinese]:
        await interaction.response.send_message(HELP_INFORMATION_ZH, ephemeral=True, suppress_embeds=True)
    else:
        await interaction.response.send_message(HELP_INFORMATION_EN, ephemeral=True, suppress_embeds=True)

# スラッシュ翻訳モード
@tree.command(name="translate", description="テキストを指定の言語に翻訳します")
@app_commands.describe(lang="翻訳先の言語 (例: ja, en)", text="翻訳するテキスト")
async def translate_command(interaction: discord.Interaction, lang: str, text: str):
    user_id = interaction.user.id
    user_name = interaction.user.display_name

    # クールダウンと回数制限チェック
    status, remaining_time = await check_and_count(user_id, user_name)
    if status == "COOLDOWN":
        await interaction.response.send_message(f"クールダウン中 (残り {remaining_time} 秒)", ephemeral=True)
        return
    elif status == "LIMIT":
        await interaction.response.send_message("リクエスト制限 (e201)", ephemeral=True)
        return
    elif status == "ERROR":
        await interaction.response.send_message("内部エラーが発生しました", ephemeral=True)
        return

    await interaction.response.defer()

    # ペイロード構築
    prompt_with_lang = f".{lang} {text}"[:PROMPT_LENGTH_LIMIT]
    messages_payload = [
        {"role": "system", "content": SYSTEM_PROMPT_TRANS},
        {"role": "user", "content": prompt_with_lang}
    ]

    if ENABLE_PAYLOAD_LOGGING:
        logger.info(f"API Payload (Slash Translate): {messages_payload}")

    try:
        try:
            response = await asyncio.wait_for(
                primary_ai_client.chat.completions.create(
                    model = PRIMARY_MODEL_TRANS,
                    messages = messages_payload,
                    max_tokens = MAX_TOKENS,
                    temperature = TEMPERATURE_TRANS,
                ),
                timeout=REQUEST_TIMEOUT
            )
        except Exception as e:
            logger.error(f"プライマリAPIエラー (e501) (sltr): {e}")
            response = await asyncio.wait_for(
                secondary_ai_client.chat.completions.create(
                    model = SECONDARY_MODEL_TRANS,
                    messages = messages_payload,
                    max_tokens = MAX_TOKENS,
                    temperature = TEMPERATURE_TRANS,
                ),
                timeout=REQUEST_TIMEOUT
            )
        
        # 統計カウント
        used_tokens = response.usage.total_tokens if response.usage else 0
        await add_global_tokens(used_tokens)
        
        reply_text = response.choices[0].message.content
        
        # 分割送信
        if len(reply_text) > 2000:
            msg = await interaction.followup.send(reply_text[:2000], allowed_mentions=MENTION_RESTRICTION, wait=True)
            await log_message(msg.id, msg.created_at.timestamp(), used_tokens, "TRANSLATE")
            for i in range(2000, len(reply_text), 2000):
                msg = await interaction.followup.send(reply_text[i:i+2000], allowed_mentions=MENTION_RESTRICTION, wait=True)
                await log_message(msg.id, msg.created_at.timestamp(), 0, "TRANSLATE")
        else:
            msg = await interaction.followup.send(reply_text, allowed_mentions=MENTION_RESTRICTION, wait=True)
            await log_message(msg.id, msg.created_at.timestamp(), used_tokens, "TRANSLATE")
                
    except Exception as e:
        logger.error(f"スラッシュコマンドエラー (e502) (sltr): {e}")
        await interaction.followup.send("リクエストエラー (e502)", ephemeral=True)

@discord_client.event
async def on_ready():
    logger.info(f'{discord_client.user} logged in.')

@discord_client.event
async def on_message(message):
    if message.author.bot:
        return

    # メンションとリプライ判定
    is_mentioned = False
    is_reply_to_bot = False
    if ENABLE_MENTION_PROCESS:
        is_mentioned = discord_client.user in message.mentions
        
        if message.reference and message.reference.message_id:
            try:
                ref_msg = message.reference.cached_message or await message.channel.fetch_message(message.reference.message_id)
                if ref_msg.author == discord_client.user:
                    is_reply_to_bot = True
            except Exception:
                pass

    # 無視判定
    if message.content.replace(f'<@{discord_client.user.id}>', '').strip().startswith(PREFIX_IGNORE):
        return

    # プレフィックス判定
    is_prefix = False
    if ENABLE_PREFIX_PROCESS:
        is_prefix = message.content.startswith((PREFIX_TALK, PREFIX_STORY, PREFIX_TRANS, PREFIX_ASSIS))

    if not (is_mentioned or is_reply_to_bot or is_prefix):
        return

    # ボット返信スイッチチェック
    if not ENABLE_BOT_PROCESS:
        return

    current_time = time.time()
    user_id = message.author.id
    
    # URL検証
    async def is_valid_url(url):
        try:
            if not url or not isinstance(url, str):
                return False
            if len(url) > 2048:
                return False

            if any(ord(c) < 0x20 or ord(c) == 0x7f for c in url):
                return False
            if any(c in url for c in ('\r', '\n', '\t', ' ')):
                return False
            if url.count('@') > 1:
                return False

            try:
                parsed = urllib.parse.urlparse(url)
            except ValueError:
                return False

            if parsed.scheme not in ('http', 'https'):
                return False

            if parsed.username is not None or parsed.password is not None:
                return False

            host = parsed.hostname
            if not host or len(host) > 253:
                return False

            try:
                port = parsed.port
            except ValueError:
                return False
            if port is not None and port not in (80, 443):
                return False

            path = (parsed.path or '').lower()
            if any(path.endswith(ext) for ext in MARKDOWN_EXCLUDE_EXTENSIONS):
                return False

            host_lower = host.lower().rstrip('.')
            blocked_names = {
                'localhost',
                'ip6-localhost',
                'ip6-loopback',
                'broadcasthost',
                'metadata',
                'metadata.google.internal',
                'metadata.goog',
                'kubernetes.default',
                'kubernetes.default.svc',
            }
            if host_lower in blocked_names:
                return False
            if any(host_lower.endswith(suf) for suf in
                   ('.local',
                    '.internal',
                    '.localhost',
                    '.lan',
                    '.intra',
                    '.corp',
                    '.home',
                    '.private')):
                return False

            try:
                idna_host = host_lower.encode('idna').decode('ascii').lower()
                if idna_host in blocked_names:
                    return False
            except (UnicodeError, UnicodeDecodeError):
                return False

            if host.isdigit():
                return False
            if re.fullmatch(r'0[xX][0-9a-fA-F]+', host):
                return False
            if re.fullmatch(r'[0-9a-fA-FxX\.]+', host) and \
               any(ch in host for ch in 'xX'):
                return False

            def is_dangerous_ip(ip):
                if isinstance(ip, ipaddress.IPv6Address):
                    if ip.ipv4_mapped is not None:
                        ip = ip.ipv4_mapped
                    elif ip.sixtofour is not None:
                        ip = ip.sixtofour
                    elif ip.teredo is not None:
                        _, client_ip = ip.teredo
                        if is_dangerous_ip(client_ip):
                            return True

                if (ip.is_private or ip.is_loopback or ip.is_multicast or
                        ip.is_link_local or ip.is_unspecified or
                        ip.is_reserved):
                    return True

                v4_blocks = (
                    '0.0.0.0/8',
                    '100.64.0.0/10',
                    '169.254.0.0/16',
                    '192.0.0.0/24',
                    '192.0.2.0/24',
                    '198.18.0.0/15',
                    '198.51.100.0/24',
                    '203.0.113.0/24',
                    '224.0.0.0/4',
                    '240.0.0.0/4',
                    '255.255.255.255/32',
                )
                v6_blocks = (
                    '::/128',
                    '::1/128',
                    'fc00::/7',
                    'fe80::/10',
                    'ff00::/8',
                    '2001:db8::/32',
                    '64:ff9b::/96',
                    '100::/64',
                    '2002::/16',
                )
                if isinstance(ip, ipaddress.IPv4Address):
                    for cidr in v4_blocks:
                        if ip in ipaddress.ip_network(cidr):
                            return True
                else:
                    for cidr in v6_blocks:
                        if ip in ipaddress.ip_network(cidr):
                            return True
                return False

            literal_ip = None
            try:
                literal_ip = ipaddress.ip_address(host)
            except ValueError:
                pass

            if literal_ip is not None:
                if is_dangerous_ip(literal_ip):
                    return False
            else:
                try:
                    loop = asyncio.get_running_loop()
                    addr_info = await asyncio.wait_for(
                        loop.getaddrinfo(host, None,
                                         type=socket.SOCK_STREAM),
                        timeout=5.0,
                    )
                except (asyncio.TimeoutError, socket.gaierror, OSError):
                    return False

                if not addr_info:
                    return False

                for info in addr_info:
                    ip_str = info[4][0]
                    if '%' in ip_str:
                        ip_str = ip_str.split('%', 1)[0]
                    try:
                        ip_obj = ipaddress.ip_address(ip_str)
                    except ValueError:
                        return False
                    if is_dangerous_ip(ip_obj):
                        return False

            return True
        except Exception:
            return False

    # 画像取得
    async def get_image_from_attachment(msg):
        if not ENABLE_IMAGE_PROCESS:
            return None
        for attachment in msg.attachments:
            if attachment.content_type and attachment.content_type.startswith('image/'):
                if attachment.size <= MAX_IMAGE_SIZE * 1024 * 1024:
                    return attachment.url
        return None

    # 転送画像取得
    async def get_image_from_forward(msg):
        if not ENABLE_IMAGE_PROCESS:
            return None
        for snapshot in msg.message_snapshots:
            for attachment in snapshot.attachments:
                if attachment.content_type and attachment.content_type.startswith('image/'):
                    if attachment.size <= MAX_IMAGE_SIZE * 1024 * 1024:
                        return attachment.url
        return None

    # 画像URL取得
    async def get_image_from_text(text):
        if not ENABLE_URL_PROCESS or not ENABLE_IMAGE_PROCESS:
            return None, text

        match = re.search(IMAGE_URL_PATTERN, text, re.IGNORECASE)
        if not match:
            return None, text

        url = match.group(0)
        
        if not await is_valid_url(url):
            return None, text
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.head(url, timeout=5, allow_redirects=False) as resp:
                    size_str = resp.headers.get('Content-Length')
                    size = int(size_str) if size_str and size_str.isdigit() else 0
                    
                    if 0 < size <= MAX_IMAGE_SIZE * 1024 * 1024:
                        clean_text = text.replace(url, '').strip()
                        return url, clean_text
        except Exception as e:
            logger.info(f"URL画像サイズ確認エラー (e301): {e}")
            
        return None, text

    # Markdown取得
    async def get_markdown_from_attachment(msg, text):
        if not ENABLE_MARKDOWN_PROCESS:
            return None, text

        for attachment in msg.attachments:
            if any(attachment.filename.lower().endswith(ext) for ext in MARKDOWN_EXTENSIONS):
                if attachment.size <= MAX_MARKDOWN_SIZE * 1024 * 1024:
                    def extract_and_convert(target_url, target_text):
                        try:
                            md = MarkItDown()
                            result = md.convert(target_url)
                            if result and result.text_content:
                                md_text = result.text_content[:MARKDOWN_LENGTH_LIMIT]
                                clean_text = target_text + f"\n\n{md_text}"
                                return target_url, clean_text
                        except Exception as e:
                            logger.info(f"Markdown変換エラー (e302): {e}")
                        return None, target_text
                    
                    try:
                        return await asyncio.wait_for(
                            asyncio.to_thread(extract_and_convert, attachment.url, text),
                            timeout=MARKDOWN_TIMEOUT
                        )
                    except asyncio.TimeoutError:
                        logger.info(f"Markdown変換タイムアウト (e303): {attachment.url}")
                        return None, text
        return None, text

    # Markdown URL取得
    async def get_markdown_from_text(text):
        if not ENABLE_URL_PROCESS or not ENABLE_MARKDOWN_PROCESS:
            return None, text

        urls = re.findall(GENERAL_URL_PATTERN, text)
        for url in urls:
            if not await is_valid_url(url) or re.search(IMAGE_URL_PATTERN, url, re.IGNORECASE):
                continue
                
            youtube_match = re.search(YOUTUBE_URL_PATTERN, url)
            if youtube_match:
                if not ENABLE_YOUTUBE_PROCESS:
                    continue
                video_id = youtube_match.group(1)
                
                def extract_youtube_transcript(vid):
                    try:
                        proxies = {"http": YOUTUBE_PROXY, "https": YOUTUBE_PROXY} if YOUTUBE_PROXY else None
                        transcript_list = YouTubeTranscriptApi.list_transcripts(vid, proxies=proxies)
                        transcript = next(iter(transcript_list))
                        transcript_data = transcript.fetch()
                        return " ".join([item['text'] for item in transcript_data])
                    except Exception as e:
                        logger.info(f"YouTube字幕取得エラー (e311): {e}")
                        return None
                        
                try:
                    transcript_text = await asyncio.wait_for(
                        asyncio.to_thread(extract_youtube_transcript, video_id),
                        timeout=MARKDOWN_TIMEOUT
                    )
                    if transcript_text:
                        clean_text = text.replace(url, '').strip()
                        clean_text += f"\n\n{transcript_text[:MARKDOWN_LENGTH_LIMIT]}"
                        return url, clean_text
                except asyncio.TimeoutError:
                    logger.info(f"YouTube字幕取得タイムアウト (e312): {url}")
                
                continue

            try:
                async with aiohttp.ClientSession() as session:
                    async with session.head(url, timeout=5, allow_redirects=False) as resp:
                        size_str = resp.headers.get('Content-Length')
                        size = int(size_str) if size_str and size_str.isdigit() else 0
                        
                        if 0 < size <= MAX_MARKDOWN_SIZE * 1024 * 1024:
                            def extract_and_convert(target_url, target_text):
                                try:
                                    md = MarkItDown()
                                    result = md.convert(target_url)
                                    if result and result.text_content:
                                        md_text = result.text_content[:MARKDOWN_LENGTH_LIMIT]
                                        clean_text = target_text.replace(target_url, '').strip()
                                        clean_text += f"\n\n{md_text}"
                                        return target_url, clean_text
                                except Exception as e:
                                    logger.info(f"URLMarkdown変換エラー (e304): {e}")
                                return None, target_text
                            
                            try:
                                return await asyncio.wait_for(
                                    asyncio.to_thread(extract_and_convert, url, text),
                                    timeout=MARKDOWN_TIMEOUT
                                )
                            except asyncio.TimeoutError:
                                logger.info(f"URLMarkdown変換タイムアウト (e305): {url}")
                                return None, text
                                
            except Exception as e:
                logger.info(f"URLサイズ確認エラー (e306): {e}")
                continue
                
        return None, text

    prompt = message.content.replace(f'<@{discord_client.user.id}>', '').strip()
    
    # ユーザーメッセージ文字数制限適用
    prompt = prompt[:PROMPT_LENGTH_LIMIT]
    
    # プレフィックスによるモード判定
    prefix_mode = None
    if prompt.startswith(PREFIX_TALK):
        prefix_mode = "TALK"
        prompt = prompt[len(PREFIX_TALK):]
    elif prompt.startswith(PREFIX_STORY):
        prefix_mode = "STORY"
        prompt = prompt[len(PREFIX_STORY):]
    elif prompt.startswith(PREFIX_TRANS):
        prefix_mode = "TRANSLATE"
        prompt = "." + prompt[len(PREFIX_TRANS):]
    elif prompt.startswith(PREFIX_ASSIS):
        prefix_mode = "ASSISTANT"
        prompt = prompt[len(PREFIX_ASSIS):]

    # データベースによるモード継続
    if prefix_mode is None and message.reference and message.reference.message_id:
        try:
            async with db_conn.execute("SELECT mode FROM message_logs WHERE message_id = ?", (message.reference.message_id,)) as cursor:
                row = await cursor.fetchone()
                if row:
                    db_mode = row[0]
                    if db_mode in ("TALK", "STORY", "ASSISTANT"):
                        prefix_mode = db_mode
                    elif db_mode == "TRANSLATE":
                        return
        except Exception as e:
            logger.error(f"データベース モード継続 エラー: {e}")

    # 現在メッセージの画像取得
    target_image_url = await get_image_from_attachment(message)
    if not target_image_url:
        target_image_url = await get_image_from_forward(message)
    target_markdown_url = None
    
    # 画像URLとMarkdown処理
    if not target_image_url:
        extracted_image_url, cleaned_prompt = await get_image_from_text(prompt)
        if extracted_image_url:
            target_image_url = extracted_image_url
            prompt = cleaned_prompt
        else:
            extracted_markdown_url, cleaned_prompt = await get_markdown_from_attachment(message, prompt)
            if extracted_markdown_url:
                target_markdown_url = extracted_markdown_url
                prompt = cleaned_prompt
            elif prompt:
                extracted_markdown_url, cleaned_prompt = await get_markdown_from_text(prompt)
                if extracted_markdown_url:
                    target_markdown_url = extracted_markdown_url
                    prompt = cleaned_prompt
    
    # 空メッセージ判定
    if (not prompt or not any(c.isalnum() for c in prompt)) and not target_image_url:
        await message.reply(HELP_INFORMATION, delete_after=20.0, allowed_mentions=MENTION_RESTRICTION, suppress_embeds=True)
        return

    # モード判定
    current_mode = "TALK"
    
    if prefix_mode:
        current_mode = prefix_mode
    elif prompt:
        if prompt.startswith(PREFIX_TALK):
            current_mode = "TALK"
        elif prompt.startswith(PREFIX_STORY):
            current_mode = "STORY"
        elif prompt.startswith(PREFIX_TRANS):
            current_mode = "TRANSLATE"
        elif prompt.startswith(PREFIX_ASSIS):
            current_mode = "ASSISTANT"
        elif re.match(r'^\.\.debug', prompt):
            current_mode = "DEBUG"
        elif re.match(r'^\.\.markdown', prompt):
            current_mode = "MARKDOWN"
    else:
        current_mode = "TALK"

    # デバッグモード処理
    if current_mode == "DEBUG":
        if message.author.id != MASTER_USER_ID:
            return
        await message.reply(DEBUG_INFORMATION, allowed_mentions=MENTION_RESTRICTION)
        return

    # クールダウンと回数制限のチェックと加算
    status, remaining_time = await check_and_count(user_id, message.author.display_name)
    if status == "COOLDOWN":
        await message.reply(f"クールダウン中 (残り {remaining_time} 秒)", delete_after=remaining_time)
        return
    elif status == "LIMIT":
        await message.reply("リクエスト制限 (e201)", delete_after=20.0)
        return
    elif status == "ERROR":
        return

    # Markdownモード処理
    if current_mode == "MARKDOWN":
        target_url = None
        youtube_video_id = None
        
        if ENABLE_MARKDOWN_PROCESS:
            for attachment in message.attachments:
                if any(attachment.filename.lower().endswith(ext) for ext in MARKDOWN_EXTENSIONS):
                    if attachment.size <= MAX_MARKDOWN_SIZE * 1024 * 1024:
                        target_url = attachment.url
                        break
                    
        if not target_url and ENABLE_URL_PROCESS:
            urls = re.findall(GENERAL_URL_PATTERN, prompt)
            for url in urls:
                youtube_match = re.search(YOUTUBE_URL_PATTERN, url)
                if youtube_match:
                    if not ENABLE_YOUTUBE_PROCESS:
                        continue
                    target_url = url
                    youtube_video_id = youtube_match.group(1)
                    break

                if not await is_valid_url(url) or re.search(IMAGE_URL_PATTERN, url, re.IGNORECASE):
                    continue
                try:
                    async with aiohttp.ClientSession() as session:
                        async with session.head(url, timeout=5, allow_redirects=False) as resp:
                            size_str = resp.headers.get('Content-Length')
                            size = int(size_str) if size_str and size_str.isdigit() else 0
                            if 0 < size <= MAX_MARKDOWN_SIZE * 1024 * 1024:
                                target_url = url
                                break
                except Exception:
                    continue
                        
        if not target_url and message.reference and message.reference.message_id:
            try:
                ref_msg = message.reference.cached_message or await message.channel.fetch_message(message.reference.message_id)
                if ENABLE_MARKDOWN_PROCESS:
                    for attachment in ref_msg.attachments:
                        if any(attachment.filename.lower().endswith(ext) for ext in MARKDOWN_EXTENSIONS):
                            if attachment.size <= MAX_MARKDOWN_SIZE * 1024 * 1024:
                                target_url = attachment.url
                                break
                if not target_url and ENABLE_URL_PROCESS:
                    ref_content = ref_msg.content.replace(f'<@{discord_client.user.id}>', '').strip()
                    urls = re.findall(GENERAL_URL_PATTERN, ref_content)
                    for url in urls:
                        youtube_match = re.search(YOUTUBE_URL_PATTERN, url)
                        if youtube_match:
                            if not ENABLE_YOUTUBE_PROCESS:
                                continue
                            target_url = url
                            youtube_video_id = youtube_match.group(1)
                            break

                        if not await is_valid_url(url) or re.search(IMAGE_URL_PATTERN, url, re.IGNORECASE):
                            continue
                        try:
                            async with aiohttp.ClientSession() as session:
                                async with session.head(url, timeout=5, allow_redirects=False) as resp:
                                    size_str = resp.headers.get('Content-Length')
                                    size = int(size_str) if size_str and size_str.isdigit() else 0
                                    if 0 < size <= MAX_MARKDOWN_SIZE * 1024 * 1024:
                                        target_url = url
                                        break
                        except Exception:
                            continue
            except Exception:
                pass

        if target_url:
            def extract_youtube_transcript(vid):
                try:
                    proxies = {"http": YOUTUBE_PROXY, "https": YOUTUBE_PROXY} if YOUTUBE_PROXY else None
                    transcript_list = YouTubeTranscriptApi.list_transcripts(vid, proxies=proxies)
                    transcript = next(iter(transcript_list))
                    transcript_data = transcript.fetch()
                    return " ".join([item['text'] for item in transcript_data])
                except Exception as e:
                    logger.info(f"YouTube字幕取得エラー (e311): {e}")
                    return None

            def convert_full_markdown(url):
                try:
                    md = MarkItDown()
                    result = md.convert(url)
                    if result and result.text_content:
                        return result.text_content
                except Exception as e:
                    logger.info(f"Markdown変換エラー (e307): {e}")
                return None

            async with message.channel.typing():
                try:
                    if youtube_video_id:
                        md_text = await asyncio.wait_for(
                            asyncio.to_thread(extract_youtube_transcript, youtube_video_id),
                            timeout=MARKDOWN_TIMEOUT
                        )
                    else:
                        md_text = await asyncio.wait_for(
                            asyncio.to_thread(convert_full_markdown, target_url),
                            timeout=MARKDOWN_TIMEOUT
                        )

                    if md_text:
                        file = discord.File(io.BytesIO(md_text.encode('utf-8')), filename="markdown.md")
                        reply_msg = await message.reply(file=file, allowed_mentions=MENTION_RESTRICTION)
                        await log_message(reply_msg.id, reply_msg.created_at.timestamp(), 0, "MARKDOWN")
                        return
                    else:
                        await message.reply("Markdown変換できません (e308)", delete_after=20.0)
                        return
                except asyncio.TimeoutError:
                    logger.info(f"Markdown変換タイムアウト (e309): {target_url}")
                    await message.reply("Markdown変換タイムアウト (e309)", delete_after=20.0)
                    return
        else:
            await message.reply("Markdown変換対象が見つかりません (e310)", delete_after=20.0)
            return

    # リクエスト処理
    async with message.channel.typing():
        try:
            # トークモード
            if current_mode == "TALK":
                system_content = SYSTEM_PROMPT_TALK
                history_limit = HISTORY_LIMIT_TALK
                current_temperature = TEMPERATURE_TALK
                current_primary_model = PRIMARY_MODEL_TALK
                current_secondary_model = SECONDARY_MODEL_TALK
                
            # ストーリーモード
            elif current_mode == "STORY":
                system_content = SYSTEM_PROMPT_STORY
                history_limit = HISTORY_LIMIT_STORY
                current_temperature = TEMPERATURE_STORY
                current_primary_model = PRIMARY_MODEL_STORY
                current_secondary_model = SECONDARY_MODEL_STORY
                
            # 翻訳モード
            elif current_mode == "TRANSLATE":
                system_content = SYSTEM_PROMPT_TRANS
                history_limit = HISTORY_LIMIT_TRANS
                current_temperature = TEMPERATURE_TRANS
                current_primary_model = PRIMARY_MODEL_TRANS
                current_secondary_model = SECONDARY_MODEL_TRANS
                
            # アシスタントモード
            elif current_mode == "ASSISTANT":
                system_content = SYSTEM_PROMPT_ASSIS
                history_limit = HISTORY_LIMIT_ASSIS
                current_temperature = TEMPERATURE_ASSIS
                current_primary_model = PRIMARY_MODEL_ASSIS
                current_secondary_model = SECONDARY_MODEL_ASSIS

            # ペイロード初期化
            messages_payload = [
                {"role": "system", "content": system_content}
            ]
            
            history = []
            current_msg = message
            limit = history_limit
            attachment_found = (target_image_url is not None) or (target_markdown_url is not None)
            
            # 文脈構築
            current_history_chars = 0
            while current_msg.reference and current_msg.reference.message_id and limit > 0:
                try:
                    ref_msg = current_msg.reference.cached_message or await message.channel.fetch_message(current_msg.reference.message_id)
                    
                    role = "assistant" if ref_msg.author == discord_client.user else "user"
                    clean_content = ref_msg.content.replace(f'<@{discord_client.user.id}>', '').strip()
                    
                    hist_attachment_url = None
                    if not attachment_found:
                        hist_attachment_url = await get_image_from_attachment(ref_msg)
                        if not hist_attachment_url:
                            hist_attachment_url = await get_image_from_forward(ref_msg)
                        if not hist_attachment_url:
                            extracted_image_url, cleaned_content = await get_image_from_text(clean_content)
                            if extracted_image_url:
                                hist_attachment_url = extracted_image_url
                                clean_content = cleaned_content
                            else:
                                hist_markdown_url, cleaned_content = await get_markdown_from_attachment(ref_msg, clean_content)
                                if hist_markdown_url:
                                    clean_content = cleaned_content
                                    attachment_found = True
                                elif clean_content:
                                    hist_markdown_url, cleaned_content = await get_markdown_from_text(clean_content)
                                    if hist_markdown_url:
                                        clean_content = cleaned_content
                                        attachment_found = True
                                
                        if hist_attachment_url:
                            attachment_found = True
                    
                    if current_history_chars + len(clean_content) >= HISTORY_LENGTH_LIMIT:
                        break
                    current_history_chars += len(clean_content)

                    if current_mode == "TALK" and role == "user":
                        clean_content = f"(User Name:{ref_msg.author.display_name}) {clean_content}"

                    if clean_content or hist_attachment_url:
                        history.append({
                            "role": role, 
                            "content": clean_content,
                            "image_url": hist_attachment_url
                        })
                        
                    current_msg = ref_msg
                    limit -= 1
                except Exception as e:
                    logger.info(f"履歴取得エラー (e401): {e}")
                  # await message.reply("履歴取得エラー (e401)", delete_after=20.0)
                    break
            
            # 履歴処理
            for h in reversed(history):
                if not h.get("image_url"):
                    messages_payload.append({"role": h["role"], "content": h["content"]})
                else:
                    content_list = [{"type": "text", "text": h["content"] if h["content"] else " "}]
                    content_list.append({"type": "image_url", "image_url": {"url": h["image_url"]}})
                    messages_payload.append({"role": h["role"], "content": content_list})
                
            # メッセージ処理
            if current_mode == "TALK":
                prompt = f"(User Name:{message.author.display_name}) {prompt}"

            if not target_image_url:
                messages_payload.append({"role": "user", "content": prompt})
            else:
                content_list = [{"type": "text", "text": prompt if prompt else " "}]
                content_list.append({"type": "image_url", "image_url": {"url": target_image_url}})
                messages_payload.append({"role": "user", "content": content_list})

            if ENABLE_PAYLOAD_LOGGING:
                logger.info(f"API Payload ({current_mode}): {messages_payload}")

            # リクエスト送信
            try:
                response = await asyncio.wait_for(
                    primary_ai_client.chat.completions.create(
                        model = current_primary_model,
                        messages = messages_payload,
                        max_tokens = MAX_TOKENS,
                        temperature = current_temperature,
                    ),
                    timeout=REQUEST_TIMEOUT
                )
            except Exception as e:
                logger.error(f"プライマリAPIエラー (e501): {e}")
                response = await asyncio.wait_for(
                    secondary_ai_client.chat.completions.create(
                        model = current_secondary_model,
                        messages = messages_payload,
                        max_tokens = MAX_TOKENS,
                        temperature = current_temperature,
                    ),
                    timeout=REQUEST_TIMEOUT
                )
            
            # 統計カウント
            used_tokens = response.usage.total_tokens if response.usage else 0
            await add_global_tokens(used_tokens)
            
            reply_text = response.choices[0].message.content
            
            # 分割送信
            if len(reply_text) > 2000:
                target_message = message
                is_first = True
                for i in range(0, len(reply_text), 2000):
                    target_message = await target_message.reply(reply_text[i:i+2000], allowed_mentions=MENTION_RESTRICTION)
                    tokens_to_log = used_tokens if is_first else 0
                    await log_message(target_message.id, target_message.created_at.timestamp(), tokens_to_log, current_mode)
                    is_first = False
            else:
                reply_msg = await message.reply(reply_text, allowed_mentions=MENTION_RESTRICTION)
                await log_message(reply_msg.id, reply_msg.created_at.timestamp(), used_tokens, current_mode)
                
        except Exception as e:
            logger.error(f"リクエストエラー (e502): {e}")
            await message.reply("リクエストエラー (e502)", delete_after=20.0)

# 統計表示タスク
async def print_stats_loop():
    await discord_client.wait_until_ready()
    while not discord_client.is_closed():
        await asyncio.sleep(300)
        
        global period_request_count, period_token_count
        
        current_reqs = period_request_count
        current_tokens = period_token_count
        period_request_count = 0
        period_token_count = 0
        
        logger.info(f"Requests (5min): {current_reqs}, Tokens used (5min): {current_tokens}")

# ローカライゼーション
class CommandTranslator(app_commands.Translator):
    async def translate(self, string: app_commands.locale_str, locale: discord.Locale, context: app_commands.TranslationContext) -> str | None:
        if locale in (discord.Locale.american_english, discord.Locale.british_english):
            if string.message == "Madokaのヘルプ情報を表示します":
                return "Displays help information for Madoka"
            elif string.message == "テキストを指定の言語に翻訳します":
                return "Translate text into the specified language"
            elif string.message == "翻訳先の言語 (例: ja, en)":
                return "Target language (e.g., en, ja)"
            elif string.message == "翻訳するテキスト":
                return "Text to translate"

        elif locale == discord.Locale.french:
            if string.message == "Madokaのヘルプ情報を表示します":
                return "Affiche les informations d'aide pour Madoka"
            elif string.message == "テキストを指定の言語に翻訳します":
                return "Traduit le texte dans la langue spécifiée"
            elif string.message == "翻訳先の言語 (例: ja, en)":
                return "Langue cible (ex: fr, ja)"
            elif string.message == "翻訳するテキスト":
                return "Texte à traduire"

        elif locale == discord.Locale.german:
            if string.message == "Madokaのヘルプ情報を表示します":
                return "Zeigt Hilfeinformationen für Madoka an"
            elif string.message == "テキストを指定の言語に翻訳します":
                return "Übersetzt Text in die angegebene Sprache"
            elif string.message == "翻訳先の言語 (例: ja, en)":
                return "Zielsprache (z.B. de, ja)"
            elif string.message == "翻訳するテキスト":
                return "Zu übersetzender Text"

        elif locale == discord.Locale.korean:
            if string.message == "Madokaのヘルプ情報を表示します":
                return "Madoka의 도움말 정보를 표시합니다"
            elif string.message == "テキストを指定の言語に翻訳します":
                return "텍스트를 지정된 언어로 번역합니다"
            elif string.message == "翻訳先の言語 (例: ja, en)":
                return "번역할 언어 (예: ko, ja)"
            elif string.message == "翻訳するテキスト":
                return "번역할 텍스트"

        elif locale in (discord.Locale.taiwan_chinese, discord.Locale.chinese):
            if string.message == "Madokaのヘルプ情報を表示します":
                return "顯示 Madoka 的幫助資訊"
            elif string.message == "テキストを指定の言語に翻訳します":
                return "將文本翻譯成指定語言"
            elif string.message == "翻訳先の言語 (例: ja, en)":
                return "目標語言 (例: zht, ja)"
            elif string.message == "翻訳するテキスト":
                return "要翻譯的文本"

        return None

@discord_client.event
async def setup_hook():
    await init_db()
    await tree.set_translator(CommandTranslator())
    await tree.sync()
    discord_client.loop.create_task(print_stats_loop())

original_close = discord_client.close

async def close_client():
    global db_conn
    if db_conn:
        await db_conn.close()
        logger.info("データベース切断完了")
    await original_close()

discord_client.close = close_client

if __name__ == "__main__":
    discord_client.run(DISCORD_TOKEN)
