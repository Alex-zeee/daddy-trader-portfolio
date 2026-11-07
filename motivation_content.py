"""Daddy Trader — rozana motivation posts ke jumle (60 din, phir dobara shuru; tasveer har dafa nayi banti hai).

Har post: andaaz (style), tasveer ki likhai, caption ki English line aur Roman Urdu line.
Naye jumle daalne hon to bas isi list mein aur jor dein.
"""

GOLD = [
    (["Focus", "Patience", "Discipline"], "Focus. Patience. Discipline.", "Market roz khulti hai, sabr bhi roz chahiye."),
    (["Plan", "Wait", "Execute"], "Plan the trade. Wait for it. Execute it.", "Pehle plan, phir intezar, phir entry."),
    (["Protect", "Your", "Capital"], "Protect your capital first.", "Paisa bachega to agla mauqa bhi milega."),
    (["Trust", "The", "Process"], "Trust the process.", "Ek din ka nateeja nahi, saal ka hisaab dekho."),
    (["Calm", "Mind", "Sharp Eye"], "A calm mind sees the chart clearly.", "Ghusse aur jaldi mein chart nazar nahi aata."),
    (["Small", "Losses", "Big Wins"], "Keep losses small. Let winners grow.", "Chhota loss qubool karo, bara profit chalne do."),
    (["Learn", "Adapt", "Grow"], "Learn. Adapt. Grow.", "Har trade kuch sikhati hai."),
    (["No Plan", "No", "Trade"], "No plan, no trade.", "Plan ke baghair entry jua hai, trading nahi."),
    (["Wait", "For The", "Setup"], "Wait for your setup.", "Har candle par trade lena zaroori nahi."),
    (["Gold", "Rewards", "Patience"], "Gold rewards patience.", "Gold mein sabr karne wala hi kamata hai."),
    (["Consistency", "Beats", "Luck"], "Consistency beats luck.", "Qismat ek din, mehnat har din."),
    (["One", "Trade", "At A Time"], "One trade at a time.", "Pichli trade bhool jao, agli par dhyan do."),
]

TARGET = [
    ("Control", "your", "risk", "Control your risk, and the profits will follow.", "Risk control mein hai to account mehfooz hai."),
    ("Focus", "on the", "process", "Focus on the process, not the outcome.", "Rules follow karo, nateeja khud aayega."),
    ("Hold", "your", "plan", "Hold your plan, not your emotions.", "Jazbaat nahi, plan ke mutabiq chalo."),
    ("Stop", "chasing", "price", "Stop chasing price. Let it come to you.", "Bhaagti market ke peeche mat bhaago."),
    ("One", "good", "trade", "One good trade is better than ten random ones.", "Das ghalat trades se ek sahi trade behtar."),
    ("Protect", "your", "capital", "Protect your capital at all costs.", "Account bacha rahe, yehi pehla usool hai."),
    ("Slow", "is", "smooth", "Slow is smooth. Smooth is profitable.", "Aahista aur sahi, tez aur ghalat se behtar."),
    ("Fomo", "kills", "accounts", "FOMO kills accounts.", "Trade chhoot jaye to koi baat nahi, account na chhoote."),
    ("Profit", "follows", "discipline", "Profit follows discipline.", "Discipline pehle, profit baad mein."),
    ("Zone", "wait for", "your level", "Wait for price to reach your zone.", "Apne level ka intezar karo, beech mein mat koodo."),
    ("Boss", "of your", "emotions", "Be the boss of your emotions.", "Dar aur laalach dono ko qaabu mein rakho."),
    ("Logic", "over", "emotion", "Logic over emotion. Every single trade.", "Har trade dimagh se, dil se nahi."),
]

