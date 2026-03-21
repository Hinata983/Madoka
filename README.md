# Madoka
Simple discord AI chat bot "Madoka"

Madokaは、Discord上で動作するシンプルなAIチャットボットです。
OpenAI互換APIを利用し、ユーザーとの自然な対話や、リプライツリーを遡った文脈の理解が可能です。

# 必須環境
Python 3.8 以上

# インストール
リポジトリのクローン
```bash
git clone https://github.com/Hinata983/Madoka.git
cd Madoka
```

必要パッケージのインストール
```bash
pip install discord.py openai
```

# 初期設定
ソースコード内の以下の変数を、ご自身の環境に合わせて書き換えてください。

DISCORD_TOKEN:Discord Developer Portalで取得したボットのトークン
BASE_URL:OpenAI互換APIエンドポイントURL
API_KEY:APIキー
MODEL_NAME:使用するモデル

# Botの起動
```bash
python main.py
```

# ライセンス
このプロジェクトは MIT License のもとで公開されています。
