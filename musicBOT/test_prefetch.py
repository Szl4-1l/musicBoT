import asyncio
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, Mock

from music_bot_2_GPT6 import MusicBot, Track


class PrefetchTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.bot = MusicBot(1, "mpv", "deno")
        self.bot.run_process = AsyncMock()

    async def asyncTearDown(self):
        await self.bot.close()

    def tracks(self, user, count):
        return [Track(user, str(user), str(i), f"https://example.com/{user}/{i}")
                for i in range(count)]

    async def test_fair_order_reuses_download_and_cleans_removed(self):
        async def download(track):
            directory = tempfile.TemporaryDirectory(prefix="prefetch-test-")
            return directory, Path(directory.name) / "audio.webm"
        self.bot.download_track = AsyncMock(side_effect=download)
        first = self.tracks(1, 5)
        self.bot.queue.add(1, first)
        self.bot.refresh_prefetch()
        await asyncio.sleep(0)
        retained = self.bot.downloads[id(first[0])]
        removed_root = self.bot.downloads[id(first[2])].result()[0].name
        second = self.tracks(2, 3)
        self.bot.queue.add(2, second)
        self.bot.refresh_prefetch()
        await asyncio.sleep(0)
        self.assertEqual(set(self.bot.downloads), {id(first[0]), id(second[0]), id(first[1])})
        self.assertIs(self.bot.downloads[id(first[0])], retained)
        self.assertFalse(Path(removed_root).exists())
        self.bot.current = self.bot.queue.next()
        self.bot.refresh_prefetch()
        self.assertEqual(len(self.bot.downloads), 4)
        self.assertIs(self.bot.downloads[id(first[0])], retained)
        self.bot.queue.clear()
        self.bot.refresh_prefetch()
        self.assertEqual(set(self.bot.downloads), {id(self.bot.current)})

    async def test_removed_pending_download_is_cancelled(self):
        async def pending(track):
            await asyncio.Event().wait()
        self.bot.download_track = AsyncMock(side_effect=pending)
        self.bot.queue.add(1, self.tracks(1, 3))
        self.bot.refresh_prefetch()
        tasks = list(self.bot.downloads.values())
        await asyncio.sleep(0)
        self.bot.queue.clear_user(1)
        self.bot.refresh_prefetch()
        await asyncio.gather(*tasks, return_exceptions=True)
        self.assertTrue(all(task.cancelled() for task in tasks))

    async def test_playback_uses_prefetched_audio(self):
        directory = Mock(name="directory")
        directory.name = str(Path.cwd())
        audio = Path(directory.name) / "prefetched.webm"
        self.bot.download_track = AsyncMock(return_value=(directory, audio))
        self.bot.wait_until_ready = AsyncMock()
        self.bot.update_dashboard = AsyncMock()
        self.bot.say = AsyncMock()
        started = asyncio.Event()
        async def play(args, **kwargs):
            started.set()
            await asyncio.Event().wait()
        self.bot.run_process.side_effect = play
        self.bot.queue.add(1, self.tracks(1, 1))
        self.bot.refresh_prefetch()
        await asyncio.sleep(0)
        self.bot.worker = asyncio.create_task(self.bot.playback_loop())
        await asyncio.wait_for(started.wait(), 2)
        self.assertEqual(self.bot.download_track.await_count, 1)
        args = self.bot.run_process.call_args.args[0]
        self.assertEqual(args[-1], str(audio))
        self.assertTrue(any("loudnorm=" in arg for arg in args))
        await self.bot.close()
        await asyncio.sleep(0)
        directory.cleanup.assert_called_once()

    async def test_failed_download_removes_temporary_directory(self):
        roots = []
        async def fail(args, **kwargs):
            roots.append(Path(args[args.index("-o") + 1]).parent)
            raise RuntimeError("download failed")
        self.bot.run_process.side_effect = fail
        with self.assertRaisesRegex(RuntimeError, "download failed"):
            await self.bot.download_track(self.tracks(1, 1)[0])
        self.assertFalse(roots[0].exists())


if __name__ == "__main__":
    unittest.main()
