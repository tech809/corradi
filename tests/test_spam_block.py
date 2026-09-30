"""El bloqueo automático solo se activa al quinto rechazo consecutivo."""
from types import SimpleNamespace
from unittest import IsolatedAsyncioTestCase
from unittest.mock import patch

from app import pipeline


class SpamBlockTest(IsolatedAsyncioTestCase):
    async def test_spam_block_threshold(self):
        statuses = []
        blocked = []

        async def recent_statuses(_user_id, limit):
            return statuses[:limit]

        async def block_user(user_id, reason):
            blocked.append((user_id, reason))

        with (patch.object(pipeline, "cfg", SimpleNamespace(spam_block_threshold=5, admin_telegram_ids=[])),
              patch.object(pipeline.repo, "recent_statuses", recent_statuses),
              patch.object(pipeline.repo, "block_user", block_user)):
            statuses[:] = ["not_opportunity"] * 4
            self.assertEqual(await pipeline._spam_check(6908780215), {"warn": True, "blocked": False})
            self.assertEqual(blocked, [])

            statuses[:] = ["not_opportunity"] * 5
            self.assertEqual(await pipeline._spam_check(6908780215), {"warn": False, "blocked": True})
            self.assertEqual(blocked, [(6908780215, "spam_auto")])

            statuses[:] = ["not_opportunity", "created", "not_opportunity", "not_opportunity", "not_opportunity"]
            self.assertEqual(await pipeline._spam_check(6908780215), {"warn": True, "blocked": False})
