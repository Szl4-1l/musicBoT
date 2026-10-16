import asyncio
from datetime import datetime
import unittest
from unittest.mock import AsyncMock, patch

from music_bot_2_GPT6 import JST, MusicBot, quiet_hours


class QuietHoursTests(unittest.TestCase):
    def test_boundaries_in_japan_time(self):
        for hour, minute, expected in [(21, 59, False), (22, 0, True),
                                        (0, 0, True), (7, 59, True), (8, 0, False)]:
            with self.subTest(hour=hour, minute=minute):
                self.assertEqual(quiet_hours(datetime(2026, 10, 16, hour, minute, tzinfo=JST)), expected)


class QuietPlaybackTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.bot = MusicBot(1, "mpv", "deno")
        self.bot.ipc_path = "test-pipe"
        self.bot.phase = "再生中"
        self.bot.update_dashboard = AsyncMock()

    async def asyncTearDown(self):
        await self.bot.close()

    async def test_night_pauses_and_morning_resumes_same_process(self):
        night = False
        started = asyncio.Event()
        paused = asyncio.Event()
        resumed = asyncio.Event()
        finish = asyncio.Event()

        async def process(*args, **kwargs):
            started.set()
            await finish.wait()

        async def ipc(command):
            if command[-1]:
                paused.set()
            else:
                resumed.set()

        self.bot.run_process = AsyncMock(side_effect=process)
        self.bot.send_ipc = AsyncMock(side_effect=ipc)
        with patch("music_bot_2_GPT6.quiet_hours", side_effect=lambda: night):
            task = asyncio.create_task(self.bot.play_audio("song.webm"))
            try:
                await asyncio.wait_for(started.wait(), 2)
                night = True
                await asyncio.wait_for(paused.wait(), 2)
                night = False
                await asyncio.wait_for(resumed.wait(), 2)
                self.bot.run_process.assert_awaited_once()
                finish.set()
                await task
            finally:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)

    async def test_manual_pause_is_preserved_in_morning(self):
        self.bot.user_paused = True
        self.bot.run_process = AsyncMock()
        self.bot.send_ipc = AsyncMock()
        with patch("music_bot_2_GPT6.quiet_hours", return_value=False):
            await self.bot.play_audio("song.webm")
        self.assertIn("--pause=yes", self.bot.run_process.call_args.args[0])
        self.bot.send_ipc.assert_not_awaited()

    async def test_night_keeps_queue_untouched(self):
        self.bot.wait_until_ready = AsyncMock()
        self.bot.queue.add(1, ["song"])
        with patch("music_bot_2_GPT6.quiet_hours", return_value=True):
            task = asyncio.create_task(self.bot.playback_loop())
            await asyncio.sleep(0)
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        self.assertEqual(self.bot.queue.preview(), ["song"])
        self.assertIsNone(self.bot.current)
