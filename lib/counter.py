from pymongo.database import Database

class Counters():
    def __init__(self, db: Database):
        self.db = db

    def get_next_branch_counter(self):
        return str(self._get_next('branch')).zfill(4)

    def _get_next(self, counter_name: str):
        """Get the next value for a given counter name

        Args:
            counter_name (str): Name of the counter

        Returns:
            int: Current counter value
        """
        res = self.db.counters.find_and_modify(query={'_id': counter_name}, update={'$inc': {'value': 1}})

        if res is None:
            # Counter not found
            self._insert_default(counter_name)
            return self._get_next(counter_name)
        elif res['value'] < 1:
            # Counter value is zero, inc again
            return self._get_next(counter_name)
        
        # Counter exists and val > 0, return it
        return res['value']


    def _insert_default(self, counter_name: str):
        """Insert a new counter with a default value

        Args:
            counter_name (str): Name of counter to create
        """
        self.db.counters.insert_one({'_id': counter_name, 'value': 0})