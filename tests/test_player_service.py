import unittest

from hearts.services.player import PlayerService, PlayerStateError


class TestPlayerService(unittest.TestCase):

    def setUp(self):
        self.svc = PlayerService()

    def test_get_player_not_found(self):
        data = self.svc.get_player(1234)
        self.assertIsNone(data)

    def test_create_player(self):
        player_id = self.svc.create_player("Joe", "password")
        player = self.svc.get_player(player_id)

        expected = {
            "id": player_id,
            "name": "Joe"
        }

        self.assertEqual(expected, player)

    def test_create_player_duplicate(self):
        self.svc.create_player("Jimbob", "password")

        self.svc.create_player("Billy", "password")

        try:
            self.svc.create_player("Jimbob", "asdf")
            self.fail("Expected to throw")
        except PlayerStateError:
            pass  # test passed

    def test_create_player_duplicate_ids(self):
        """
        Test that we don't skip ID numbers
        when failing to create a player
        due to duplicate name.
        """
        first_id = self.svc.create_player("Joe", "asdf")

        try:
            self.svc.create_player("Joe", "asdf")
        except PlayerStateError:
            pass

        second_id = self.svc.create_player("Charlie", "asdf")

        self.assertEqual(first_id + 1, second_id)

    def test_get_id(self):
        player_id = self.svc.create_player("Steve", "asdf")
        fetched_id = self.svc.get_player_id("Steve")

        self.assertEqual(player_id, fetched_id)

    def test_get_by_name(self):
        player_id = self.svc.create_player("Jimmy", "password")
        player = self.svc.get_player_by_name("Jimmy")

        expected = {
            "id": player_id,
            "name": "Jimmy"
        }
        self.assertEqual(expected, player)

    def test_ids_not_equal(self):
        j_id = self.svc.create_player("Jimmy", "password")
        b_id = self.svc.create_player("Bob", "password")

        self.assertNotEqual(b_id, j_id)

        jimmy = self.svc.get_player(j_id)
        bob = self.svc.get_player(b_id)

        self.assertEqual("Jimmy", jimmy["name"])
        self.assertEqual("Bob", bob["name"])


if __name__ == '__main__':
    unittest.main()
