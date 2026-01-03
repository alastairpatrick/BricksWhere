from model.db import create_connection, connection_ctx


class MainViewModel:
    def __init__(self, db_path: str = "data.db"):
        self.db_path = db_path
