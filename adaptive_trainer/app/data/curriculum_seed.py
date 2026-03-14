"""Seed vocabulary data for Ring 0 and Ring 1 curriculum units.

Each unit contains ~10-12 words in colloquial Bengaluru Kannada (Roman
transliteration).  Call ``seed_vocabulary()`` at startup or from a
management command to populate the curriculum_units and unit_vocabulary tables.
"""

from __future__ import annotations

import logging
from typing import TypedDict

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.curriculum import CurriculumUnit, UnitVocabulary

logger = logging.getLogger(__name__)


class SeedEntry(TypedDict, total=False):
    word: str  # Kannada Roman transliteration
    english: str
    usage_example: str
    tags: list[str]
    usage_context: str
    grammar_note: str


# ---------------------------------------------------------------------------
# Ring 0 — Survival Reflexes (4 units, ~10 atoms each)
# ---------------------------------------------------------------------------

GREETINGS: list[SeedEntry] = [
    {"word": "Namaskara", "english": "Hello / Greetings", "usage_example": "Namaskara, hegiddira?",
     "tags": ["greeting", "polite", "formal"], "usage_context": "Universal greeting, any time of day",
     "grammar_note": "From Sanskrit namaskaara; safe in all registers"},
    {"word": "Hegiddira?", "english": "How are you?", "usage_example": "Hegiddira? Chennagiddira?",
     "tags": ["greeting", "question"], "usage_context": "Follow-up after namaskara",
     "grammar_note": "hegiddira = how are you (respectful -ira suffix)"},
    {"word": "Nanna hesaru", "english": "My name is", "usage_example": "Nanna hesaru Anil.",
     "tags": ["introduction", "self"], "usage_context": "Introducing yourself to anyone",
     "grammar_note": "nanna = my, hesaru = name"},
    {"word": "Dhanyavada", "english": "Thank you", "usage_example": "Thumba dhanyavada, sir.",
     "tags": ["polite", "gratitude"], "usage_context": "After receiving help, service, or a favour",
     "grammar_note": "Formal; casual = 'thanks' or 'thumba thanks'"},
    {"word": "Hogi banni", "english": "Goodbye (go and come)", "usage_example": "Sari, hogi banni!",
     "tags": ["farewell", "polite"], "usage_context": "Saying goodbye, implies you'll meet again",
     "grammar_note": "hogi = go, banni = come; lit. 'go and come back'"},
    {"word": "Shubha dinadalli", "english": "Good day / Good wishes", "usage_example": "Nimge shubha dinadalli.",
     "tags": ["greeting", "formal", "wishes"], "usage_context": "Formal well-wishing, written or spoken"},
    {"word": "Shubha raatri", "english": "Good night", "usage_example": "Shubha raatri, naalae sigona.",
     "tags": ["farewell", "evening"], "usage_context": "Parting at night"},
    {"word": "Houdhu", "english": "Yes", "usage_example": "Houdhu, naanu ready.",
     "tags": ["basic", "response"], "usage_context": "Affirming anything",
     "grammar_note": "Casual yes; more formal = 'haudu'"},
    {"word": "Illa", "english": "No", "usage_example": "Illa, naanu baralla.",
     "tags": ["basic", "response"], "usage_context": "Declining or negating",
     "grammar_note": "baralla = won't come (bar- + alla negation)"},
    {"word": "Dayavittu", "english": "Please", "usage_example": "Dayavittu illi kootko.",
     "tags": ["polite", "request"], "usage_context": "Making any polite request",
     "grammar_note": "From daya (mercy) + vittu; kootko = sit (informal)"},
]

