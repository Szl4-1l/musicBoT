import asyncio
import json
import os
from pathlib import Path
import tempfile
import music_bot
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock

from music_bot import MusicBot, ProcessError, Skipped, normalize_url, track_url


class UrlTests(unittest.TestCase):
    def test_supported_urls(self):
        cases = {
            'https://youtu.be/abcdefghijk?t=20': ('https://www.youtube.com/watch?v=abcdefghijk', False),
            'https://www.youtube.com/playlist?list=PL123': ('https://www.youtube.com/playlist?list=PL123', True),
            'https://www.nicovideo.jp/watch/sm123?from=share': ('https://www.nicovideo.jp/watch/sm123', False),
            'https://nico.ms/so123': ('https://www.nicovideo.jp/watch/so123', False),
            'https://sp.nicovideo.jp/watch/nm123': ('https://www.nicovideo.jp/watch/nm123', False),
            'https://www.nicovideo.jp/watch/123': ('https://www.nicovideo.jp/watch/123', False),
            'https://www.nicovideo.jp/user/7/mylist/123': ('https://www.nicovideo.jp/mylist/123', True),
            'https://www.nicovideo.jp/series/123': ('https://www.nicovideo.jp/series/123', True),
        }
        for raw, expected in cases.items():
            with self.subTest(raw=raw):
                self.assertEqual(normalize_url(raw), expected)

    def test_rejected_urls(self):
        for url in ['https://evil.test/watch/sm1', 'https://nicovideo.jp.evil.test/watch/sm1',
                    'https://name:secret@www.nicovideo.jp/watch/sm1',
                    'https://www.nicovideo.jp:8080/watch/sm1',
                    'https://www.nicovideo.jp/watch/lv123',
                    'https://www.nicovideo.jp/watch/sm1/extra']:
            with self.subTest(url=url), self.assertRaises(ValueError):
                normalize_url(url)
        with self.assertRaises(ValueError):
            normalize_url('https://nico.ms/sm1', force_playlist=True)

    def test_source_specific_ids(self):
        self.assertEqual(track_url({'id': 'sm123'}, 'https://www.nicovideo.jp/mylist/1'),
                         'https://www.nicovideo.jp/watch/sm123')
        self.assertIsNone(track_url({'id': 'sm123'}, 'https://www.youtube.com/playlist?list=PL1'))
        self.assertIsNone(track_url({'id': '../evil'}, 'https://www.nicovideo.jp/mylist/1'))


class BotTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.bot = MusicBot(1, 'mpv', 'deno')
        self.bot.say = AsyncMock()
        self.bot.update_dashboard = AsyncMock()

    async def asyncTearDown(self):
        await self.bot.close()

    async def test_slash_skip_and_stop_use_player_shutdown(self):
        user = SimpleNamespace(id=1, guild_permissions=SimpleNamespace(manage_guild=True))
        self.bot.current = SimpleNamespace(user_id=1)
        self.bot.skip_current = AsyncMock()
        reply = AsyncMock()
        interaction = SimpleNamespace(guild=object(), channel_id=1, user=user,
            response=SimpleNamespace(defer=AsyncMock()),
            followup=SimpleNamespace(send=AsyncMock()))
        await self.bot.slash_command(interaction, 'skip')
        self.bot.skip_current.assert_awaited_once()
        await self.bot.handle_command(user, '!stop', reply)
        self.assertEqual(self.bot.skip_current.await_count, 2)
        self.assertTrue(self.bot.stopped)
        self.bot.update_dashboard.assert_awaited()
        interaction.followup.send.assert_awaited_once()

    async def test_slash_commands_are_registered(self):
        self.assertEqual({c.name for c in self.bot.tree.get_commands()},
            {'ping', 'help', 'queue', 'now', 'skip', 'pause', 'resume', 'clear', 'stop', 'play', 'playlist'})
        self.assertEqual([p.name for p in self.bot.tree.get_command('play').parameters], ['url'])

    async def test_process_error_includes_stderr(self):
        with self.assertRaises(ProcessError) as caught:
            await self.bot.run_process([sys.executable, '-c',
                                        'import sys; sys.stderr.write("ERROR: extractor failed"); sys.exit(3)'])
        self.assertIn('extractor failed', str(caught.exception))
        self.assertIn('3', str(caught.exception))
        self.assertFalse(self.bot.processes)

    async def test_timeout_and_skip_cleanup(self):
        with self.assertRaises(TimeoutError):
            await self.bot.run_process([sys.executable, '-c', 'import time; time.sleep(10)'], timeout=0.05)
        self.assertFalse(self.bot.processes)
        task = asyncio.create_task(self.bot.run_process(
            [sys.executable, '-c', 'import time; time.sleep(10)']))
        await asyncio.sleep(0.05)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertFalse(self.bot.processes)
        skip = asyncio.Event()
        task = asyncio.create_task(self.bot.run_process(
            [sys.executable, '-c', 'import time; time.sleep(10)'], skip=skip))
        await asyncio.sleep(0.05)
        skip.set()
        with self.assertRaises(Skipped):
            await task
        self.assertFalse(self.bot.processes)

    async def test_nico_registration_and_public_error(self):
        user = SimpleNamespace(id=1, display_name='User')
        reply = AsyncMock()
        self.bot.run_process = AsyncMock(return_value=json.dumps(
            {'id': 'sm123', 'title': 'Nico', 'duration': 30}).encode())
        await self.bot.add_url(user, 'https://nico.ms/sm123', False, reply)
        self.assertEqual(self.bot.queue.preview()[0].url, 'https://www.nicovideo.jp/watch/sm123')
        self.bot.run_process.side_effect = ProcessError('ERROR: permission denied')
        await self.bot.handle_command(user, '!play https://nico.ms/sm123', reply)
        self.assertIn('permission denied', self.bot.say.call_args.args[0])
        self.assertTrue(self.bot.say.call_args.kwargs['error'])

    async def test_redaction_and_repeated_error(self):
        self.bot.http.token = 'secret-bot-token'
        error = RuntimeError('secret-bot-token https://example.test/media?signature=secret Cookie=session')
        await self.bot.report_error('test', error, repeat=True)
        await self.bot.report_error('test', error, repeat=True)
        self.bot.say.assert_awaited_once()
        text = self.bot.say.call_args.args[0]
        self.assertNotIn('secret-bot-token', text)
        self.assertNotIn('signature=secret', text)
        self.assertNotIn('session', text)


class SkipTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.bot = music_bot.MusicBot.__new__(music_bot.MusicBot)
        self.bot.processes = set()
        self.bot.skip_event = asyncio.Event()
        self.bot.ipc_path = "test-player"
        self.bot.phase = "再生中"
        self.bot.send_ipc = AsyncMock()

    async def test_skip_quits_player_and_signals_worker(self):
        await self.bot.skip_current()
        self.bot.send_ipc.assert_awaited_once_with(["quit"])
        self.assertTrue(self.bot.skip_event.is_set())

    async def test_ipc_failure_still_signals_worker(self):
        self.bot.send_ipc.side_effect = ValueError("player not ready")
        await self.bot.skip_current()
        self.assertTrue(self.bot.skip_event.is_set())

    async def test_skip_during_download(self):
        self.bot.phase = "準備中"
        await self.bot.skip_current()
        self.bot.send_ipc.assert_not_awaited()
        self.assertTrue(self.bot.skip_event.is_set())

    async def test_skip_does_not_signal_next_track(self):
        original = self.bot.skip_event

        async def advance(command):
            self.bot.skip_event = asyncio.Event()

        self.bot.send_ipc.side_effect = advance
        await self.bot.skip_current()
        self.assertTrue(original.is_set())
        self.assertFalse(self.bot.skip_event.is_set())

    async def wait_for_process(self):
        async with asyncio.timeout(5):
            while not self.bot.processes:
                await asyncio.sleep(0.01)
        return next(iter(self.bot.processes))

    async def test_skip_terminates_running_process(self):
        task = asyncio.create_task(self.bot.run_process(
            [sys.executable, "-c", "import time; time.sleep(60)"],
            skip=self.bot.skip_event,
        ))
        try:
            proc = await self.wait_for_process()
            self.bot.skip_event.set()
            with self.assertRaises(music_bot.Skipped):
                await asyncio.wait_for(task, 10)
            self.assertIsNotNone(proc.returncode)
            self.assertFalse(self.bot.processes)
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    @unittest.skipUnless(os.name == "nt", "Windows process tree regression")
    async def test_skip_terminates_child_that_holds_audio_file(self):
        # 子プロセスがファイルと出力パイプを保持するランチャーを再現する。
        with tempfile.TemporaryDirectory() as directory:
            audio = Path(directory) / "audio.tmp"
            ready = Path(directory) / "ready"
            child = (
                "import pathlib, sys, time; "
                "f = open(sys.argv[1], 'wb'); "
                "pathlib.Path(sys.argv[2]).touch(); time.sleep(20)"
            )
            parent = (
                "import subprocess, sys; "
                "p = subprocess.Popen([sys.executable, '-c', sys.argv[1], *sys.argv[2:]]); "
                "p.wait()"
            )
            task = asyncio.create_task(self.bot.run_process(
                [sys.executable, "-c", parent, child, str(audio), str(ready)],
                skip=self.bot.skip_event,
            ))
            try:
                async with asyncio.timeout(5):
                    while not ready.exists():
                        await asyncio.sleep(0.02)
                self.bot.skip_event.set()
                with self.assertRaises(music_bot.Skipped):
                    await asyncio.wait_for(task, 10)
                audio.unlink()  # 子が残っていればWindowsでは削除できない。
                self.assertFalse(self.bot.processes)
            finally:
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)


if __name__ == '__main__':
    unittest.main()
