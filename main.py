import time
import discord
from openai import AsyncOpenAI

# トークン設定
DISCORD_TOKEN = 'DISCORD_TOKEN'

# OpenAI互換API設定
BASE_URL = 'https://api.example.com/v1'  # エンドポイントURL
API_KEY = 'API_KEY'             # API Key
MODEL_NAME = 'MODEL_NAME'          # デフォルトは'gpt-5.4-mini'

# システムプロンプト設定
SYSTEM_PROMPT = """システム設定 (System)
言語：ユーザーのプロンプトに順応
名前：Madoka
機能：AIアシスタント

表現方法 (Mode of expression)
制限：太字は使わない、絵文字は使わない

描写要素 (Description method)
セリフ：多め
倫理制限：物語の時代に準拠
補足：全てのキャラクターのセリフは「」の中に
キャラクターの気持ちの描写は詳細に

翻訳機能設定 (Translation)
ユーザープロンプトは .jp のような言語コードから始まる場合は、ただそのメッセージを指定された言語コードに翻訳するだけ
"""

# プロンプトなしの場合の返信
EMPTY_PROMPT_REPLY = """About Madoka
Version:v1.0.2-202603P02
By hinata983
https://github.com/Hinata983/Madoka
"""

# クールダウン設定
user_cooldowns = {}
COOLDOWN_SECONDS = 10

# 非同期版のOpenAIクライアントの初期化
ai_client = AsyncOpenAI(
    api_key=API_KEY,
    base_url=BASE_URL,
)

# Discordボットの設定
intents = discord.Intents.default()
intents.message_content = True
discord_client = discord.Client(intents=intents)

@discord_client.event
async def on_ready():
    print(f'{discord_client.user} がログインしました。')

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
    
    # プロンプトが空だった場合は EMPTY_PROMPT_REPLY で返信
    if not prompt:
        await message.reply(EMPTY_PROMPT_REPLY)
        return

    async with message.channel.typing():
        try:
            # 文脈構築
            messages_payload = [
                {"role": "system", "content": SYSTEM_PROMPT}
            ]
            
            history = []
            current_msg = message
            
            # 返信を遡る最大件数
            limit = 6
            while current_msg.reference and current_msg.reference.message_id and limit > 0:
                try:
                    ref_msg = current_msg.reference.cached_message or await message.channel.fetch_message(current_msg.reference.message_id)
                    
                    # 発言者がボットならassistant、ユーザーならuser
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
                model=MODEL_NAME,
                messages=messages_payload,
                max_tokens=4096,
                temperature=0.9,
            )
            
            reply_text = response.choices[0].message.content
            
            # Discordの文字数制限を超える場合は分割送信
            if len(reply_text) > 2000:
                target_message = message
                for i in range(0, len(reply_text), 2000):
                    target_message = await target_message.reply(reply_text[i:i+2000])
            else:
                await message.reply(reply_text)
                
        except Exception as e:
            await message.reply(f"エラーが発生しました (e017): {e}")

discord_client.run(DISCORD_TOKEN)