EMERGENCY_TOOLKIT: list[SeedEntry] = [
    {"word": "Help maadi", "english": "Help me", "usage_example": "Dayavittu help maadi!",
     "tags": ["emergency", "request"], "usage_context": "Asking for help in urgent situations",
     "grammar_note": "maadi = do/make (imperative polite)"},
    {"word": "Naanige gothilla", "english": "I don't know / understand", "usage_example": "Sorry, naanige gothilla.",
     "tags": ["emergency", "comprehension"], "usage_context": "When you don't understand something",
     "grammar_note": "naanige = to me, gothilla = not known"},
    {"word": "Nidhaanavaagi maathaadi", "english": "Please speak slowly", "usage_example": "Dayavittu nidhaanavaagi maathaadi.",
     "tags": ["emergency", "comprehension", "request"], "usage_context": "When someone speaks too fast",
     "grammar_note": "nidhaanavaagi = slowly, maathaadi = speak (polite)"},
    {"word": "Doctor beku", "english": "Need a doctor", "usage_example": "Doctor beku, hushaarilla.",
     "tags": ["emergency", "medical"], "usage_context": "Medical emergency",
     "grammar_note": "beku = need/want"},
    {"word": "Aaspatre yelli?", "english": "Where is the hospital?", "usage_example": "Hattira aaspatre yelli ide?",
     "tags": ["emergency", "medical", "question"], "usage_context": "Finding medical help",
     "grammar_note": "yelli = where, ide = is"},
    {"word": "Police", "english": "Police", "usage_example": "Police ge call maadi.",
     "tags": ["emergency", "safety"], "usage_context": "Reporting crime or emergency",
     "grammar_note": "ge = to (dative); English loanword"},
    {"word": "Hushaarilla", "english": "Not feeling well", "usage_example": "Naanige hushaarilla.",
     "tags": ["emergency", "medical", "self"], "usage_context": "Telling someone you're unwell",
     "grammar_note": "hushaar = alert/well, -illa = negation"},
    {"word": "Kannada barthilla", "english": "I don't speak Kannada", "usage_example": "Naanige Kannada barthilla.",
     "tags": ["emergency", "language"], "usage_context": "When you can't follow a conversation",
     "grammar_note": "barthilla = doesn't come (i.e. I don't know it)"},
    {"word": "English barthaa?", "english": "Do you speak English?", "usage_example": "Nimge English barthaa?",
     "tags": ["emergency", "language", "question"], "usage_context": "Checking if someone speaks English",
     "grammar_note": "barthaa = does it come? (question form)"},
    {"word": "Swalpa Kannada baratte", "english": "I know a little Kannada", "usage_example": "Naanige swalpa Kannada baratte.",
     "tags": ["language", "self"], "usage_context": "Setting expectations about your Kannada level",
     "grammar_note": "swalpa = a little, baratte = it comes (to me)"},
]

