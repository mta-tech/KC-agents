import psycopg2
from contextlib import contextmanager

class PostgreSQLDatabase:
    def __init__(self, connection=None):
        self.connection = connection

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()
    
    def connect(self, url=None):
        if url:
            self.connection = psycopg2.connect(url)
        elif not self.connection:
            raise ValueError("Connection is not established")

    def disconnect(self):
        if self.connection:
            self.connection.close()
            self.connection = None

    def connect_with_url(self, url):
        self.connect(url)

    def upsert(self, table_name, data):
        cursor = self.connection.cursor()
        column_names = data.keys()
        column_values = [data[k] for k in column_names]
        update_clause = ', '.join([f"{col} = %s" for col in column_names])
        try:
            cursor.execute(f"INSERT INTO {table_name} ({', '.join(column_names)}) "
                           f"VALUES ({', '.join(['%s'] * len(column_names) )}) "
                           f"ON CONFLICT (id) DO UPDATE SET {update_clause}", column_values + column_values)
            self.connection.commit()
        except Exception as e:
            self.connection.rollback()
            raise e
        finally:
            cursor.close()

    def delete(self, table_name, _id):
        cursor = self.connection.cursor()
        try:
            cursor.execute(f"DELETE FROM {table_name} WHERE id = %s", (_id,))
            self.connection.commit()
        except Exception as e:
            self.connection.rollback()
            raise e
        finally:
            cursor.close()

    def get(self, table_name, _id):
        cursor = self.connection.cursor()
        cursor.execute(f"SELECT * FROM {table_name} WHERE id = %s", (_id,))
        result = cursor.fetchone()
        cursor.close()
        return result

    def get_all(self, table_name):
        cursor = self.connection.cursor()
        cursor.execute(f"SELECT * FROM {table_name}")
        results = cursor.fetchall()
        cursor.close()
        return results

    def run_sql(self, sql):
        cursor = self.connection.cursor()
        print(sql)
        cursor.execute(sql)
        try:
            result = cursor.fetchall()  # Use fetchall to get the query results
        except:
            result = 'SUCCESS'
        cursor.close()
        self.connection.commit()  # You can commit here or in the calling code
        return result
      
    def get_table_definition(self, table_name):
        cursor = self.connection.cursor()
        cursor.execute("SELECT column_name FROM information_schema.columns WHERE columns.table_name = %s", (table_name,))
        result = cursor.fetchone()
        cursor.close()
        if result:
            return result[0]
        else:
            return None


    def get_all_table_names(self):
        cursor = self.connection.cursor()
        cursor.execute("SELECT tablename FROM pg_tables ")
        results = cursor.fetchall()
        cursor.close()
        return [result[0] for result in results]

    def get_table_definitions_for_prompt(self):
        table_definitions = {}
        table_names = self.get_all_table_names()
        for table_name in table_names:
            table_definition = self.get_table_definition(table_name)
            if table_definition:
                table_definitions[table_name] = table_definition
        return table_definitions
