import asyncio
import os
from datetime import datetime

import aiohttp
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN missing in .env")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

transactions = []

CURRENCIES = ["USD", "EUR", "RUB", "GBP", "AMD"]
BUY_RATE_DISCOUNT = 0.02


class TransactionState(StatesGroup):
    currency = State()
    amount = State()
    source = State()


class CalculatorState(StatesGroup):
    from_currency = State()
    amount = State()
    to_currency = State()


class ExchangeState(StatesGroup):
    from_currency = State()
    amount = State()
    to_currency = State()
    confirm = State()


main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="➕ Add Income"), KeyboardButton(text="➖ Add Expense")],
        [KeyboardButton(text="💼 Balance"), KeyboardButton(text="📜 History")],
        [KeyboardButton(text="🧮 Calculator"), KeyboardButton(text="🔄 Exchange")],
    ],
    resize_keyboard=True,
)

currency_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="USD"), KeyboardButton(text="EUR")],
        [KeyboardButton(text="RUB"), KeyboardButton(text="GBP")],
        [KeyboardButton(text="AMD")],
        [KeyboardButton(text="Cancel")],
    ],
    resize_keyboard=True,
)

confirm_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="✅ Save"), KeyboardButton(text="❌ No")],
        [KeyboardButton(text="Cancel")],
    ],
    resize_keyboard=True,
)


def is_button(message: types.Message, text: str) -> bool:
    return bool(message.text and text.lower() in message.text.lower())