NUMBERS_MONEY: list[SeedEntry] = [
    {"word": "Ondu", "english": "One", "usage_example": "Ondu kaafi kodi.",
     "tags": ["number", "basic"], "usage_context": "Counting, ordering single items"},
    {"word": "Eradu", "english": "Two", "usage_example": "Eradu dosa beku.",
     "tags": ["number", "basic"], "usage_context": "Counting, ordering two items"},
    {"word": "Mooru", "english": "Three", "usage_example": "Mooru jana idivi.",
     "tags": ["number", "basic"], "usage_context": "Counting people or items",
     "grammar_note": "jana = people, idivi = we are"},
    {"word": "Nalku", "english": "Four", "usage_example": "Nalku gante aaytu.",
     "tags": ["number", "basic"], "usage_context": "Telling time or counting"},
    {"word": "Aidu", "english": "Five", "usage_example": "Aidu nimisha thaali.",
     "tags": ["number", "basic"], "usage_context": "Common in time expressions",
     "grammar_note": "nimisha = minute, thaali = wait"},
    {"word": "Aaru", "english": "Six", "usage_example": "Aaru gantege barthini.",
     "tags": ["number"], "usage_context": "Time, quantities"},
    {"word": "Yelu", "english": "Seven", "usage_example": "Yelu dina beku.",
     "tags": ["number"], "usage_context": "Days of the week references"},
    {"word": "Entu", "english": "Eight", "usage_example": "Entu rupayi aaytu.",
     "tags": ["number"], "usage_context": "Counting, prices"},
    {"word": "Ombattu", "english": "Nine", "usage_example": "Ombattu gantege meeting ide.",
     "tags": ["number"], "usage_context": "Time references"},
    {"word": "Hattu", "english": "Ten", "usage_example": "Hattu rupayi kodi.",
     "tags": ["number", "basic"], "usage_context": "Prices, counting",
     "grammar_note": "Base for teens: hattondu (11), hanneradu (12)"},
    {"word": "Ippattu", "english": "Twenty", "usage_example": "Ippattu rupayi aagatte.",
     "tags": ["number", "money"], "usage_context": "Prices, auto fares"},
    {"word": "Nooru", "english": "Hundred", "usage_example": "Nooru rupayi aagatte.",
     "tags": ["number", "money"], "usage_context": "Prices above 100"},
    {"word": "Saavira", "english": "Thousand", "usage_example": "Ondu saavira rupayi beku.",
     "tags": ["number", "money"], "usage_context": "Larger amounts, rent, shopping"},
    {"word": "Rupayi", "english": "Rupees", "usage_example": "Yeshtu rupayi aagatte?",
     "tags": ["money", "basic"], "usage_context": "Any price discussion"},
    {"word": "Yeshtu aagatte?", "english": "How much will it cost?", "usage_example": "Idhu yeshtu aagatte?",
     "tags": ["money", "question", "transaction"], "usage_context": "Asking price at shops, autos, restaurants",
     "grammar_note": "yeshtu = how much, aagatte = will it be"},
]

FIRST_TRANSACTIONS: list[SeedEntry] = [
    {"word": "Ondu kaafi kodi", "english": "Give me one coffee", "usage_example": "Ondu kaafi kodi, please.",
     "tags": ["food", "request", "transaction"], "usage_context": "Ordering at any coffee shop or restaurant",
     "grammar_note": "kodi = please give (imperative polite)"},
    {"word": "Eradu dosa kodi", "english": "Give me two dosas", "usage_example": "Eradu masala dosa kodi.",
     "tags": ["food", "request", "transaction"], "usage_context": "Ordering food at a restaurant"},
    {"word": "Bill kodi", "english": "Give the bill", "usage_example": "Bill kodi, hogbekku.",
     "tags": ["transaction", "request"], "usage_context": "Asking for the check at a restaurant",
     "grammar_note": "hogbekku = I need to go"},
    {"word": "Parcel maadi", "english": "Pack it / Takeaway", "usage_example": "Eradu idli parcel maadi.",
     "tags": ["food", "request", "transaction"], "usage_context": "Ordering takeaway food",
     "grammar_note": "parcel = takeaway (common Indianism)"},
    {"word": "Neeru kodi", "english": "Give water", "usage_example": "Swalpa neeru kodi.",
     "tags": ["food", "request", "basic"], "usage_context": "Asking for water anywhere",
     "grammar_note": "neeru = water"},
    {"word": "Beku", "english": "Want / Need", "usage_example": "Ondu chaaha beku.",
     "tags": ["basic", "request"], "usage_context": "Expressing a want or need for anything",
     "grammar_note": "Versatile; placed after the thing you want"},
    {"word": "Beda", "english": "Don't want", "usage_example": "Illa beda, saaku.",
     "tags": ["basic", "response"], "usage_context": "Declining an offer or refusing something",
     "grammar_note": "saaku = enough; beda is the opposite of beku"},
    {"word": "Yeshtu?", "english": "How much?", "usage_example": "Idhu yeshtu?",
     "tags": ["question", "transaction", "basic"], "usage_context": "Quick price inquiry at any shop",
     "grammar_note": "Short form; idhu = this"},
    {"word": "UPI maadthini", "english": "I'll pay by UPI", "usage_example": "UPI maadthini, okay aa?",
     "tags": ["transaction", "payment"], "usage_context": "Paying digitally at shops, autos, restaurants",
     "grammar_note": "maadthini = I will do"},
    {"word": "Cash", "english": "Cash payment", "usage_example": "Cash kodi, change ide aa?",
     "tags": ["transaction", "payment"], "usage_context": "Paying with cash",
     "grammar_note": "ide aa? = is there? (question)"},
]

