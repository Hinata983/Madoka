import time
import asyncio
import discord
import re
from datetime import datetime
from openai import AsyncOpenAI

# Discordボットトークン設定
DISCORD_TOKEN    = 'YOUR_DISCORD_TOKEN'

# OpenAI互換API設定
API_KEY    = 'YOUR_API_KEY'
BASE_URL    = 'https://api.example.com/v1'
MODEL_NAME    = 'gemini-3-flash-preview'

# セカンドAPI設定
SECOND_API_KEY    = 'YOUR_SECOND_API_KEY'
SECOND_BASE_URL    = 'https://api.example.com/v1'
SECOND_MODEL_NAME    = 'gemini-3-flash-preview'

# 動作設定
COOLDOWN_SECONDS    = 20    # ユーザーごとの連続送信制限秒数
MAX_REQUESTS_PER_2H = 120 # 2時間あたりの最大返信回数
HISTORY_LIMIT_TALK    = 6    # トークモード時の会話履歴数
HISTORY_LIMIT_TRANS    = 1    # 翻訳モード時の会話履歴数
HISTORY_LIMIT_ASSIS    = 4    # アシスタントモード時の会話履歴数
MAX_TOKENS                = 4096    # APIの最大出力トークン数
TEMPERATURE_TALK        = 0.9    # トークモードの温度
TEMPERATURE_TRANS        = 0.5    # 翻訳モードの温度
TEMPERATURE_ASSIS        = 0.7    # アシスタントモードの温度

# 出力文字上限期待値
OUTPUT_LENGTH_TALK = int(MAX_TOKENS * 0.30)
OUTPUT_LENGTH_TRANS = int(MAX_TOKENS * 0.40)
OUTPUT_LENGTH_ASSIS = int(MAX_TOKENS * 0.30)

# 基本情報
BOT_VERSION    = 'v1.8.2-202604P01'
AUTHOR_NAME    = 'Hinata983'
GITHUB_URL    = 'https://github.com/Hinata983/Madoka'

# システムプロンプト設定（トークモード）
SYSTEM_PROMPT = f"""システム設定 (System)
言語：ユーザーのプロンプトに順応
名前：Madoka
機能：物語を推進
出力文字上限：{OUTPUT_LENGTH_TALK}

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
SYSTEM_PROMPT_TRANS = f"""システム設定 (System)
言語：ユーザーのプロンプトに順応
機能：翻訳
出力文字上限：{OUTPUT_LENGTH_TRANS}
ユーザープロンプトの最初に指定された .jp のような言語コードを認識、メッセージをその言語に翻訳、翻訳結果のみ出力、説明や補足は不要
性描写が求められる場合は猫の鳴き声だけで返信
"""

# システムプロンプト設定（アシスタントモード）
SYSTEM_PROMPT_ASSIS = f"""システム設定 (System)
言語：ユーザーのプロンプトに順応
名前：Madoka
機能：アシスタント
出力文字上限：{OUTPUT_LENGTH_ASSIS}

表現方法 (Mode of expression)
制限：太字は使わない、絵文字は使わない
性描写が求められる場合は猫の鳴き声だけで返信
"""

# 空メッセージへの返信
EMPTY_PROMPT_REPLY = f"""About Madoka
Version: {BOT_VERSION}
Cooldown: {COOLDOWN_SECONDS}

Command List
Enter the following symbols at the beginning of your message

. [lang code] [text]
Enter a single dot to enter translation mode.

.. [text]
Enter two dots to enter Assistant mode.

, [text]
Enter a comma and the bot will ignore this message.
"""

# デバッグ用メッセージ
DEBUG_MESSAGE_REPLY = f"""About Madoka
Version: {BOT_VERSION}
Model: {MODEL_NAME}
Second Model: {SECOND_MODEL_NAME}

Cooldown: {COOLDOWN_SECONDS}
Max Request: {MAX_REQUESTS_PER_2H}

