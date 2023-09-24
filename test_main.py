import main
import unittest
import sqlite3

class UserTests(unittest.TestCase):
    def setUp(self):
        database = sqlite3.connect(main.path)
        database.execute("""
                           create table if not exists user
                           (
                             telegram_id int primary key,
                             name varchar(20) not null,
                             budget number check(budget > 0)
                           );
                         """)
        database.commit()
        database.close()


    def test_user_instantiation(self):
        # Test checks creation, existance and budget updating of user
        database = sqlite3.connect(main.path)
        main.create_user(-1, 'USER_TEST')
        result = bool(main.check_user_exists(-1))
        main.update_budget(8440, -1)
        result = result and main.get_budget(-1) == 8440
        database.close()
        self.assertTrue(result)


    def tearDown(self):
        database = sqlite3.connect(main.path)
        database.execute("delete from user where telegram_id = -1;")
        database.commit()
        database.close()



class StockTests(unittest.TestCase):
    def setUp(self):
        database = sqlite3.connect(main.path)
        database.execute("""
                           create table if not exists user
                           (
                             telegram_id int primary key,
                             name varchar(20) not null,
                             budget number check(budget > 0)
                           );
                         """)
        database.execute("""
                           create table if not exists stock_contract
                           (
                             telegram_id int,
                             indx varchar(10) not null,
                             cost number not null
                           );
                         """)
        database.commit()
        database.close()


    def test_stock_purchasing(self):
        # Test checks budget after purchasing stocks and dividends amount
        database = sqlite3.connect(main.path)
        main.create_user(-2, 'USER_TEST_1')
        main.update_budget(1000, -2)
        database.execute("insert into stock_contract values(-2, 'TEST', 240);")
        database.commit()
        result = main.get_budget(-2) == (1000 - 240)
        database.close()
        self.assertTrue(result)


    def test_fetch_stock_cost(self):
        # Test checks cost of real and imagine stocks
        failed_index_cost = main.get_stock_price('|-0-|-O-|-0-|')
        real_index_cost = main.get_stock_price('SBER')
        self.assertTrue(failed_index_cost is None and real_index_cost is not None)


    def tearDown(self):
        database = sqlite3.connect(main.path)
        database.execute("delete from user where telegram_id = -2;")
        database.commit()
        database.close()


if __name__ == '__main__':
    unittest.main()