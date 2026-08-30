# -*- coding: utf-8 -*-
"""The free edition's capacity limit: one draft and one live, per person.

Counted per owner rather than per database, so a whole team can try the
product. The tests below pin the two things that would quietly break it: an
archived dashboard still counting, and publishing being a route around the
create check.
"""
import json

from odoo.exceptions import ValidationError
from odoo.tests import TransactionCase, tagged

from .test_spec import minimal


@tagged("post_install", "-at_install")
class TestQuota(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.alice = cls.env["res.users"].create({
            "name": "Quota Alice", "login": "ai_quota_alice",
            "group_ids": [(6, 0, [cls.env.ref("base.group_user").id])],
        })
        cls.bob = cls.env["res.users"].create({
            "name": "Quota Bob", "login": "ai_quota_bob",
            "group_ids": [(6, 0, [cls.env.ref("base.group_user").id])],
        })

    def _make(self, user, state="draft", name="Board"):
        return self.env["ai.dashboard"].with_user(user).create({
            "name": name,
            "spec_json": json.dumps(minimal()),
            "state": state,
        })

    # ------------------------------------------------------------- the limit
    def test_a_second_draft_is_refused(self):
        self._make(self.alice, "draft", "First")
        with self.assertRaises(ValidationError):
            self._make(self.alice, "draft", "Second")

    def test_a_second_live_dashboard_is_refused(self):
        self._make(self.alice, "published", "First")
        with self.assertRaises(ValidationError):
            self._make(self.alice, "published", "Second")

    def test_one_of_each_is_allowed(self):
        """The states are counted separately: a draft in progress must not
        block the live dashboard somebody is already using."""
        self._make(self.alice, "draft", "Draft")
        self._make(self.alice, "published", "Live")

    def test_the_refusal_says_what_to_do_about_it(self):
        self._make(self.alice, "draft", "First")
        with self.assertRaises(ValidationError) as caught:
            self._make(self.alice, "draft", "Second")
        message = str(caught.exception)
        self.assertIn("publish or discard", message.lower())
        self.assertIn("Pro", message, "a limit has to name the way past it")

    # ------------------------------------------------------------ per person
    def test_the_limit_is_per_person_not_per_database(self):
        """A team has to be able to try this, or the free edition is a demo."""
        self._make(self.alice, "published", "Alice's")
        self._make(self.bob, "published", "Bob's")   # must not raise

    # --------------------------------------------------------- the loopholes
    def test_publishing_a_second_dashboard_is_refused_too(self):
        """create() is not the only door: a draft promoted with action_publish
        would otherwise walk straight past the limit."""
        self._make(self.alice, "published", "Live")
        draft = self._make(self.alice, "draft", "Draft")
        with self.assertRaises(ValidationError):
            draft.with_user(self.alice).action_publish()

    def test_an_archived_dashboard_still_counts(self):
        """Archiving is not deleting - it is still theirs and still
        restorable, so letting it free a slot hands out unlimited dashboards
        to anyone who notices."""
        board = self._make(self.alice, "published", "Live")
        board.with_user(self.alice).write({"active": False})
        with self.assertRaises(ValidationError):
            self._make(self.alice, "published", "Another")

    def test_discarding_a_draft_frees_the_slot(self):
        """The way out has to actually work, or the limit is a wall."""
        draft = self._make(self.alice, "draft", "First")
        draft.with_user(self.alice).action_discard()
        self._make(self.alice, "draft", "Second")   # must not raise

    def test_publishing_a_draft_frees_the_draft_slot(self):
        draft = self._make(self.alice, "draft", "First")
        draft.with_user(self.alice).action_publish()
        self.assertEqual(draft.state, "published")
        self._make(self.alice, "draft", "Next")     # must not raise

    def test_handing_a_dashboard_over_respects_the_new_owner_quota(self):
        """owner_id is the third door into the same count."""
        self._make(self.bob, "published", "Bob's own")
        board = self._make(self.alice, "published", "Alice's")
        with self.assertRaises(ValidationError):
            board.sudo().write({"owner_id": self.bob.id})