NEON = [
    ("GOLD", [("G", "Growth"), ("O", "Order"), ("L", "Logic"), ("D", "Discipline")], ["PLAN.", "WAIT.", "STRIKE.", "GROW."],
     "G-O-L-D: Growth, Order, Logic, Discipline.", "Gold trade karna hai to pehle ye chaar cheezein seekho."),
    ("FOCUS", [("F", "Filter noise"), ("O", "Observe"), ("C", "Commit"), ("U", "Understand"), ("S", "Stay calm")],
     ["SEE.", "WAIT.", "ACT.", "REVIEW."], "Focus is a skill. Train it daily.", "Shor se door raho, chart par nazar rakho."),
    ("TRADE", [("T", "Timing"), ("R", "Rules"), ("A", "Accept loss"), ("D", "Data"), ("E", "Edge")],
     ["THINK.", "TEST.", "TRADE.", "TRACK."], "Timing, rules, data and edge make a trade.", "Andaze se nahi, data se trade karo."),
    ("EDGE", [("E", "Entry rules"), ("D", "Discipline"), ("G", "Grit"), ("E", "Execution")],
     ["TEST.", "PROVE.", "REPEAT.", "SCALE."], "Find your edge. Then repeat it.", "Apna tareeqa dhoondo aur usi par qaim raho."),
    ("WIN", [("W", "Wait"), ("I", "Identify"), ("N", "Nail entry")], ["PATIENT.", "PRECISE.", "PROFITABLE.", ""],
     "Wait. Identify. Nail the entry.", "Sahi waqt ka intezar hi asal jeet hai."),
    ("RISK", [("R", "Respect it"), ("I", "Inspect it"), ("S", "Size it"), ("K", "Keep small")],
     ["1%", "RULE.", "ALWAYS.", ""], "Respect risk before you chase reward.", "Pehle socho kitna kho sakte ho, phir socho kitna kamao ge."),
    ("CALM", [("C", "Clear mind"), ("A", "Accept loss"), ("L", "Limit risk"), ("M", "Move on")],
     ["BREATHE.", "THINK.", "ACT.", ""], "Stay calm. The market rewards a clear mind.", "Loss ke baad revenge trade mat lo."),
    ("PLAN", [("P", "Prepare"), ("L", "Levels"), ("A", "Action"), ("N", "Notes")],
     ["BEFORE", "THE", "OPEN.", ""], "Plan your levels before the market opens.", "Market khulne se pehle levels tayyar rakho."),
    ("HABIT", [("H", "Hold rules"), ("A", "Accept loss"), ("B", "Be patient"), ("I", "Improve"), ("T", "Track trades")],
     ["DAILY.", "WEEKLY.", "ALWAYS.", ""], "Great traders are built by daily habits.", "Achi aadatein hi acha trader banati hain."),
    ("GROW", [("G", "Goals"), ("R", "Routine"), ("O", "Observe"), ("W", "Win small")],
     ["STEP.", "BY.", "STEP.", ""], "Grow slowly. Grow surely.", "Chhoti jeet roz, bari jeet khud ban jaati hai."),
    ("SABR", [("S", "Stay calm"), ("A", "Accept"), ("B", "Believe"), ("R", "Repeat")],
     ["PATIENCE", "IS", "POWER.", ""], "Sabr: the most underrated trading skill.", "Sabr karne wala trader hi aakhir mein jeet'ta hai."),
    ("PROFIT", [("P", "Patience"), ("R", "Rules"), ("O", "Order"), ("F", "Focus"), ("I", "Intent"), ("T", "Time")],
     ["EARN", "IT.", "DAILY.", ""], "Profit is the result of patience, rules and time.", "Profit jaldi ka nahi, sabr ka phal hai."),
]

MONO = [
    (["The market pays", "the patient,", "not the loud."], "The market pays the patient, not the loud.", "Shor machane wale nahi, sabr wale kamate hain."),
    (["No trade", "is also", "a position."], "No trade is also a position.", "Kabhi kabhi trade na lena hi sab se acha faisla hai."),
    (["Protect the downside.", "The upside", "takes care of itself."], "Protect the downside. The upside takes care of itself.", "Nuqsan control karo, faida khud aayega."),
    (["Losses are tuition.", "Pay them small."], "Losses are tuition. Pay them small.", "Loss fees hai, bas chhoti rakho."),
    (["Fear your emotions,", "not the chart."], "Fear your emotions, not the chart.", "Chart dushman nahi, jazbaat hain."),
    (["A good trader", "waits more", "than he trades."], "A good trader waits more than he trades.", "Acha trader zyada intezar karta hai, kam trade."),
    (["Your stop loss", "is your", "seatbelt."], "Your stop loss is your seatbelt.", "Stop loss ke baghair gaari mat chalao."),
    (["Don't predict.", "Prepare", "and react."], "Don't predict. Prepare and react.", "Andaza nahi, tayyari karo."),
    (["Gold moves fast.", "Your mind", "must stay slow."], "Gold moves fast. Your mind must stay slow.", "Market tez ho to dimagh thanda rakho."),
    (["Every chart", "tells a story.", "Read it fully."], "Every chart tells a story. Read it fully.", "Poora chart parho, sirf aakhri candle nahi."),
    (["Discipline is", "doing it right,", "even unseen."], "Discipline is doing it right, even when no one is watching.", "Koi dekhe ya na dekhe, rules wahi rehte hain."),
    (["Consistency", "turns small wins", "into big results."], "Consistency turns small wins into big results.", "Roz ki chhoti jeet mil kar bari ban jaati hai."),
]

