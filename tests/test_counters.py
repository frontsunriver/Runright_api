from lib.counter import Counters
import unittest


from lib.db import Db

class TestCounters(unittest.TestCase):
    def setUp(self) -> None:
        database = Db('127.0.0.1')
        self.db = database.get_database('avaclone-unittests')
        return super().setUp()

    def test_get_next(self):
        # Ensure there are no existing counters
        self.db.counters.delete_many({})
        counters = Counters(self.db)
        # Ensure first counter is 1
        self.assertEqual(counters._get_next('example_counter'), 1)
        # Ensure next is 2
        self.assertEqual(counters._get_next('example_counter'), 2)
        for _ in range(20):
            counters._get_next('example_counter')
        
        self.assertEqual(counters._get_next('example_counter'), 23)
