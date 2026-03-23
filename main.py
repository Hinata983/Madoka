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

# 動作設定
COOLDOWN_SECONDS    = 10    # ユーザーごとの連続送信制限秒数
HISTORY_LIMIT_TALK    = 6    # トークモード時の会話履歴数
HISTORY_LIMIT_TRANS    = 1    # 翻訳モード時の会話履歴数
MAX_TOKENS                = 4096    # APIの最大出力トークン数
TEMPERATURE                = 0.9    # APIの回答の温度

# 基本情報
BOT_VERSION    = 'v1.3.1-202603P08'
AUTHOR_NAME    = 'Hinata983'
GITHUB_URL    = 'https://github.com/Hinata983/Madoka'

# システムプロンプト設定（トークモード）
SYSTEM_PROMPT = """システム設定 (System)
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
TRANSLATION_SYSTEM_PROMPT = """システム設定 (System)
機能：翻訳
ユーザープロンプトの最初に指定された .jp のような言語コードを認識、メッセージをその言語に翻訳、翻訳結果のみ出力、説明や補足は不要
"""

# プロンプトなしの場合の返信
EMPTY_PROMPT_REPLY = f"""About Madoka
Version: {BOT_VERSION}
Model: {MODEL_NAME}
"""

# デバッグ用メッセージ
DEBUG_MESSAGE_REPLY = f"""About Madoka
Version: {BOT_VERSION}
Model: {MODEL_NAME}

Cooldown: {COOLDOWN_SECONDS}
History Limit (Talk): {HISTORY_LIMIT_TALK}
History Limit (Trans): {HISTORY_LIMIT_TRANS}
Max Tokens: {MAX_TOKENS}
Temperature: {TEMPERATURE}

By {AUTHOR_NAME}
{GITHUB_URL}
"""

# 状態管理用変数
user_cooldowns = {}
request_count = 0
total_tokens = 0

# 非同期版OpenAIクライアントの初期化
ai_client = AsyncOpenAI(
    api_key = API_KEY,
    base_url = BASE_URL,
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
    
    if user_id in user_cooldowns:
        time_passed = current_time - user_cooldowns[user_id]
        if time_passed < COOLDOWN_SECONDS:
            return
            
    user_cooldowns[user_id] = current_time

    prompt = message.content.replace(f'<@{discord_client.user.id}>', '').strip()
    
    # プロンプトなしの場合の返信
    if not prompt:
        await message.reply(EMPTY_PROMPT_REPLY, delete_after=10.0)
        return

    # モード判定
    current_mode = "TALK"
    
    if re.match(r'^\.[0-9]+', prompt):
        current_mode = "DEBUG"
    elif re.match(r'^\.[a-zA-Z]+', prompt):
        current_mode = "TRANSLATION"

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
                
            # 翻訳モード
            elif current_mode == "TRANSLATION":
                system_content = TRANSLATION_SYSTEM_PROMPT
                history_limit = HISTORY_LIMIT_TRANS

            # ペイロード初期化
            messages_payload = [
                {"role": "system", "content": system_content}
            ]
            
            history = []
            current_msg = message
            limit = history_limit
            
            # 文脈構築
            while current_msg.reference and current_msg.reference.message_id and limit > 0:
                try:
                    ref_msg = current_msg.reference.cached_message or await message.channel.fetch_message(current_msg.reference.message_id)
                    
                    role = "assistant" if ref_msg.author == discord_client.user else "user"
                    clean_content = ref_msg.content.replace(f'<@{discord_client.user.id}>', '').strip()
                    
                    if clean_content:
                        history.append({"role": role, "content": clean_content})
                        
                    current_msg = ref_msg
                    limit -= 1
                except Exception as e:
                    print(f"履歴取得エラー (e016): {e}")
                    break
            
            for h in reversed(history):
                messages_payload.append(h)
                
            messages_payload.append({"role": "user", "content": prompt})

            # リクエスト送信
            response = await ai_client.chat.completions.create(
                model = MODEL_NAME,
                messages = messages_payload,
                max_tokens = MAX_TOKENS,
                temperature = TEMPERATURE,
            )
            
            # 統計カウント
            global request_count, total_tokens
            used_tokens = response.usage.total_tokens if response.usage else 0
            request_count += 1
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
            await message.reply(f"エラーが発生しました (e017): {e}")

# 統計表示タスク
async def print_stats_loop():
    await discord_client.wait_until_ready()
    while not discord_client.is_closed():
        await asyncio.sleep(600)
        
        global request_count, total_tokens
        
        current_reqs = request_count
        current_tokens = total_tokens
        request_count = 0
        total_tokens = 0
        
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{now}] Requests: {current_reqs}, Tokens used: {current_tokens}")

# クールダウン辞書クリーンアップタスク
async def cleanup_cooldowns_loop():
    await discord_client.wait_until_ready()
    while not discord_client.is_closed():
        await asyncio.sleep(3600)
        user_cooldowns.clear()

@discord_client.event
async def setup_hook():
    discord_client.loop.create_task(print_stats_loop())
    discord_client.loop.create_task(cleanup_cooldowns_loop())

if __name__ == "__main__":
    discord_client.run(DISCORD_TOKEN)