SUMMIT = [
    (["Plan.", "Wait.", "Execute.", "Repeat."], ["Protect capital first.", "Profit follows."], "Plan. Wait. Execute. Repeat.", "Yehi chaar qadam roz dohrao."),
    (["Learn.", "Test.", "Trust.", "Grow."], ["Backtest before you bet.", "Data beats doubt."], "Backtest before you risk real money.", "Pehle backtest, phir asli paisa."),
    (["Small risk.", "Big vision."], ["Think in years,", "not in trades."], "Small risk. Big vision.", "Aaj ka risk chhota, kal ka khwab bara."),
    (["Fall.", "Learn.", "Rise.", "Repeat."], ["Every loss is a lesson.", "Keep climbing."], "Fall. Learn. Rise. Repeat.", "Girna bura nahi, uth kar seekhna zaroori hai."),
    (["Dream.", "Plan.", "Trade.", "Review."], ["Journal every trade.", "Grow every week."], "Journal every trade. Review every week.", "Har trade likho, har hafte dekho."),
    (["One step", "at a time."], ["The summit is built", "trade by trade."], "One step at a time.", "Choti tak ek ek qadam se pohanchte hain."),
    (["Focus.", "Enter.", "Manage.", "Exit."], ["Know your exit", "before you enter."], "Know your exit before you enter.", "Entry se pehle exit ka pata hona chahiye."),
    (["Stay", "the", "course."], ["Drawdowns end.", "Discipline stays."], "Stay the course.", "Bura waqt guzar jaata hai, discipline rehna chahiye."),
    (["Patience", "is a", "position."], ["Waiting is part", "of the strategy."], "Patience is a position.", "Intezar bhi strategy ka hissa hai."),
    (["Slow.", "Steady.", "Sure."], ["Compounding rewards", "the consistent."], "Slow. Steady. Sure.", "Aahista aahista, magar pakka."),
    (["No", "shortcuts", "to the", "summit."], ["Skill compounds", "like capital."], "There are no shortcuts to the summit.", "Kamyabi ka koi shortcut nahi."),
    (["Today.", "Better.", "Than.", "Yesterday."], ["1% better", "every session."], "Be 1% better than yesterday.", "Kal se thora behtar, bas itna kaafi hai."),
]


def _posts():
    out = []
    for i in range(12):
        l, en, ur = GOLD[i]
        out.append({"style": "gold", "lines": l, "en": en, "ur": ur})
        w, mid, end, en, ur = TARGET[i]
        out.append({"style": "target", "word": w, "mid": mid, "end": end, "en": en, "ur": ur})
        w, rows, tag, en, ur = NEON[i]
        out.append({"style": "neon", "word": w, "rows": rows, "tag": [t for t in tag if t], "en": en, "ur": ur})
        l, en, ur = MONO[i]
        out.append({"style": "mono", "lines": l, "en": en, "ur": ur})
        l, sub, en, ur = SUMMIT[i]
        out.append({"style": "summit", "lines": l, "sub": sub, "en": en, "ur": ur})
    return out


POSTS = _posts()

CHANNEL = "https://whatsapp.com/channel/0029Vb8tas7BFLga0KUzOI0A"
TAGS = "#DaddyTrader #XAUUSD #GoldTrading #TradingMindset #ForexPakistan #TradingDiscipline"


def caption(p):
    return "\n".join([
        p["en"],
        p["ur"],
        "",
        "📲 Free XAUUSD signals — WhatsApp channel join karein: " + CHANNEL,
        "🌐 daddytrader.live",
        "",
        TAGS,
    ])
