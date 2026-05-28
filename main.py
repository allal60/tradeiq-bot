import logging
import json
import re
import os
import anthropic
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters, ConversationHandler

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")

CAPITAL, MARKET, PAIR, TIMEFRAME, RISK = range(5)
logging.basicConfig(level=logging.INFO)

PAIRS = {
    "forex": ["EUR/USD","GBP/USD","USD/JPY","XAU/USD","AUD/USD"],
    "crypto": ["BTC/USDT","ETH/USDT","BNB/USDT","SOL/USDT","XRP/USDT"],
    "stocks": ["AAPL","TSLA","MSFT","NVDA","AMZN"]
}

def get_analysis(capital, market, pair, timeframe, risk):
    risk_map = {"low":"منخفض 1-2%","medium":"متوسط 2-4%","high":"عالي 4-6%"}
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    prompt = f"""أنت محلل تداول. حلل هذا الزوج وأجب بـ JSON فقط بدون أي نص إضافي:
الزوج: {pair} | السوق: {market} | الإطار: {timeframe} | رأس المال: ${capital} | المخاطرة: {risk_map[risk]}
{{
  "signal": "BUY أو SELL أو WAIT",
  "confidence": 70,
  "entry": "سعر الدخول",
  "tp": "Take Profit",
  "sl": "Stop Loss",
  "lot_size": "حجم اللوت",
  "rr_ratio": "نسبة R:R",
  "max_loss_usd": "أقصى خسارة",
  "potential_profit_usd": "الربح المتوقع",
  "analysis": "تحليل باللغة العربية"
}}"""
    msg = client.messages.create(model="claude-sonnet-4-20250514", max_tokens=1000, messages=[{"role":"user","content":prompt}])
    text = msg.content[0].text
    return json.loads(re.sub(r'```json|```','',text).strip())

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🤖 *أهلاً! أنا TradeIQ Bot*\n\nاضغط /analyze لتبدأ التحليل 📊", parse_mode='Markdown')

async def analyze_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("💰 *كم رأس مالك بالدولار؟*\n\nمثال: `500`", parse_mode='Markdown')
    return CAPITAL