async def cancel_action(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer("Action cancelled.", reply_markup=main_keyboard)


def parse_amount(text: str):
    try:
        amount = float(text.replace(",", ".").strip())
        if amount <= 0:
            return None
        return amount
    except Exception:
        return None


def calculate_balance(user_id: int):
    balances = {}

    for transaction in transactions:
        if transaction["user_id"] != user_id:
            continue

        currency = transaction["currency"]
        balances.setdefault(currency, 0.0)

        if transaction["type"] in ["income", "exchange_in"]:
            balances[currency] += transaction["amount"]
        elif transaction["type"] in ["expense", "exchange_out"]:
            balances[currency] -= transaction["amount"]

    return {
        currency: amount
        for currency, amount in balances.items()
        if abs(amount) > 0.0001
    }


async def convert_currency_buy_rate(
    amount: float,
    from_currency: str,
    to_currency: str,
):
    """
    API is called ONLY when user requests calculation/exchange.
    No background requests.
    """

    from_code = from_currency.lower()
    to_code = to_currency.lower()

    url = (
        "https://cdn.jsdelivr.net/npm/@fawazahmed0/"
        f"currency-api@latest/v1/currencies/{from_code}.json"
    )

    async with aiohttp.ClientSession() as session:
        async with session.get(url, timeout=10) as response:
            if response.status != 200:
                raise RuntimeError(f"Currency API error: HTTP {response.status}")

            data = await response.json()

            rates = data.get(from_code)
            if not isinstance(rates, dict):
                raise RuntimeError("Currency API returned invalid data")

            market_rate = rates.get(to_code)
            if market_rate is None:
                raise RuntimeError(f"Rate {from_currency}->{to_currency} not found")

            market_rate = float(market_rate)
            buy_rate = market_rate * (1 - BUY_RATE_DISCOUNT)
            converted = amount * buy_rate

            return converted, market_rate, buy_rate


@dp.message(CommandStart())
async def start(message: types.Message, state: FSMContext):
    await state.clear()
    await message.answer(
        "💰 Welcome to CashControl!\n\n"
        "Track income, expenses, balance, history, calculator, and exchange.\n\n"
        "Choose an action:",
        reply_markup=main_keyboard,
    )


@dp.message(lambda message: is_button(message, "Add Income"))
async def add_income(message: types.Message, state: FSMContext):
    await state.clear()
    await state.update_data(transaction_type="income")
    await state.set_state(TransactionState.currency)
    await message.answer("Choose income currency:", reply_markup=currency_keyboard)


@dp.message(lambda message: is_button(message, "Add Expense"))
async def add_expense(message: types.Message, state: FSMContext):
    await state.clear()
    await state.update_data(transaction_type="expense")
    await state.set_state(TransactionState.currency)
    await message.answer("Choose expense currency:", reply_markup=currency_keyboard)


@dp.message(TransactionState.currency)
async def transaction_currency(message: types.Message, state: FSMContext):
    if message.text == "Cancel":
        return await cancel_action(message, state)

    if message.text not in CURRENCIES:
        return await message.answer("Please choose a currency from the buttons.")

    await state.update_data(currency=message.text)
    await state.set_state(TransactionState.amount)
    await message.answer(f"Enter amount in {message.text}:")


@dp.message(TransactionState.amount)
async def transaction_amount(message: types.Message, state: FSMContext):
    if message.text == "Cancel":
        return await cancel_action(message, state)

    amount = parse_amount(message.text)
    if amount is None:
        return await message.answer("❌ Invalid amount. Example: 500")

    await state.update_data(amount=amount)
    data = await state.get_data()
    await state.set_state(TransactionState.source)

    if data["transaction_type"] == "income":
        await message.answer(
            "Please enter the source of income.\n\n"
            "Examples:\n"
            "- job\n"
            "- freelance\n"
            "- side work\n"
            "- company name\n"
            "- business income"
        )
    else:
        await message.answer(
            "Please enter the expense category.\n\n"
            "Examples:\n"
            "- food\n"
            "- credit payment\n"
            "- clothes and shoes\n"
            "- sport\n"
            "- software"
        )


@dp.message(TransactionState.source)
async def transaction_source(message: types.Message, state: FSMContext):
    if message.text == "Cancel":
        return await cancel_action(message, state)

    data = await state.get_data()

    transactions.append(
        {
            "user_id": message.from_user.id,
            "type": data["transaction_type"],
            "currency": data["currency"],
            "amount": data["amount"],
            "source": message.text.strip(),
            "created_at": datetime.now(),
        }
    )

    sign = "+" if data["transaction_type"] == "income" else "-"

    await state.clear()
    await message.answer(
        f"✅ Saved!\n\n"
        f"{data['transaction_type'].title()}: {sign}{data['amount']:.2f} {data['currency']}\n"
        f"Source: {message.text.strip()}",
        reply_markup=main_keyboard,
    )


@dp.message(lambda message: is_button(message, "Balance"))
async def balance(message: types.Message):
    balances = calculate_balance(message.from_user.id)

    if not balances:
        return await message.answer(
            "💼 Balance: 0.00\n\nNo transactions yet.",
            reply_markup=main_keyboard,
        )

    text = "💼 Your balance:\n\n"

    for currency in CURRENCIES:
        if currency in balances:
            text += f"{currency}: {balances[currency]:.2f}\n"

    await message.answer(text, reply_markup=main_keyboard)


@dp.message(lambda message: is_button(message, "History"))
async def history(message: types.Message):
    user_id = message.from_user.id
    user_transactions = [t for t in transactions if t["user_id"] == user_id]

    if not user_transactions:
        return await message.answer("📭 No transactions yet.", reply_markup=main_keyboard)

    text = "📜 History:\n\n"

    for transaction in user_transactions:
        date = transaction["created_at"].strftime("%Y-%m-%d %H:%M")

        if transaction["type"] == "income":
            line = f"Income: +{transaction['amount']:.2f} {transaction['currency']}"
        elif transaction["type"] == "expense":
            line = f"Expense: -{transaction['amount']:.2f} {transaction['currency']}"
        elif transaction["type"] == "exchange_out":
            line = f"Exchange out: -{transaction['amount']:.2f} {transaction['currency']}"
        elif transaction["type"] == "exchange_in":
            line = f"Exchange in: +{transaction['amount']:.2f} {transaction['currency']}"
        else:
            line = f"{transaction['type']}: {transaction['amount']:.2f} {transaction['currency']}"

        text += f"{date}\n{line}\nSource: {transaction['source']}\n\n"

    await message.answer(text, reply_markup=main_keyboard)


@dp.message(lambda message: is_button(message, "Calculator"))
async def calculator_start(message: types.Message, state: FSMContext):
    await state.clear()
    await state.set_state(CalculatorState.from_currency)
    await message.answer("Choose currency to calculate from:", reply_markup=currency_keyboard)


@dp.message(CalculatorState.from_currency)
async def calculator_from_currency(message: types.Message, state: FSMContext):
    if message.text == "Cancel":
        return await cancel_action(message, state)

    if message.text not in CURRENCIES:
        return await message.answer("Please choose a currency from the buttons.")

    await state.update_data(from_currency=message.text)
    await state.set_state(CalculatorState.amount)
    await message.answer(f"Enter amount in {message.text}:")


@dp.message(CalculatorState.amount)
async def calculator_amount(message: types.Message, state: FSMContext):
    if message.text == "Cancel":
        return await cancel_action(message, state)

    amount = parse_amount(message.text)
    if amount is None:
        return await message.answer("❌ Invalid amount. Example: 500")

    await state.update_data(amount=amount)
    await state.set_state(CalculatorState.to_currency)
    await message.answer("Choose target currency:", reply_markup=currency_keyboard)


@dp.message(CalculatorState.to_currency)
async def calculator_to_currency(message: types.Message, state: FSMContext):
    if message.text == "Cancel":
        return await cancel_action(message, state)

    if message.text not in CURRENCIES:
        return await message.answer("Please choose a currency from the buttons.")

    data = await state.get_data()
    from_currency = data["from_currency"]
    to_currency = message.text
    amount = data["amount"]

    if from_currency == to_currency:
        await state.clear()
        return await message.answer(
            f"🧮 Calculation result:\n\n"
            f"{amount:.2f} {from_currency} → {amount:.2f} {to_currency}",
            reply_markup=main_keyboard,
        )

    try:
        converted, market_rate, buy_rate = await convert_currency_buy_rate(
            amount, from_currency, to_currency
        )
    except Exception as error:
        await state.clear()
        return await message.answer(
            f"❌ Currency calculator error.\n\n"
            f"Reason: {error}",
            reply_markup=main_keyboard,
        )

    await state.clear()
    await message.answer(
        f"🧮 Calculation result:\n\n"
        f"{amount:.2f} {from_currency} → {converted:.2f} {to_currency}\n\n"
        f"Buy rate used: 1 {from_currency} = {buy_rate:.4f} {to_currency}\n"
        f"Market rate: {market_rate:.4f}\n\n"
        f"Balance was not changed.",
        reply_markup=main_keyboard,
    )


@dp.message(lambda message: is_button(message, "Exchange"))
async def exchange_start(message: types.Message, state: FSMContext):
    await state.clear()
    await state.set_state(ExchangeState.from_currency)
    await message.answer("Choose currency to exchange from:", reply_markup=currency_keyboard)


@dp.message(ExchangeState.from_currency)
async def exchange_from_currency(message: types.Message, state: FSMContext):
    if message.text == "Cancel":
        return await cancel_action(message, state)

    if message.text not in CURRENCIES:
        return await message.answer("Please choose a currency from the buttons.")

    balances = calculate_balance(message.from_user.id)
    available = balances.get(message.text, 0.0)

    if available <= 0:
        return await message.answer(
            f"❌ You do not have {message.text} balance.\n\n"
            f"Choose another currency or add income first."
        )

    await state.update_data(from_currency=message.text)
    await state.set_state(ExchangeState.amount)
    await message.answer(
        f"Available: {available:.2f} {message.text}\n\n"
        f"Enter amount in {message.text}:"
    )


@dp.message(ExchangeState.amount)
async def exchange_amount(message: types.Message, state: FSMContext):
    if message.text == "Cancel":
        return await cancel_action(message, state)

    amount = parse_amount(message.text)
    if amount is None:
        return await message.answer("❌ Invalid amount. Example: 500")

    data = await state.get_data()
    from_currency = data["from_currency"]

    balances = calculate_balance(message.from_user.id)
    available = balances.get(from_currency, 0.0)

    if amount > available:
        return await message.answer(
            f"❌ Not enough balance.\n\n"
            f"Available: {available:.2f} {from_currency}\n"
            f"Requested: {amount:.2f} {from_currency}\n\n"
            f"Enter another amount or press Cancel."
        )

    await state.update_data(amount=amount)
    await state.set_state(ExchangeState.to_currency)
    await message.answer("Choose target currency:", reply_markup=currency_keyboard)


@dp.message(ExchangeState.to_currency)
async def exchange_to_currency(message: types.Message, state: FSMContext):
    if message.text == "Cancel":
        return await cancel_action(message, state)

    if message.text not in CURRENCIES:
        return await message.answer("Please choose a currency from the buttons.")

    data = await state.get_data()
    from_currency = data["from_currency"]
    to_currency = message.text
    amount = data["amount"]

    if from_currency == to_currency:
        return await message.answer("❌ Source currency and target currency cannot be the same.")

    try:
        converted, market_rate, buy_rate = await convert_currency_buy_rate(
            amount, from_currency, to_currency
        )
    except Exception as error:
        await state.clear()
        return await message.answer(
            f"❌ Exchange error.\n\n"
            f"Reason: {error}",
            reply_markup=main_keyboard,
        )

    await state.update_data(
        to_currency=to_currency,
        converted=converted,
        buy_rate=buy_rate,
    )
    await state.set_state(ExchangeState.confirm)

    await message.answer(
        f"🔄 Exchange result:\n\n"
        f"{amount:.2f} {from_currency} → {converted:.2f} {to_currency}\n\n"
        f"Buy rate used: 1 {from_currency} = {buy_rate:.4f} {to_currency}\n\n"
        f"Save this exchange to your balance?",
        reply_markup=confirm_keyboard,
    )


@dp.message(ExchangeState.confirm)
async def exchange_confirm(message: types.Message, state: FSMContext):
    if message.text == "Cancel" or message.text == "❌ No":
        await state.clear()
        return await message.answer("Exchange was not saved.", reply_markup=main_keyboard)

    if message.text != "✅ Save":
        return await message.answer("Please choose ✅ Save or ❌ No.")

    data = await state.get_data()
    user_id = message.from_user.id
    now = datetime.now()

    from_currency = data["from_currency"]
    to_currency = data["to_currency"]
    amount = data["amount"]
    converted = data["converted"]

    balances = calculate_balance(user_id)
    available = balances.get(from_currency, 0.0)

    if amount > available:
        await state.clear()
        return await message.answer(
            f"❌ Exchange cannot be saved. Your balance changed.\n\n"
            f"Available: {available:.2f} {from_currency}",
            reply_markup=main_keyboard,
        )

    transactions.append(
        {
            "user_id": user_id,
            "type": "exchange_out",
            "currency": from_currency,
            "amount": amount,
            "source": f"Exchange to {to_currency}",
            "created_at": now,
        }
    )

    transactions.append(
        {
            "user_id": user_id,
            "type": "exchange_in",
            "currency": to_currency,
            "amount": converted,
            "source": f"Exchange from {from_currency}",
            "created_at": now,
        }
    )

    await state.clear()
    await message.answer(
        f"✅ Exchange saved!\n\n"
        f"-{amount:.2f} {from_currency}\n"
        f"+{converted:.2f} {to_currency}",
        reply_markup=main_keyboard,
    )


@dp.message()
async def unknown_message(message: types.Message):
    await message.answer("Please choose an action from the menu.", reply_markup=main_keyboard)


async def main():
    print("CashControl bot started")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
