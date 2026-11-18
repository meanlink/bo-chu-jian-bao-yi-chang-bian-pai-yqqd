from sqlalchemy import inspect, text
from src.config.database import Base, engine
from src import models

# create_all only creates missing tables; add columns introduced after the first release.
ADDED_COLUMNS = {
    'jobs': {'started_at': 'DOUBLE', 'approved_at': 'DOUBLE'},
}

def migrate():
    Base.metadata.create_all(engine)
    inspector = inspect(engine)
    with engine.begin() as connection:
        for table, columns in ADDED_COLUMNS.items():
            if table not in inspector.get_table_names():
                continue
            existing = {column['name'] for column in inspector.get_columns(table)}
            for name, kind in columns.items():
                if name not in existing:
                    connection.execute(text(f'ALTER TABLE {table} ADD COLUMN {name} {kind} NULL'))

if __name__=='__main__':migrate()
