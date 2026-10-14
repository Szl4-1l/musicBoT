"""Discord接続の確認用。!pingへの返信とYouTube URLの受付を行います。
この段階では音声再生や予約の保存は行いません。
実行: py -3.13 bot.py
"""
import getpass
import re

import discord


def main():
    raw_channel = input("音楽受付チャンネルのIDを貼り付けてEnter: ").strip()
    if not raw_channel.isdigit() or int(raw_channel) <= 0:
        print("チャンネルIDには数字だけを入力してください。")
        return
    channel_id = int(raw_channel)
    token = getpass.getpass("Botトークンを貼り付けてEnter（入力は表示されません）: ").strip()
    if not token:
        print("トークンが空です。")
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
        print("ログインできませんでした。Bot画面で発行したトークンを確認してください。")
    except discord.PrivilegedIntentsRequired:
        print("Developer PortalのBot画面でMessage Content Intentを有効にしてください。")


if __name__ == "__main__":
    main()