# ---------------------------------------------------------------------------
# Ring 1 — Transactional Independence (6 units, ~12 atoms each)
# ---------------------------------------------------------------------------

TRANSPORT: list[SeedEntry] = [
    {"word": "Bus", "english": "Bus", "usage_example": "Majestic ge bus yavdu?",
     "tags": ["transport", "vehicle"], "usage_context": "Public bus travel in Bengaluru",
     "grammar_note": "ge = to (destination marker)"},
    {"word": "Auto", "english": "Auto rickshaw", "usage_example": "Auto maadbeku, Koramangala ge.",
     "tags": ["transport", "vehicle"], "usage_context": "Hiring an auto for short trips",
     "grammar_note": "maadbeku = need to do/arrange"},
    {"word": "Metro", "english": "Metro train", "usage_example": "Metro station yelli ide?",
     "tags": ["transport", "vehicle"], "usage_context": "Using Namma Metro in Bengaluru"},
    {"word": "Nildana", "english": "Bus stop / Stand", "usage_example": "Mundina nildana yavdu?",
     "tags": ["transport", "place"], "usage_context": "Finding bus stops",
     "grammar_note": "mundina = next, yavdu = which"},
    {"word": "Illi nilsi", "english": "Stop here", "usage_example": "Driver, illi nilsi.",
     "tags": ["transport", "command"], "usage_context": "Telling auto/taxi driver to stop",
     "grammar_note": "nilsi = stop (imperative)"},
    {"word": "Hogbekku", "english": "I need to go", "usage_example": "Naanu MG Road ge hogbekku.",
     "tags": ["transport", "basic"], "usage_context": "Telling driver your destination",
     "grammar_note": "hog- = go, -bekku = need to"},
    {"word": "Station yelli?", "english": "Where is the station?", "usage_example": "Metro station yelli ide?",
     "tags": ["transport", "question"], "usage_context": "Finding stations or stops"},
    {"word": "Ticket", "english": "Ticket", "usage_example": "Eradu ticket kodi.",
     "tags": ["transport", "transaction"], "usage_context": "Buying bus or metro tickets"},
    {"word": "Yeshtu aagatte?", "english": "How much will it cost?", "usage_example": "Indiranagar ge yeshtu aagatte?",
     "tags": ["transport", "question", "money"], "usage_context": "Negotiating auto fare"},
    {"word": "Bega", "english": "Quickly / Fast", "usage_example": "Bega hogi, late aagthide.",
     "tags": ["transport", "urgency"], "usage_context": "Asking driver to hurry",
     "grammar_note": "aagthide = it's becoming (late)"},
    {"word": "Taxi", "english": "Taxi / Cab", "usage_example": "Taxi book maadidini.",
     "tags": ["transport", "vehicle"], "usage_context": "Booking Ola/Uber or street taxi",
     "grammar_note": "maadidini = I did/have done"},
    {"word": "Irangthini", "english": "I'll get off", "usage_example": "Mundina stop nalli irangthini.",
     "tags": ["transport", "action"], "usage_context": "Telling bus conductor you want to get off",
     "grammar_note": "irang- = descend, -thini = I will"},
]

