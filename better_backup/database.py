from pydal import DAL, Field
import os
from better_backup.config import config

database: DAL = None


def load_database():
    global database
    os.makedirs(config.backup_data_path, exist_ok=True)
    database = DAL("sqlite://storage.db", folder=config.backup_data_path)

    database.define_table("files",
                          Field("backup_uuid"),
                          Field("name"),
                          Field("hash"),
                          Field("hash_type"),
                          Field("path")
                        )
    database.define_table("count",
                          Field("hash"),
                          Field("count", type="integer", default=0)
                        )
    database.define_table("backups", 
                          Field("uuid"), 
                          Field("time", type="integer"), 
                          Field("size", type="integer"), 
                          Field("message"), 
                          Field("locked", type="boolean", default=False)
                        )


load_database()
