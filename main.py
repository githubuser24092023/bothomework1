from aiogram import Bot, Dispatcher, types, executor
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters import Command
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage
import sqlite3
import requests
import os
from dotenv import load_dotenv

path = 'app_data\\hw1.db'



database = sqlite3.connect(path)
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

load_dotenv()
api_token = os.getenv('API_TOKEN')
bot = Bot(token=api_token)

storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)


class StatesCollection(StatesGroup):
    typing_user_name = State()
    typing_user_budget = State()
    purc_fetching_indx = State()
    sell_fetching_indx = State()



def get_stock_price(stock_indx):
  url = f"https://iss.moex.com/iss/engines/stock/markets/shares/boards/TQBR/securities/{stock_indx}.json?iss.only=securities&securities.columns=PREVPRICE,CURRENCYID"
  responce = requests.get(url)
  if responce.status_code == 200:
    stock_info = responce.json().get("securities", {}).get('data', [[]])
    if len(stock_info) > 0:
      return float(stock_info[0][0])
  return None



@dp.message_handler(commands=['purchase_stock'])
async def purchase_stock(message: types.Message):
  await StatesCollection.purc_fetching_indx.set()
  await bot.send_message(message.chat.id, "Type stock INDEX")



@dp.message_handler(state=StatesCollection.purc_fetching_indx)
async def get_purc_stock_indx(message: types.Message, state: FSMContext):
  cost = get_stock_price(message.text)
  budget = get_budget(message.from_user.id)
  if cost is None:
    await bot.send_message(message.chat.id, f"No information about {message.text}")
  else:
    if cost > budget:
      await bot.send_message(message.chat.id, f"You have no money to buy {message.text}")
    else:
      database.execute(f"insert into stock_contract values({message.from_user.id}, '{message.text}', {cost});")
      await bot.send_message(message.chat.id, "Purchased")
  await state.finish()



@dp.message_handler(commands=['sell_stock'])
async def sell_stock(message: types.Message):
  await StatesCollection.sell_fetching_indx.set()
  await bot.send_message(message.chat.id, "Type stock INDEX")



@dp.message_handler(state=StatesCollection.sell_fetching_indx)
async def get_sell_stock_indx(message: types.Message, state: FSMContext):
  exists = database.cursor().execute(f"""
                                         select count(*) from stock_contract 
                                           where telegram_id = {message.chat.id}
                                             and indx = '{message.text}';
                                      """).fetchone()[0]
  if exists == 0:
    await bot.send_message(message.chat.id, f"You have no stock {message.text}")
  else:
    database.execute(f"""
                      delete from stock_contract where
                        rowid = (
                                 select min(rowid) from stock_contract 
                                   where telegram_id = {message.from_user.id} 
                                     and indx = '{message.text}'
                                );
                      """)
    await bot.send_message(message.chat.id, f"Sold")
  await state.finish()


def check_user_exists(user_id):
  return database.cursor().execute(f'select count(1) from user where telegram_id = {user_id};').fetchone()[0]


@dp.message_handler(commands=['start'])
async def start_command(message: types.Message):
  await bot.send_message(message.chat.id, "Type /help to see commands you can use.\n\nWelcome to finance_bot.")
  if check_user_exists(message.from_user.id) == 0:
    await StatesCollection.typing_user_name.set()
    await bot.send_message(message.chat.id, "Let's create your profile: type your name")
  else:
    await bot.send_message(message.chat.id, "Your profile already created")



@dp.message_handler(commands=['help'])
async def help_command(message: types.Message):
  msg = "/sell_stock - Sell stock (requires stock's index, allows you to sell 1 stock)\n\n"
  msg += "/purchase_stock - Purchase stock (requires stock's index, allows you to purchase 1 stock)\n\n"
  msg += "/get_user_info - Get Info about yourself (allows you to see all your stocks)"
  await bot.send_message(message.chat.id, msg)


def create_user(telegram_id, name):
  database.execute(f"insert into user(telegram_id, name) values({telegram_id}, '{name}');")
  database.commit()


@dp.message_handler(state=StatesCollection.typing_user_name)
async def type_user_name(message: types.Message, state: FSMContext):
  create_user(message.from_user.id, message.text)
  await state.finish()
  await StatesCollection.typing_user_budget.set()
  await bot.send_message(message.chat.id, "Type budget you are planning (RUB)")


def update_budget(new_budget, user_id):
  database.execute(f"update user set budget = {new_budget} where telegram_id = {user_id};")
  database.commit()


@dp.message_handler(state=StatesCollection.typing_user_budget)
async def type_user_budget(message: types.Message, state: FSMContext):
  update_budget(message.text, message.from_user.id)
  await bot.send_message(message.chat.id, "Account created")
  await state.finish()


def get_budget(user_id):
  budget = database.cursor().execute(f"""
                                      select U.budget - ifnull(R.total_cost, 0) from
                                      (
                                        select telegram_id, budget from user
                                      ) U
                                        left join
                                        (
                                          select telegram_id, sum(cost) as total_cost from stock_contract
                                            group by telegram_id
                                        ) R
                                          on U.telegram_id = R.telegram_id
                                        where U.telegram_id = {user_id};
                                      """).fetchone()[0]
  return budget


def get_dividents_amt(user_id):
  estimated_dividents = database.cursor().execute(f"""
                                                    select ifnull(R.total_cost, 0) * 0.05 from
                                                    (
                                                      select telegram_id, budget from user
                                                    ) U
                                                      left join
                                                      (
                                                        select telegram_id, sum(cost) as total_cost from stock_contract
                                                          group by telegram_id
                                                      ) R
                                                        on U.telegram_id = R.telegram_id
                                                      where U.telegram_id = {user_id};
                                                  """).fetchone()[0]
  return round(estimated_dividents, 2)


@dp.message_handler(commands=['get_user_info'])
async def get_user_info(message: types.Message, state: FSMContext):
  name = database.cursor().execute(f'select name from user where telegram_id = {message.from_user.id}').fetchone()[0]

  budget = get_budget(message.from_user.id)
  estimated_dividents = get_dividents_amt(message.from_user.id)

  all_stocks = database.cursor().execute(f"""
                                          select indx, cost from stock_contract
                                            where telegram_id = {message.from_user.id};      
                                          """).fetchall()

  stock_info = ''
  for pair in all_stocks:
    stock_info += f'{pair[0]}   {pair[1]}\n'
  stock_info = stock_info.strip()

  msg = f'Your name: {name}\nYour budget (left): {budget}'
  if stock_info != '':
    msg += f'\n\nList of your stocks:\n{stock_info}'
    if estimated_dividents > 0:
      msg += f'\n\nDividents (about): {estimated_dividents}'

  await bot.send_message(message.chat.id, msg)



if __name__ == '__main__':
      executor.start_polling(dp, skip_updates=True)