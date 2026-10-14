"""Discord接続の確認用。!pingへの返信とYouTube URLの受付を行います。
この段階では音声再生や予約の保存は行いません。
実行: py -3.13 bot.py
"""
import getpass
import json
from pathlib import Path
import re

import discord

CONFIG_FILE = Path(__file__).with_name("config.json")


def load_config():
    """config.jsonがあれば読み込み、なければ初回のみ入力を受け付けて保存する。"""
    if CONFIG_FILE.is_file():
        try:
            data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            channel_id = int(data["channel_id"])
            token = str(data["token"]).strip()
            if channel_id > 0 and token:
                return channel_id, token
        except (OSError, ValueError, KeyError, TypeError):
            print("config.json の読み込みに失敗したため、再入力します。")

    raw_channel = input("音楽受付チャンネルのIDを貼り付けてEnter: ").strip()
    if not raw_channel.isdigit() or int(raw_channel) <= 0:
        print("チャンネルIDには数字だけを入力してください。")
        return None, None
    token = getpass.getpass("Botトークンを貼り付けてEnter（入力は表示されません）: ").strip()
    if not token:
        print("トークンが空です。")
        return None, None

    channel_id = int(raw_channel)
    try:
        CONFIG_FILE.write_text(
            json.dumps({"channel_id": channel_id, "token": token}, indent=2),
            encoding="utf-8",
        )
        print(f"設定を {CONFIG_FILE.name} に保存しました。次回から自動で読み込みます。")
    except OSError as e:
        print(f"設定の保存に失敗しました: {e}")

    return channel_id, token


def main():
    channel_id, token = load_config()
    if not channel_id or not token:
        return

    intents = discord.Intents.default()
    intents.message_content = True
    client = discord.Client(intents=intents, allowed_mentions=discord.AllowedMentions.none())

    @client.event
    async def on_ready():
        print(f"接続成功: {client.user}")
        print("指定チャンネルに !ping またはYouTubeのURLを送ってください。")
        print("終了するには、この画面で Ctrl+C を押します。")

    @client.event
    async def on_message(message):
        if message.author.bot or message.guild is None or message.channel.id != channel_id:
            return
        if message.content.strip() == "!ping":
            await message.channel.send("接続OK！")
            return
        if re.search(r"https?://(?:www\.|m\.|music\.)?(?:youtube\.com|youtu\.be)(?:/|\?)", message.content, re.IGNORECASE):
            await message.channel.send(
                f"{message.author.display_name}さんのYouTube URLを受け取りました。\n"
                "現在は接続確認用なので、まだ音声は再生しません。"
            )
            print(f"URL受付: ユーザーID={message.author.id}")

    try:
        client.run(token)
    except discord.LoginFailure:
        print("ログインできませんでした。トークンを再設定する場合は config.json を削除して再実行してください。")
    except discord.PrivilegedIntentsRequired:
        print("Developer PortalのBot画面でMessage Content Intentを有効にしてください。")


if __name__ == "__main__":
    main()