async def get_capital(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        capital = float(update.message.text.strip())
        if capital < 10:
            await update.message.reply_text("⚠️ 10$ على الأقل، حاول مرة أخرى:")
            return CAPITAL
        context.user_data['capital'] = capital
    except:
        await update.message.reply_text("⚠️ أرسل رقماً مثل: `500`", parse_mode='Markdown')
        return CAPITAL
    keyboard = [[InlineKeyboardButton("🌍 Forex",callback_data="market_forex"),InlineKeyboardButton("₿ Crypto",callback_data="market_crypto"),InlineKeyboardButton("📈 Stocks",callback_data="market_stocks")]]
    await update.message.reply_text("🌍 *اختار نوع السوق:*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    return MARKET

async def get_market(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    market = query.data.replace("market_","")
    context.user_data['market'] = market
    pairs = PAIRS[market]
    keyboard = [[InlineKeyboardButton(p, callback_data=f"pair_{p}") for p in pairs[i:i+2]] for i in range(0,len(pairs),2)]
    await query.edit_message_text("📌 *اختار الزوج:*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    return PAIR

async def get_pair(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['pair'] = query.data.replace("pair_","")
    keyboard = [[InlineKeyboardButton("M5",callback_data="tf_M5"),InlineKeyboardButton("M15",callback_data="tf_M15"),InlineKeyboardButton("H1",callback_data="tf_H1")],[InlineKeyboardButton("H4",callback_data="tf_H4"),InlineKeyboardButton("D1",callback_data="tf_D1")]]
    await query.edit_message_text("⏱ *اختار الإطار الزمني:*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    return TIMEFRAME

async def get_timeframe(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data['timeframe'] = query.data.replace("tf_","")
    keyboard = [[InlineKeyboardButton("🟢 منخفض",callback_data="risk_low"),InlineKeyboardButton("🟡 متوسط",callback_data="risk_medium"),InlineKeyboardButton("🔴 عالي",callback_data="risk_high")]]
    await query.edit_message_text("⚖️ *اختار مستوى المخاطرة:*", reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    return RISK

async def get_risk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    risk = query.data.replace("risk_","")
    capital = context.user_data['capital']
    market = context.user_data['market']
    pair = context.user_data['pair']
    timeframe = context.user_data['timeframe']
    await query.edit_message_text(f"⚡ *جاري تحليل {pair}...*", parse_mode='Markdown')
    try:
        d = get_analysis(capital, market, pair, timeframe, risk)
        sig = {"BUY":"🟢 شراء ↑","SELL":"🔴 بيع ↓","WAIT":"🟡 انتظر ⏳"}.get(d['signal'],"🟡 انتظر")
        msg = f"""╔══════════════════╗
   📊 *{pair}*
╚══════════════════╝

{sig} | ثقة: {d['confidence']}%

━━━━━━━━━━━━━━━━━━
🔵 الدخول: `{d['entry']}`
🟢 Take Profit: `{d['tp']}`
🔴 Stop Loss: `{d['sl']}`

━━━━━━━━━━━━━━━━━━
📦 اللوت: *{d['lot_size']}*
⚖️ R:R: *{d['rr_ratio']}*
❌ خسارة: *${d['max_loss_usd']}*
✅ ربح: *${d['potential_profit_usd']}*

━━━━━━━━━━━━━━━━━━
🧠 _{d['analysis']}_

⚠️ _للأغراض التعليمية فقط_"""
        keyboard = [[InlineKeyboardButton("🔄 تحليل جديد",callback_data="new"),InlineKeyboardButton("📊 نفس الزوج",callback_data="same")]]
        await query.message.reply_text(msg, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as e:
        await query.message.reply_text("❌ خطأ في التحليل، حاول مرة أخرى بـ /analyze")
    return ConversationHandler.END

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "new":
        await query.message.reply_text("💰 *كم رأس مالك؟*", parse_mode='Markdown')
        return CAPITAL
    elif query.data == "same":
        await query.message.reply_text(f"⚡ *جاري إعادة تحليل {context.user_data.get('pair','—')}...*", parse_mode='Markdown')
        try:
            d = get_analysis(context.user_data['capital'], context.user_data['market'], context.user_data['pair'], context.user_data['timeframe'], 'low')
            sig = {"BUY":"🟢 شراء ↑","SELL":"🔴 بيع ↓","WAIT":"🟡 انتظر ⏳"}.get(d['signal'],"🟡")
            msg = f"*{context.user_data['pair']}* | {sig}\n\n🔵 `{d['entry']}` 🟢 `{d['tp']}` 🔴 `{d['sl']}`\n\n_{d['analysis']}_"
            keyboard = [[InlineKeyboardButton("🔄 تحليل جديد",callback_data="new"),InlineKeyboardButton("📊 نفس الزوج",callback_data="same")]]
            await query.message.reply_text(msg, parse_mode='Markdown', reply_markup=InlineKeyboardMarkup(keyboard))
        except:
            await query.message.reply_text("❌ خطأ، حاول /analyze")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ تم الإلغاء. اكتب /analyze للبدء.")
    return ConversationHandler.END

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    conv = ConversationHandler(
        entry_points=[CommandHandler('analyze', analyze_start), CallbackQueryHandler(button_handler, pattern='^(new|same)$')],
        states={CAPITAL:[MessageHandler(filters.TEXT & ~filters.COMMAND, get_capital)], MARKET:[CallbackQueryHandler(get_market, pattern='^market_')], PAIR:[CallbackQueryHandler(get_pair, pattern='^pair_')], TIMEFRAME:[CallbackQueryHandler(get_timeframe, pattern='^tf_')], RISK:[CallbackQueryHandler(get_risk, pattern='^risk_')]},
        fallbacks=[CommandHandler('cancel', cancel)]
    )
    app.add_handler(CommandHandler('start', start))
    app.add_handler(conv)
    print("🚀 Bot running...")
    app.run_polling()

if __name__ == '__main__':
    main()
