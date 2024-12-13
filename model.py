import psycopg2


class Model:

    def __init__(self):
        self.conn = psycopg2.connect(
            dbname='postgres',
            user='postgres',
            password='qwerty123',
            host='localhost',
            port=5432
        )

    def get_all_tables(self):
        c = self.conn.cursor()
        c.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")
        return c.fetchall()

    def get_all_columns(self, table_name):
        c = self.conn.cursor()
        c.execute("SELECT column_name FROM information_schema.columns WHERE table_name = %s", (table_name,))
        return c.fetchall()

    def add_data(self, table_name, columns, val):
        c = self.conn.cursor()
        columns_str = ', '.join(columns)
        placeholders = ', '.join(['%s'] * len(val))

        # Отримати всі значення ідентифікаторів
        c.execute(f'SELECT {table_name.lower()}_id FROM "public"."{table_name}"')
        existing_identifiers = c.fetchall()

        # Розділити значення ідентифікаторів на пробіли
        existing_identifiers = [item for sublist in existing_identifiers for item in sublist]

        # Перетворити значення ідентифікатора у відповідний тип
        identifier_column = f'{table_name.lower()}_id'
        identifier_index = columns.index(identifier_column)
        val[identifier_index] = int(val[identifier_index])

        # Перевірити, чи ідентифікатор вже існує
        if val[identifier_index] in existing_identifiers:
            return 2

        # Отримати всі колонки, які є зовнішніми ключами
        external_keys = [column for column in columns if column.endswith('_id') and column != identifier_column]

        for key_column in external_keys:
            # Отримати всі значення з таблиці, які відповідають зовнішньому ключу
            referenced_table = key_column[:-3].capitalize()
            c.execute(f'SELECT {key_column} FROM "public"."{referenced_table}"')
            referenced_values = [item for sublist in c.fetchall() for item in sublist]

            # Перевірити чи зовнішній ключ існує
            val_index = columns.index(key_column)
            val_id = int(val[val_index])

            if val_id not in referenced_values:
                return 3

        # Вставити дані
        c.execute(f'INSERT INTO "public"."{table_name}" ({columns_str}) VALUES ({placeholders})', val)
        self.conn.commit()
        return 1

    def update_data(self, table_name, column, id, new_value):
        c = self.conn.cursor()

        identifier_column = f'{table_name.lower()}_id'
        is_unique_identifier = identifier_column == column

        if is_unique_identifier:
            # Отримати всі значення ідентифікаторів
            c.execute(f'SELECT {table_name.lower()}_id FROM "public"."{table_name}"')
            existing_identifiers = c.fetchall()

            # Розділити значення ідентифікаторів на пробіли
            existing_identifiers = [item for sublist in existing_identifiers for item in sublist]

            val_id = int(new_value)
            # Перевірити, чи ідентифікатор існує
            if val_id in existing_identifiers:
                return 2
        elif column.endswith('_id'):
            # Отримати всі значення з таблиці, які відповідають зовнішньому ключу
            referenced_table = column[:-3].capitalize()
            c.execute(f'SELECT {column} FROM "public"."{referenced_table}"')
            referenced_values = [item for sublist in c.fetchall() for item in sublist]

            val_id = int(new_value)
            # Перевірити, чи ідентифікатор існує
            if val_id not in referenced_values:
                return 3

        # Оновити дані
        c.execute(f'UPDATE "public"."{table_name}" SET {column} = %s WHERE {identifier_column} = %s',
                  (new_value, id))
        self.conn.commit()
        return 1

    def delete_data(self, table_name, id):
        c = self.conn.cursor()

        # Отримати список всіх таблиць в базі даних
        c.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public' AND table_type = "
                  "'BASE TABLE'")
        tables = [item[0] for item in c.fetchall()]

        for current_table in tables:
            if current_table == table_name:
                continue  # Пропустити поточну таблицю

            c.execute("SELECT column_name FROM information_schema.columns WHERE table_name = %s", (current_table,))
            column_names = [item for sublist in c.fetchall() for item in sublist]
            for column_name in column_names:
                if column_name == f'{table_name.lower()}_id':
                    # Отримати всі колонки відповідної таблиці
                    c.execute(f'SELECT {column_name} FROM "public"."{current_table}"')
                    referenced_values = [item for sublist in c.fetchall() for item in sublist]
                    # Перевірити, чи зовнішній ключ існує
                    if id in referenced_values:
                        return 0
        # Видалити дані
        c.execute(f'DELETE FROM "public"."{table_name}" WHERE {table_name.lower()}_id = %s', (id,))
        self.conn.commit()
        return 1

    def generate_data(self, table_name, count):
        c = self.conn.cursor()
        c.execute(f"SELECT column_name, data_type FROM information_schema.columns WHERE table_name = %s", (table_name,))
        columns_info = c.fetchall()

        # Знайдемо назву ключового поля
        id_column = f'{table_name.lower()}_id'

        # Генеруємо значення для всіх інших полів
        for i in range(count):
            insert_query = f'INSERT INTO "public"."{table_name}" ('
            select_subquery = ""

            for column_info in columns_info:
                column_name = column_info[0]
                column_type = column_info[1]

                if column_name == id_column:
                    c.execute(f'SELECT max("{id_column}") FROM "public"."{table_name}"')
                    max_id = c.fetchone()[0] or 0
                    select_subquery += f'{max_id + 1},'
                elif column_name.endswith('_id'):
                    related_table_name = column_name[:-3].capitalize()
                    # Знаходимо існуючий id з відповідної таблиці
                    c.execute(f'SELECT {related_table_name.lower()}_id FROM "public"."{related_table_name}" ORDER '
                              f'BY RANDOM() LIMIT 1')
                    related_id = c.fetchone()[0]
                    select_subquery += f'{related_id},'
                elif column_type == 'integer':
                    select_subquery += f'trunc(random()*100)::INT,'
                elif column_type == 'character varying':
                    select_subquery += f"'Text {column_name}',"
                elif column_type == 'date':
                    select_subquery += "'2022-01-01',"
                elif column_type == 'timestamp with time zone':
                    select_subquery += "'2022-01-01 08:30:00+03',"
                else:
                    continue

                insert_query += f'"{column_name}",'

            insert_query = insert_query.rstrip(',') + f') VALUES ({select_subquery[:-1]})'
            c.execute(insert_query)

        self.conn.commit()