FOOD_ORDERING: list[SeedEntry] = [
    {"word": "Menu kodi", "english": "Give the menu", "usage_example": "Menu kodi, please.",
     "tags": ["food", "request"], "usage_context": "At any sit-down restaurant"},
    {"word": "Oota", "english": "Meal / Food", "usage_example": "Oota aaytha?",
     "tags": ["food", "basic"], "usage_context": "Asking if someone has eaten",
     "grammar_note": "aaytha? = is it done? (very common greeting)"},
    {"word": "Dosa", "english": "Dosa (crepe)", "usage_example": "Masala dosa kodi.",
     "tags": ["food", "item"], "usage_context": "Ordering the iconic South Indian dish"},
    {"word": "Idli", "english": "Idli (steamed cake)", "usage_example": "Eradu idli chutney jote kodi.",
     "tags": ["food", "item"], "usage_context": "Breakfast staple, available everywhere",
     "grammar_note": "jote = with/along with"},
    {"word": "Roti", "english": "Flatbread", "usage_example": "Mooru roti palya jote kodi.",
     "tags": ["food", "item"], "usage_context": "North Indian restaurants, lunch",
     "grammar_note": "palya = vegetable side dish"},
    {"word": "Anna", "english": "Rice", "usage_example": "Anna saaru haakolli.",
     "tags": ["food", "item", "basic"], "usage_context": "Rice meals at any South Indian restaurant",
     "grammar_note": "saaru = rasam, haakolli = please serve"},
    {"word": "Kaafi", "english": "Coffee", "usage_example": "Ondu kaafi kodi.",
     "tags": ["food", "drink", "basic"], "usage_context": "Filter coffee, Bengaluru's favourite"},
    {"word": "Neeru", "english": "Water", "usage_example": "Neeru kodi, please.",
     "tags": ["food", "drink", "basic"], "usage_context": "Asking for water at any restaurant"},
    {"word": "Spicy kammi", "english": "Less spicy", "usage_example": "Spicy kammi maadi, please.",
     "tags": ["food", "preference", "request"], "usage_context": "Customising spice level",
     "grammar_note": "kammi = less, maadi = make/do"},
    {"word": "Table beku", "english": "Need a table", "usage_example": "Naalkjanakke table beku.",
     "tags": ["food", "request"], "usage_context": "Getting seated at a restaurant",
     "grammar_note": "naalkjanakke = for four people"},
    {"word": "Yenu special?", "english": "What's the special?", "usage_example": "Indu yenu special ide?",
     "tags": ["food", "question"], "usage_context": "Asking about daily specials",
     "grammar_note": "yenu = what, indu = today"},
    {"word": "Thumba chennaagittu", "english": "It was very tasty", "usage_example": "Oota thumba chennaagittu!",
     "tags": ["food", "compliment", "polite"], "usage_context": "Complimenting the food after eating",
     "grammar_note": "thumba = very, chennaagittu = was nice/tasty"},
]

DIRECTIONS: list[SeedEntry] = [
    {"word": "Yelli", "english": "Where", "usage_example": "Bus stop yelli ide?",
     "tags": ["direction", "question", "basic"], "usage_context": "Asking location of anything"},
    {"word": "Illi", "english": "Here", "usage_example": "Illi banni.",
     "tags": ["direction", "basic"], "usage_context": "Pointing to current location",
     "grammar_note": "banni = come (polite imperative)"},
    {"word": "Alli", "english": "There", "usage_example": "Alli nodri, aa building.",
     "tags": ["direction", "basic"], "usage_context": "Pointing to a distant location",
     "grammar_note": "nodri = look (polite), aa = that"},
    {"word": "Balake", "english": "Right side", "usage_example": "Balake tirugri.",
     "tags": ["direction", "navigation"], "usage_context": "Giving or following directions",
     "grammar_note": "tirugri = turn (polite)"},
    {"word": "Edake", "english": "Left side", "usage_example": "Edake hogi.",
     "tags": ["direction", "navigation"], "usage_context": "Giving or following directions"},
    {"word": "Neravagi", "english": "Straight", "usage_example": "Neravagi hogi, signal hattira sigatte.",
     "tags": ["direction", "navigation"], "usage_context": "Directing someone to go straight",
     "grammar_note": "sigatte = you'll find/reach"},
    {"word": "Hattira", "english": "Near / Close", "usage_example": "Station hattira ide.",
     "tags": ["direction", "distance"], "usage_context": "Describing proximity"},
    {"word": "Doora", "english": "Far", "usage_example": "Thumba doora illa, hattira ide.",
     "tags": ["direction", "distance"], "usage_context": "Describing distance"},
    {"word": "Mundhe", "english": "Ahead / In front", "usage_example": "Mundhe hogi, signal ide.",
     "tags": ["direction", "navigation"], "usage_context": "Directing someone forward"},
    {"word": "Hinde", "english": "Behind / Back", "usage_example": "Hinde nodri, alli ide.",
     "tags": ["direction", "navigation"], "usage_context": "Pointing behind"},
    {"word": "Pakka", "english": "Next to / Beside", "usage_example": "Bank pakka ide.",
     "tags": ["direction", "position"], "usage_context": "Describing relative position",
     "grammar_note": "Also means 'sure/definite' in different context"},
    {"word": "Yelli ide?", "english": "Where is it?", "usage_example": "ATM yelli ide?",
     "tags": ["direction", "question"], "usage_context": "Quick location question for any place"},
]

