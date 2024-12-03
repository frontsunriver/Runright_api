from pymongo import MongoClient


class Db(object):

    def __init__(self, host):
        self.host = host
        self.connect()

    def connected(self):
        return hasattr(self, "_connection") and self._connection

    def connect(self):
        # Already connected?
        if self.connected():
            return
        try:
            self._connection = MongoClient(
                "mongodb://{}".format(self.host),
                connect=False)
        except:
            self._connection = None

    # Return our database instance
    def get_database(self, dbname):
        self.connect()
        return self._connection[dbname]