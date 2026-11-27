import asyncio
import os
from aiohttp import web

# Создаем простой веб-сервер
async def handle(request):
    return web.Response(text="Bot is alive!")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', int(os.environ.get('PORT', 10000)))
    await site.start()
import logging
from datetime import datetime
import yfinance as yf
import pandas as pd
import ta
from sklearn.ensemble import RandomForestClassifier
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message

# --- НАСТРОЙКИ ---
# ВАЖНО: Вставьте сюда ваш НОВЫЙ токен (после перевыпуска)
BOT_TOKEN = "9072933341:AAFXHWH2QDifcUsFHZKSpXvY1J2bgbL8D3g"

# Настройки торговли
PAIR = "EURUSD=X" # Валютная пара для Yahoo Finance
TIMEFRAME = "5m"  # Таймфрейм (5 минут)
PERIOD = "5d"     # Загружаем историю за 5 дней

logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

def generate_signal():
    """Функция скачивания данных и генерации сигнала"""
    try:
        # 1. Скачиваем данные
        data = yf.download(tickers=PAIR, period=PERIOD, interval=TIMEFRAME, progress=False)
        if data.empty:
            return "Ошибка: Не удалось загрузить данные с рынка."

        # 2. Считаем индикаторы (как на вашем скрине)
        data['RSI'] = ta.momentum.rsi(data['Close'], window=14)
        data['SMA'] = ta.trend.sma_indicator(data['Close'], window=20)
        data['MACD'] = ta.trend.macd_diff(data['Close'])
        data['Body'] = abs(data['Close'] - data['Open'])
        
        # Создаем цель для обучения (1 - следующая свеча выше, 0 - ниже)
        data['Target'] = (data['Close'].shift(-1) > data['Close']).astype(int)
        data = data.dropna()

        # 3. Обучаем модель
        features = ['RSI', 'SMA', 'MACD', 'Body']
        train_data = data.iloc[:-1] # Все данные кроме последней свечи
        X = train_data[features]
        y = train_data['Target']

        model = RandomForestClassifier(n_estimators=100, max_depth=5, random_state=42)
        model.fit(X, y)

        # 4. Делаем прогноз на последнюю (текущую) свечу
        last_candle = data.iloc[[-1]]
        prediction = model.predict(last_candle[features])[0]
        probability = model.predict_proba(last_candle[features])[0]
        
        prob_up = probability[1] * 100
        current_price = last_candle['Close'].values[0]

        # 5. Формируем рекомендацию
        if prob_up > 60:
            signal_text = "🟢 <b>ВВЕРХ (CALL)</b>"
            confidence = prob_up
        elif prob_up < 40:
            signal_text = "🔴 <b>ВНИЗ (PUT)</b>"
            confidence = 100 - prob_up
        else:
            signal_text = "⚪️ <b>НЕТ СИГНАЛА (Флэт)</b>"
            confidence = max(prob_up, 100 - prob_up)

        # Формируем итоговое сообщение (рекомендую экспирацию 1-2 свечи)
        message = (
            f"📊 <b>Анализ {PAIR} ({TIMEFRAME})</b>\n\n"
            f"💰 Текущая цена: <code>{current_price:.5f}</code>\n"
            f"📈 Сигнал: {signal_text}\n"
            f"🎯 Уверенность ИИ: <code>{confidence:.1f}%</code>\n"
            f"⏱ Экспирация: <b>5 минут (1 свеча)</b>\n\n"
            f"<i>⚠️ Это не финансовый совет. Торгуйте на демо!</i>"
        )
        return message

    except Exception as e:
        return f"⚠️ Ошибка при анализе: {str(e)}"

@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer("🤖 Привет! Я твой ИИ-помощник.\nНажми /signal, чтобы я проанализировал график и выдал сигнал.")

@dp.message(Command("signal"))
async def cmd_signal(message: Message):
    await message.answer("🔄 Скачиваю данные и обучаю нейросеть, подожди ~10 секунд...")
    signal_result = generate_signal()
    await message.answer(signal_result, parse_mode="HTML")

async def main():
    logging.info("Бот запущен...")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