SHOPPING: list[SeedEntry] = [
    {"word": "Bele yeshtu?", "english": "How much is the price?", "usage_example": "Ee shirt bele yeshtu?",
     "tags": ["shopping", "question", "money"], "usage_context": "Asking price at any shop",
     "grammar_note": "bele = price, ee = this"},
    {"word": "Thumba jaasti", "english": "Too expensive", "usage_example": "Thumba jaasti, kammi maadi.",
     "tags": ["shopping", "bargaining"], "usage_context": "Negotiating price at markets",
     "grammar_note": "jaasti = too much/more"},
    {"word": "Kammi maadi", "english": "Reduce the price", "usage_example": "Swalpa kammi maadi, please.",
     "tags": ["shopping", "bargaining", "request"], "usage_context": "Bargaining at street markets",
     "grammar_note": "swalpa = a little"},
    {"word": "Kodi", "english": "Give (me)", "usage_example": "Aa neelanadu kodi.",
     "tags": ["shopping", "request", "basic"], "usage_context": "Requesting any item from a shopkeeper",
     "grammar_note": "Polite imperative of 'kodu' (give)"},
    {"word": "Beku", "english": "Want / Need", "usage_example": "Naanige ee size beku.",
     "tags": ["shopping", "request", "basic"], "usage_context": "Expressing what you want to buy"},
    {"word": "Beda", "english": "Don't want", "usage_example": "Illa beda, bere nodthini.",
     "tags": ["shopping", "response"], "usage_context": "Declining an item or offer",
     "grammar_note": "nodthini = I'll look/see"},
    {"word": "Chennaagide", "english": "It's nice / good", "usage_example": "Ee banna chennaagide.",
     "tags": ["shopping", "opinion"], "usage_context": "Complimenting an item",
     "grammar_note": "banna = colour; chennaagide = is nice"},
    {"word": "Bere banna", "english": "Different color", "usage_example": "Bere banna ide aa?",
     "tags": ["shopping", "question"], "usage_context": "Asking for colour options"},
    {"word": "Size", "english": "Size", "usage_example": "Nanna size sigthilla.",
     "tags": ["shopping"], "usage_context": "Asking about clothing size",
     "grammar_note": "sigthilla = not finding"},
    {"word": "Cash/UPI", "english": "Cash or UPI payment", "usage_example": "UPI maadthini, okay aa?",
     "tags": ["shopping", "payment", "transaction"], "usage_context": "Choosing payment method"},
]

