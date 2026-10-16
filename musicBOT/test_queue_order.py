import unittest
from unittest.mock import AsyncMock, Mock, patch

from music_bot_2_GPT6 import FairQueue, MusicBot, Track


class QueueOrderTests(unittest.TestCase):
    def test_insert_and_move_preserve_fair_turns(self):
        queue = FairQueue()
        queue.add(1, ["a", "b", "c"])
        queue.add(2, ["x", "y"])
        queue.add(1, ["d", "e"], 2)
        queue.move(1, 5, 1)
        self.assertEqual(queue.preview(10), ["c", "x", "a", "y", "d", "e", "b"])
        queue.move(1, 1, 5)
        self.assertEqual(list(queue.queues[1]), ["a", "d", "e", "b", "c"])

    def test_invalid_positions_do_not_mutate_queue(self):
        queue = FairQueue()
        queue.add(1, ["a", "b"])
        for position in (0, 4):
            with self.assertRaises(ValueError):
                queue.add(1, ["c"], position)
        with self.assertRaises(ValueError):
            queue.move(1, 1, 3)
        with self.assertRaises(ValueError):
            queue.add(2, ["x"], 2)
        self.assertEqual(queue.preview(), ["a", "b"])
        self.assertEqual(list(queue.turns), [1])

    def test_shuffle_only_changes_own_tracks(self):
        queue = FairQueue()
        queue.add(1, ["a", "b", "c"])
        queue.add(2, ["x", "y"])
        with patch("music_bot_2_GPT6.random.shuffle", side_effect=lambda items: items.reverse()):
            queue.shuffle(1)
        self.assertEqual(queue.preview(), ["c", "x", "b", "y", "a"])


class CommandTests(unittest.IsolatedAsyncioTestCase):
    async def test_commands_and_slash_options(self):
        bot = MusicBot(1, "mpv", "deno")
        bot.refresh_prefetch = Mock()
        bot.update_dashboard = AsyncMock()
        reply = AsyncMock()
        author = Mock(id=1)
        tracks = [Track(1, "user", str(i), "url") for i in range(3)]
        bot.queue.add(1, tracks)
        try:
            await bot.handle_command(author, "/move 3 1", reply)
            self.assertIs(bot.queue.queues[1][0], tracks[2])
            await bot.handle_command(author, "/myqueue", reply)
            self.assertIn("1. 2", reply.call_args.args[0])
            bot.add_url = AsyncMock()
            await bot.handle_command(author, "/play https://youtu.be/abcdefghijk 2", reply)
            self.assertEqual(bot.add_url.call_args.args[-1], 2)
            params = {p.name: p for p in bot.tree.get_command("play").parameters}
            self.assertFalse(params["position"].required)
            self.assertEqual([p.name for p in bot.tree.get_command("move").parameters],
                             ["source", "destination"])
        finally:
            await bot.close()


if __name__ == "__main__":
    unittest.main()
