import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from music_bot_2_GPT6 import MusicBot


class CommandTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.bot = MusicBot(1, "mpv", "deno")
        self.bot.say = AsyncMock()
        self.bot.update_dashboard = AsyncMock()

    async def asyncTearDown(self):
        await self.bot.close()

    def message(self, text, channel=1, bot=False):
        return SimpleNamespace(content=text, author=SimpleNamespace(bot=bot),
                               guild=SimpleNamespace(id=10),
                               channel=SimpleNamespace(id=channel))

    async def test_ping_prefixes(self):
        for text in ("!ping", "/ping", "  !PING  "):
            with self.subTest(text=text):
                self.bot.say.reset_mock()
                await self.bot.on_message(self.message(text))
                self.bot.say.assert_awaited_once_with("接続OK！")

    async def test_ignores_other_channels_and_bots(self):
        await self.bot.on_message(self.message("!ping", channel=2))
        await self.bot.on_message(self.message("!ping", bot=True))
        self.bot.say.assert_not_awaited()

    async def test_play_preserves_url(self):
        self.bot.add_url = AsyncMock()
        message = self.message("!play https://youtu.be/abcdefghijk")
        await self.bot.on_message(message)
        self.bot.add_url.assert_awaited_once_with(
            message.author, "https://youtu.be/abcdefghijk", False, self.bot.say)