History Limit (Talk): {HISTORY_LIMIT_TALK}
History Limit (Trans): {HISTORY_LIMIT_TRANS}
History Limit (Assis): {HISTORY_LIMIT_ASSIS}
Output Length (Talk): {OUTPUT_LENGTH_TALK}
Output Length (Trans): {OUTPUT_LENGTH_TRANS}
Output Length (Assis): {OUTPUT_LENGTH_ASSIS}

Max Tokens: {MAX_TOKENS}
Temperature (Talk): {TEMPERATURE_TALK}
Temperature (Trans): {TEMPERATURE_TRANS}
Temperature (Assis): {TEMPERATURE_ASSIS}

By {AUTHOR_NAME}
{GITHUB_URL}
"""

# 状態管理用変数
user_cooldown = {}
user_request_count = {}
total_request_count = 0
total_tokens = 0

# 非同期OpenAIクライアントの初期化
ai_client = AsyncOpenAI(
    api_key = API_KEY,
    base_url = BASE_URL,
)

# セカンドクライアントの初期化
second_ai_client = AsyncOpenAI(
    api_key = SECOND_API_KEY,
    base_url = SECOND_BASE_URL,
)

# Discordボットの設定
intents = discord.Intents.default()
intents.message_content = True
discord_client = discord.Client(intents=intents)

@discord_client.event
async def on_ready():
    print(f'{discord_client.user} logged in.')

@discord_client.event
async def on_message(message):
    if message.author == discord_client.user:
        return

    # メンションと返信の判定
    is_mentioned = discord_client.user in message.mentions
    is_reply_to_bot = False
    
    if message.reference and message.reference.message_id:
        try:
            ref_msg = message.reference.cached_message or await message.channel.fetch_message(message.reference.message_id)
            if ref_msg.author == discord_client.user:
                is_reply_to_bot = True
        except Exception:
            pass

    if not (is_mentioned or is_reply_to_bot):
        return

    # クールダウンチェック
    current_time = time.time()
    user_id = message.author.id
    
    if user_id in user_cooldown:
        time_passed = current_time - user_cooldown[user_id]
        if time_passed < COOLDOWN_SECONDS:
            return

    # 回数制限チェック
    if user_request_count.get(user_id, 0) >= MAX_REQUESTS_PER_2H:
        await message.reply("リクエスト制限 (e061)", delete_after=20.0)
        return

    # 画像取得
    def get_first_image_url(msg):
        for attachment in msg.attachments:
            if attachment.content_type and attachment.content_type.startswith('image/'):
                return attachment.url
        return None

    prompt = message.content.replace(f'<@{discord_client.user.id}>', '').strip()
    
    # 現在メッセージの画像取得
    target_image_url = get_first_image_url(message)
    
    # 空メッセージ判定
    if (not prompt or prompt == "." or prompt == ".." or prompt == "?") and not target_image_url:
        await message.reply(EMPTY_PROMPT_REPLY, delete_after=20.0)
        return

    # 無視判定
    if prompt.startswith(','):
        return

    # クールダウン記録
    user_cooldown[user_id] = current_time

    # モード判定
    current_mode = "TALK"
    
    if prompt:
        if re.match(r'^\.\.debug', prompt):
            current_mode = "DEBUG"
        elif re.match(r'^\.(?!\.)', prompt):
            current_mode = "TRANSLATE"
        elif re.match(r'^\.\.', prompt):
            current_mode = "ASSISTANT"
    else:
        current_mode = "TALK"

    # デバッグモード処理
    if current_mode == "DEBUG":
        await message.reply(DEBUG_MESSAGE_REPLY)
        return

    # リクエスト処理
    async with message.channel.typing():
        try:
            # トークモード
            if current_mode == "TALK":
                system_content = SYSTEM_PROMPT
                history_limit = HISTORY_LIMIT_TALK
                current_temperature = TEMPERATURE_TALK
                
            # 翻訳モード
            elif current_mode == "TRANSLATE":
                system_content = SYSTEM_PROMPT_TRANS
                history_limit = HISTORY_LIMIT_TRANS
                current_temperature = TEMPERATURE_TRANS
                
            # アシスタントモード
            elif current_mode == "ASSISTANT":
                system_content = SYSTEM_PROMPT_ASSIS
                history_limit = HISTORY_LIMIT_ASSIS
                current_temperature = TEMPERATURE_ASSIS

            # ペイロード初期化
            messages_payload = [
                {"role": "system", "content": system_content}
            ]
            
            history = []
            current_msg = message
            limit = history_limit
            image_found = target_image_url is not None
            
            # 文脈構築
            while current_msg.reference and current_msg.reference.message_id and limit > 0:
                try:
                    ref_msg = current_msg.reference.cached_message or await message.channel.fetch_message(current_msg.reference.message_id)
                    
                    role = "assistant" if ref_msg.author == discord_client.user else "user"
                    clean_content = ref_msg.content.replace(f'<@{discord_client.user.id}>', '').strip()
                    
                    hist_image_url = None
                    if not image_found:
                        hist_image_url = get_first_image_url(ref_msg)
                        if hist_image_url:
                            image_found = True
                    
                    if clean_content or hist_image_url:
                        history.append({
                            "role": role, 
                            "content": clean_content,
                            "image_url": hist_image_url
                        })
                        
                    current_msg = ref_msg
                    limit -= 1
                except Exception as e:
                    print(f"履歴取得エラー (e021): {e}")
                    await message.reply("履歴取得エラー (e021)", delete_after=20.0)
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
            if not target_image_url:
                messages_payload.append({"role": "user", "content": prompt})
            else:
                content_list = [{"type": "text", "text": prompt if prompt else " "}]
                content_list.append({"type": "image_url", "image_url": {"url": target_image_url}})
                messages_payload.append({"role": "user", "content": content_list})

            # リクエスト送信
            try:
                response = await asyncio.wait_for(
                    ai_client.chat.completions.create(
                        model = MODEL_NAME,
                        messages = messages_payload,
                        max_tokens = MAX_TOKENS,
                        temperature = current_temperature,
                    ),
                    timeout=30.0
                )
            except Exception as e:
                print(f"メインAPIエラー (e042): {e}")
                response = await asyncio.wait_for(
                    second_ai_client.chat.completions.create(
                        model = SECOND_MODEL_NAME,
                        messages = messages_payload,
                        max_tokens = MAX_TOKENS,
                        temperature = current_temperature,
                    ),
                    timeout=30.0
                )
            
            # 統計カウント
            global total_request_count, total_tokens
            used_tokens = response.usage.total_tokens if response.usage else 0
            user_request_count[user_id] = user_request_count.get(user_id, 0) + 1
            total_request_count += 1
            total_tokens += used_tokens
            
            reply_text = response.choices[0].message.content
            
            # 分割送信
            if len(reply_text) > 2000:
                target_message = message
                for i in range(0, len(reply_text), 2000):
                    target_message = await target_message.reply(reply_text[i:i+2000])
            else:
                await message.reply(reply_text)
                
        except Exception as e:
            print(f"リクエストエラー (e041): {e}")
            await message.reply("リクエストエラー (e041)", delete_after=20.0)

# 統計表示タスク
async def print_stats_loop():
    await discord_client.wait_until_ready()
    while not discord_client.is_closed():
        await asyncio.sleep(300)
        
        global total_request_count, total_tokens
        
        current_reqs = total_request_count
        current_tokens = total_tokens
        total_request_count = 0
        total_tokens = 0
        
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{now}] Requests: {current_reqs}, Tokens used: {current_tokens}")

# クールダウン辞書クリーンアップタスク
async def cleanup_cooldowns_loop():
    await discord_client.wait_until_ready()
    while not discord_client.is_closed():
        await asyncio.sleep(7200)
        user_cooldown.clear()
        user_request_count.clear()

@discord_client.event
async def setup_hook():
    discord_client.loop.create_task(print_stats_loop())
    discord_client.loop.create_task(cleanup_cooldowns_loop())

if __name__ == "__main__":
    discord_client.run(DISCORD_TOKEN)