TIME_DAYS: list[SeedEntry] = [
    {"word": "Gante", "english": "Hour / O'clock", "usage_example": "Eeshtu gante aaythu?",
     "tags": ["time", "basic"], "usage_context": "Asking or telling time",
     "grammar_note": "aaythu = has become"},
    {"word": "Nimisha", "english": "Minute", "usage_example": "Aidu nimisha thaali.",
     "tags": ["time", "basic"], "usage_context": "Asking someone to wait"},
    {"word": "Indhu", "english": "Today", "usage_example": "Indhu yenu plan?",
     "tags": ["time", "basic"], "usage_context": "Talking about today's plans"},
    {"word": "Naalae", "english": "Tomorrow", "usage_example": "Naalae sigona.",
     "tags": ["time", "basic"], "usage_context": "Making plans for tomorrow",
     "grammar_note": "sigona = shall we meet"},
    {"word": "Ninne", "english": "Yesterday", "usage_example": "Ninne male banthu.",
     "tags": ["time", "basic"], "usage_context": "Talking about past events",
     "grammar_note": "male = rain, banthu = came"},
    {"word": "Beligge", "english": "Morning", "usage_example": "Beligge bega barthini.",
     "tags": ["time", "period"], "usage_context": "Morning time references"},
    {"word": "Sanje", "english": "Evening", "usage_example": "Sanje sigona.",
     "tags": ["time", "period"], "usage_context": "Evening plans"},
    {"word": "Raatri", "english": "Night", "usage_example": "Raatri oota aaytha?",
     "tags": ["time", "period"], "usage_context": "Night time references"},
    {"word": "Somavaara", "english": "Monday", "usage_example": "Somavaara office ide.",
     "tags": ["time", "day"], "usage_context": "Naming days of the week"},
    {"word": "Shukravaara", "english": "Friday", "usage_example": "Shukravaara chutti beku.",
     "tags": ["time", "day"], "usage_context": "Weekend planning",
     "grammar_note": "chutti = holiday/leave"},
    {"word": "Shanivara", "english": "Saturday", "usage_example": "Shanivara free idhini.",
     "tags": ["time", "day"], "usage_context": "Weekend planning"},
    {"word": "Bhanuvaara", "english": "Sunday", "usage_example": "Bhanuvaara rest maadthini.",
     "tags": ["time", "day"], "usage_context": "Weekend references"},
]

PHONE_COURTESY: list[SeedEntry] = [
    {"word": "Hello", "english": "Hello (phone greeting)", "usage_example": "Hello, yaaru maathaadhthiddira?",
     "tags": ["phone", "greeting"], "usage_context": "Answering or starting a phone call"},
    {"word": "Yaaru?", "english": "Who is this?", "usage_example": "Yaaru maathaadhthiddira?",
     "tags": ["phone", "question"], "usage_context": "Asking caller identity",
     "grammar_note": "maathaadhthiddira = who is speaking (respectful)"},
    {"word": "Call maadthini", "english": "I'll call", "usage_example": "Nanthara call maadthini.",
     "tags": ["phone", "promise"], "usage_context": "Promising to call back",
     "grammar_note": "nanthara = later"},
    {"word": "Message kalisthini", "english": "I'll send a message", "usage_example": "Nanthara message kalisthini.",
     "tags": ["phone", "promise"], "usage_context": "Promising to text back"},
    {"word": "Busy idhini", "english": "I am busy", "usage_example": "Eega busy idhini, nanthara maathaadhona.",
     "tags": ["phone", "excuse"], "usage_context": "Politely declining a call",
     "grammar_note": "eega = now, maathaadhona = let's talk"},
    {"word": "Free aadmele", "english": "After I'm free", "usage_example": "Free aadmele call maadthini.",
     "tags": ["phone", "time"], "usage_context": "Deferring a conversation"},
    {"word": "Wrong number", "english": "Wrong number", "usage_example": "Sorry, wrong number.",
     "tags": ["phone"], "usage_context": "When someone dials wrong"},
    {"word": "Network illa", "english": "No network", "usage_example": "Illi network illa, horate hogthini.",
     "tags": ["phone", "excuse"], "usage_context": "Explaining connectivity issues",
     "grammar_note": "horate = outside, hogthini = I'll go"},
    {"word": "Kshamisi", "english": "Excuse me / Sorry", "usage_example": "Kshamisi, yaaru beku?",
     "tags": ["phone", "polite"], "usage_context": "Polite interruption on phone or in person",
     "grammar_note": "From kshama (forgiveness)"},
    {"word": "Thumba thanks", "english": "Thanks a lot", "usage_example": "Thumba thanks, help maadidikke.",
     "tags": ["phone", "gratitude", "polite"], "usage_context": "Thanking someone on the phone",
     "grammar_note": "maadidikke = for having done/helped"},
]

