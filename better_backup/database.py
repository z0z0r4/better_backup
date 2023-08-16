from pydal import DAL, Field
from better_backup.config import config

database: DAL = None


def load_database():
    global database
    database = DAL("sqlite://storage.db", folder=config.backup_data_path)
    
    if "files" not in database.tables:
        database.define_table("files", Field("backup_uuid"), Field("name"), Field("hash"), Field("hash_type"), Field("path"))
    if "backups" not in database.tables:
        database.define_table("backups", Field("uuid"), Field("time", type="integer"), Field("size", type="integer"), Field("message"))
    
load_database()