# ---------------------------------------------------------------------------
# Ring-structured unit registry
# ---------------------------------------------------------------------------

UNIT_RINGS: dict[str, int] = {
    # Ring 0 — Survival Reflexes
    "greetings": 0,
    "emergency_toolkit": 0,
    "numbers_money": 0,
    "first_transactions": 0,
    # Ring 1 — Transactional Independence
    "transport": 1,
    "food_ordering": 1,
    "directions": 1,
    "shopping": 1,
    "time_days": 1,
    "phone_courtesy": 1,
}

ALL_UNITS: dict[str, list[SeedEntry]] = {
    # Ring 0
    "greetings": GREETINGS,
    "emergency_toolkit": EMERGENCY_TOOLKIT,
    "numbers_money": NUMBERS_MONEY,
    "first_transactions": FIRST_TRANSACTIONS,
    # Ring 1
    "transport": TRANSPORT,
    "food_ordering": FOOD_ORDERING,
    "directions": DIRECTIONS,
    "shopping": SHOPPING,
    "time_days": TIME_DAYS,
    "phone_courtesy": PHONE_COURTESY,
}

# Human-readable unit names for CurriculumUnit.name
UNIT_NAMES: dict[str, str] = {
    "greetings": "Greetings & Politeness",
    "emergency_toolkit": "Emergency Toolkit",
    "numbers_money": "Numbers 1-20 + Money",
    "first_transactions": "First Transactions",
    "transport": "Transport",
    "food_ordering": "Food & Ordering",
    "directions": "Directions & Places",
    "shopping": "Shopping & Prices",
    "time_days": "Time & Days",
    "phone_courtesy": "Phone & Basic Courtesy",
}


async def seed_vocabulary(*, dry_run: bool = False) -> int:
    """Insert seed curriculum units and vocabulary into the database.

    Populates ``CurriculumUnit`` and ``UnitVocabulary`` tables.
    Skips units/words that already exist (matched on slug / word text).

    Returns the number of newly inserted vocabulary items.
    """
    inserted = 0

    async with AsyncSessionLocal() as db:
        for unit_order, (unit_slug, entries) in enumerate(ALL_UNITS.items(), start=1):
            ring = UNIT_RINGS[unit_slug]
            name = UNIT_NAMES[unit_slug]

            # Upsert CurriculumUnit
            result = await db.execute(
                select(CurriculumUnit).where(CurriculumUnit.slug == unit_slug)
            )
            cu = result.scalar_one_or_none()
            if cu is None:
                cu = CurriculumUnit(
                    ring=ring,
                    unit_order=unit_order,
                    name=name,
                    slug=unit_slug,
                )
                db.add(cu)
                await db.flush()  # get cu.id
                logger.info("Created CurriculumUnit: %s (ring %d)", unit_slug, ring)

            # Insert vocabulary entries
            for entry in entries:
                result = await db.execute(
                    select(UnitVocabulary).where(
                        UnitVocabulary.unit_id == cu.id,
                        UnitVocabulary.word == entry["word"],
                    )
                )
                if result.scalar_one_or_none() is not None:
                    continue

                if dry_run:
                    logger.info(
                        "dry-run: would insert %s → %s (unit: %s)",
                        entry["english"],
                        entry["word"],
                        unit_slug,
                    )
                    inserted += 1
                    continue

                vocab = UnitVocabulary(
                    unit_id=cu.id,
                    word=entry["word"],
                    roman=entry["word"],
                    english=entry["english"],
                    usage_example=entry.get("usage_example"),
                    tags=entry.get("tags"),
                    usage_context=entry.get("usage_context"),
                    grammar_note=entry.get("grammar_note"),
                )
                db.add(vocab)
                inserted += 1

        if not dry_run:
            await db.commit()

    logger.info("seed_vocabulary: inserted %d items", inserted)
    return inserted
