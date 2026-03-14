"""Seed vocabulary data for Level 1 and Level 2 curriculum units.

Each unit contains 10-15 words in colloquial Bengaluru Kannada (Roman
transliteration).  Call ``seed_vocabulary()`` at startup or from a
management command to populate the vocabulary_items table.
"""

from __future__ import annotations

import logging
from typing import TypedDict

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.vocabulary import VocabularyItem

logger = logging.getLogger(__name__)


class SeedEntry(TypedDict):
    unit: str
    word: str  # Kannada Roman transliteration
    english: str
    usage_example: str


# ---------------------------------------------------------------------------
# Level 1 units
# ---------------------------------------------------------------------------

GREETINGS: list[SeedEntry] = [
    {"unit": "greetings", "word": "Namaskara", "english": "Hello / Greetings", "usage_example": "Namaskara, hegiddira?"},
    {"unit": "greetings", "word": "Hegiddira?", "english": "How are you?", "usage_example": "Hegiddira? Chennagiddira?"},
    {"unit": "greetings", "word": "Nanna hesaru", "english": "My name is", "usage_example": "Nanna hesaru Anil."},
    {"unit": "greetings", "word": "Dhanyavada", "english": "Thank you", "usage_example": "Thumba dhanyavada, sir."},
    {"unit": "greetings", "word": "Hogi banni", "english": "Goodbye (go and come)", "usage_example": "Sari, hogi banni!"},
    {"unit": "greetings", "word": "Shubha dinadalli", "english": "Good day / Good wishes", "usage_example": "Nimge shubha dinadalli."},
    {"unit": "greetings", "word": "Shubha raatri", "english": "Good night", "usage_example": "Shubha raatri, naalae sigona."},
    {"unit": "greetings", "word": "Houdhu", "english": "Yes", "usage_example": "Houdhu, naanu ready."},
    {"unit": "greetings", "word": "Illa", "english": "No", "usage_example": "Illa, naanu baralla."},
    {"unit": "greetings", "word": "Dayavittu", "english": "Please", "usage_example": "Dayavittu illi kootko."},
]

NUMBERS: list[SeedEntry] = [
    {"unit": "numbers", "word": "Ondu", "english": "One", "usage_example": "Ondu kaafi kodi."},
    {"unit": "numbers", "word": "Eradu", "english": "Two", "usage_example": "Eradu dosa beku."},
    {"unit": "numbers", "word": "Mooru", "english": "Three", "usage_example": "Mooru jana idivi."},
    {"unit": "numbers", "word": "Nalku", "english": "Four", "usage_example": "Nalku gante aaytu."},
    {"unit": "numbers", "word": "Aidu", "english": "Five", "usage_example": "Aidu nimisha thaali."},
    {"unit": "numbers", "word": "Aaru", "english": "Six", "usage_example": "Aaru gantege barthini."},
    {"unit": "numbers", "word": "Yelu", "english": "Seven", "usage_example": "Yelu dina beku."},
    {"unit": "numbers", "word": "Entu", "english": "Eight", "usage_example": "Entu rupayi aaytu."},
    {"unit": "numbers", "word": "Ombattu", "english": "Nine", "usage_example": "Ombattu gantege meeting ide."},
    {"unit": "numbers", "word": "Hattu", "english": "Ten", "usage_example": "Hattu rupayi kodi."},
    {"unit": "numbers", "word": "Nooru", "english": "Hundred", "usage_example": "Nooru rupayi aagatte."},
    {"unit": "numbers", "word": "Saavira", "english": "Thousand", "usage_example": "Ondu saavira rupayi beku."},
]

FAMILY: list[SeedEntry] = [
    {"unit": "family", "word": "Amma", "english": "Mother", "usage_example": "Nanna amma maneyalli idare."},
    {"unit": "family", "word": "Appa", "english": "Father", "usage_example": "Nanna appa office ge hogidare."},
    {"unit": "family", "word": "Anna", "english": "Elder brother", "usage_example": "Nanna anna Bangalore nalli kelsa madthare."},
    {"unit": "family", "word": "Akka", "english": "Elder sister", "usage_example": "Nanna akka teacher."},
    {"unit": "family", "word": "Tamma", "english": "Younger brother", "usage_example": "Nanna tamma school ge hogthane."},
    {"unit": "family", "word": "Tangi", "english": "Younger sister", "usage_example": "Nanna tangi chikku iddaale."},
    {"unit": "family", "word": "Ajji", "english": "Grandmother", "usage_example": "Ajji thumba olle saaru maadthare."},
    {"unit": "family", "word": "Tata", "english": "Grandfather", "usage_example": "Tata tota nalli idare."},
    {"unit": "family", "word": "Maga", "english": "Son", "usage_example": "Avara maga engineer."},
    {"unit": "family", "word": "Magalu", "english": "Daughter", "usage_example": "Avara magalu doctor aagidaale."},
]

FOOD: list[SeedEntry] = [
    {"unit": "food", "word": "Oota", "english": "Meal / Food", "usage_example": "Oota aaytha?"},
    {"unit": "food", "word": "Neeru", "english": "Water", "usage_example": "Neeru kodi, please."},
    {"unit": "food", "word": "Kaafi", "english": "Coffee", "usage_example": "Ondu kaafi kodi."},
    {"unit": "food", "word": "Chaaha", "english": "Tea", "usage_example": "Bisi chaaha beku."},
    {"unit": "food", "word": "Dosa", "english": "Dosa (crepe)", "usage_example": "Masala dosa kodi."},
    {"unit": "food", "word": "Idli", "english": "Idli (steamed cake)", "usage_example": "Eradu idli chutney jote kodi."},
    {"unit": "food", "word": "Roti", "english": "Flatbread", "usage_example": "Mooru roti palya jote kodi."},
    {"unit": "food", "word": "Anna", "english": "Rice", "usage_example": "Anna saaru haakolli."},
    {"unit": "food", "word": "Saaru", "english": "Rasam (soup)", "usage_example": "Saaru thumba chennaagide."},
    {"unit": "food", "word": "Palya", "english": "Vegetable dish", "usage_example": "Indu yaav palya ide?"},
    {"unit": "food", "word": "Haalu", "english": "Milk", "usage_example": "Bisi haalu beku."},
    {"unit": "food", "word": "Hannina rasa", "english": "Fruit juice", "usage_example": "Maavinhannina rasa kodi."},
]

DIRECTIONS: list[SeedEntry] = [
    {"unit": "directions", "word": "Yelli", "english": "Where", "usage_example": "Bus stop yelli ide?"},
    {"unit": "directions", "word": "Illi", "english": "Here", "usage_example": "Illi banni."},
    {"unit": "directions", "word": "Alli", "english": "There", "usage_example": "Alli nodri, aa building."},
    {"unit": "directions", "word": "Balake", "english": "Right side", "usage_example": "Balake tirugri."},
    {"unit": "directions", "word": "Edake", "english": "Left side", "usage_example": "Edake hogi."},
    {"unit": "directions", "word": "Neravagi", "english": "Straight", "usage_example": "Neravagi hogi, signal hattira sigatte."},
    {"unit": "directions", "word": "Hattira", "english": "Near / Close", "usage_example": "Station hattira ide."},
    {"unit": "directions", "word": "Doora", "english": "Far", "usage_example": "Thumba doora illa, hattira ide."},
    {"unit": "directions", "word": "Mundhe", "english": "Ahead / In front", "usage_example": "Mundhe hogi, signal ide."},
    {"unit": "directions", "word": "Hinde", "english": "Behind / Back", "usage_example": "Hinde nodri, alli ide."},
]

TRANSPORT: list[SeedEntry] = [
    {"unit": "transport", "word": "Bus", "english": "Bus", "usage_example": "Majestic ge bus yavdu?"},
    {"unit": "transport", "word": "Auto", "english": "Auto rickshaw", "usage_example": "Auto maadbeku, Koramangala ge."},
    {"unit": "transport", "word": "Taxi", "english": "Taxi / Cab", "usage_example": "Taxi book maadidini."},
    {"unit": "transport", "word": "Nildana", "english": "Bus stop / Stand", "usage_example": "Mundina nildana yavdu?"},
    {"unit": "transport", "word": "Yeshtu aagatte?", "english": "How much will it cost?", "usage_example": "Indiranagar ge yeshtu aagatte?"},
    {"unit": "transport", "word": "Illi nilsi", "english": "Stop here", "usage_example": "Driver, illi nilsi."},
    {"unit": "transport", "word": "Hogbekku", "english": "I need to go", "usage_example": "Naanu MG Road ge hogbekku."},
    {"unit": "transport", "word": "Station yelli?", "english": "Where is the station?", "usage_example": "Metro station yelli ide?"},
    {"unit": "transport", "word": "Ticket", "english": "Ticket", "usage_example": "Eradu ticket kodi."},
    {"unit": "transport", "word": "Bega", "english": "Quickly / Fast", "usage_example": "Bega hogi, late aagthide."},
]

# ---------------------------------------------------------------------------
# Level 2 units
# ---------------------------------------------------------------------------

SHOPPING: list[SeedEntry] = [
    {"unit": "shopping", "word": "Bele yeshtu?", "english": "How much is the price?", "usage_example": "Ee shirt bele yeshtu?"},
    {"unit": "shopping", "word": "Thumba jaasti", "english": "Too expensive", "usage_example": "Thumba jaasti, kammi maadi."},
    {"unit": "shopping", "word": "Kammi maadi", "english": "Reduce the price", "usage_example": "Swalpa kammi maadi, please."},
    {"unit": "shopping", "word": "Kodi", "english": "Give (me)", "usage_example": "Aa neelanadu kodi."},
    {"unit": "shopping", "word": "Beku", "english": "Want / Need", "usage_example": "Naanige ee size beku."},
    {"unit": "shopping", "word": "Beda", "english": "Don't want", "usage_example": "Illa beda, bere nodthini."},
    {"unit": "shopping", "word": "Chennaagide", "english": "It's nice / good", "usage_example": "Ee banna chennaagide."},
    {"unit": "shopping", "word": "Bere banna", "english": "Different color", "usage_example": "Bere banna ide aa?"},
    {"unit": "shopping", "word": "Size sigthilla", "english": "Size not available", "usage_example": "Nanna size sigthilla."},
    {"unit": "shopping", "word": "Cash/UPI", "english": "Cash or UPI payment", "usage_example": "UPI maadthini, okay aa?"},
]

RESTAURANTS: list[SeedEntry] = [
    {"unit": "restaurants", "word": "Menu kodi", "english": "Give the menu", "usage_example": "Menu kodi, please."},
    {"unit": "restaurants", "word": "Oota ready aa?", "english": "Is the food ready?", "usage_example": "Namma oota ready aa?"},
    {"unit": "restaurants", "word": "Spicy kammi", "english": "Less spicy", "usage_example": "Spicy kammi maadi, please."},
    {"unit": "restaurants", "word": "Bill kodi", "english": "Give the bill", "usage_example": "Bill kodi, hogbekku."},
    {"unit": "restaurants", "word": "Parcel maadi", "english": "Pack it / Takeaway", "usage_example": "Eradu biryani parcel maadi."},
    {"unit": "restaurants", "word": "Thindi", "english": "Snack", "usage_example": "Swalpa thindi thinona banni."},
    {"unit": "restaurants", "word": "Neeru kodi", "english": "Give water", "usage_example": "Swalpa neeru kodi."},
    {"unit": "restaurants", "word": "Thumba chennaagittu", "english": "It was very tasty", "usage_example": "Oota thumba chennaagittu!"},
    {"unit": "restaurants", "word": "Table beku", "english": "Need a table", "usage_example": "Naalkjanakke table beku."},
    {"unit": "restaurants", "word": "Yenu special?", "english": "What's the special?", "usage_example": "Indu yenu special ide?"},
]

PHONE_CALLS: list[SeedEntry] = [
    {"unit": "phone_calls", "word": "Hello", "english": "Hello (phone greeting)", "usage_example": "Hello, yaaru maathaadhthiddira?"},
    {"unit": "phone_calls", "word": "Yaaru?", "english": "Who is this?", "usage_example": "Yaaru maathaadhthiddira?"},
    {"unit": "phone_calls", "word": "Naaliddu call maadthini", "english": "I'll call tomorrow", "usage_example": "Naanu naaliddu call maadthini."},
    {"unit": "phone_calls", "word": "Message kalisthini", "english": "I'll send a message", "usage_example": "Nanthara message kalisthini."},
    {"unit": "phone_calls", "word": "Phone sigthilla", "english": "Phone not reachable", "usage_example": "Avra phone sigthilla."},
    {"unit": "phone_calls", "word": "Busy idhini", "english": "I am busy", "usage_example": "Eega busy idhini, nanthara maathaadhona."},
    {"unit": "phone_calls", "word": "Free aadmele", "english": "After I'm free", "usage_example": "Free aadmele call maadthini."},
    {"unit": "phone_calls", "word": "Wrong number", "english": "Wrong number", "usage_example": "Sorry, wrong number."},
    {"unit": "phone_calls", "word": "Cut maadu", "english": "Hang up / Disconnect", "usage_example": "Sari, cut maadu, nanthara maathaadhona."},
    {"unit": "phone_calls", "word": "Network illa", "english": "No network", "usage_example": "Illi network illa, horate hogthini."},
]

WEATHER: list[SeedEntry] = [
    {"unit": "weather", "word": "Bisilu", "english": "Sunshine / Sunny", "usage_example": "Indu thumba bisilu ide."},
    {"unit": "weather", "word": "Chali", "english": "Cold", "usage_example": "Beligge thumba chali ide."},
    {"unit": "weather", "word": "Male", "english": "Rain", "usage_example": "Male barthide, chatri togo."},
    {"unit": "weather", "word": "Gaali", "english": "Wind", "usage_example": "Thumba gaali barthide."},
    {"unit": "weather", "word": "Mooda", "english": "Cloudy / Overcast", "usage_example": "Aakasha mooda ide."},
    {"unit": "weather", "word": "Bisi", "english": "Hot", "usage_example": "Indu thumba bisi ide."},
    {"unit": "weather", "word": "Thandane", "english": "Cool / Pleasant", "usage_example": "Sanje thumba thandane ide."},
    {"unit": "weather", "word": "Male barthide", "english": "It's going to rain", "usage_example": "Male barthide, olagade iri."},
    {"unit": "weather", "word": "Chatri beku", "english": "Need an umbrella", "usage_example": "Male ide, chatri beku."},
    {"unit": "weather", "word": "Chaliagide", "english": "It's cold / feeling cold", "usage_example": "Naanige chaliagide, sweater kodi."},
]

EMOTIONS: list[SeedEntry] = [
    {"unit": "emotions", "word": "Khushi", "english": "Happy / Happiness", "usage_example": "Naanige thumba khushi aagide."},
    {"unit": "emotions", "word": "Kashta", "english": "Difficulty / Hardship", "usage_example": "Thumba kashta aaythu."},
    {"unit": "emotions", "word": "Kopa", "english": "Anger", "usage_example": "Yaake eshtu kopa?"},
    {"unit": "emotions", "word": "Bhaya", "english": "Fear", "usage_example": "Naanige bhaya aagthide."},
    {"unit": "emotions", "word": "Preethi", "english": "Love / Affection", "usage_example": "Thumba preethi ide nimma mele."},
    {"unit": "emotions", "word": "Ascharyaa", "english": "Surprise / Amazement", "usage_example": "Ascharyaa! Neenu illi?"},
    {"unit": "emotions", "word": "Boring", "english": "Boring / Bored", "usage_example": "Thumba boring aagide."},
    {"unit": "emotions", "word": "Santhoshaa", "english": "Joy / Delight", "usage_example": "Nimmannu nodhi santhoshaa aaythu."},
    {"unit": "emotions", "word": "Dukha", "english": "Sadness / Sorrow", "usage_example": "Aa vishya kelhi dukha aaythu."},
    {"unit": "emotions", "word": "Tension", "english": "Tension / Stress", "usage_example": "Tension maadkobedi, ella sari aagatte."},
]

HEALTH: list[SeedEntry] = [
    {"unit": "health", "word": "Hushaarilla", "english": "Not feeling well", "usage_example": "Naanige hushaarilla, maneyalli irthini."},
    {"unit": "health", "word": "Talenoovu", "english": "Headache", "usage_example": "Thumba talenoovu ide."},
    {"unit": "health", "word": "Hotteynoovu", "english": "Stomach ache", "usage_example": "Hotteynoovu barthide, tablet kodi."},
    {"unit": "health", "word": "Jwara", "english": "Fever", "usage_example": "Jwara barthide, doctor hattira hogbekku."},
    {"unit": "health", "word": "Novu", "english": "Pain", "usage_example": "Kaalu novu ide."},
    {"unit": "health", "word": "Doctor beku", "english": "Need a doctor", "usage_example": "Doctor beku, hushaarilla."},
    {"unit": "health", "word": "Maatre", "english": "Tablet / Medicine", "usage_example": "Maatre thogondu, vishraanthi thogo."},
    {"unit": "health", "word": "Aaspatre", "english": "Hospital", "usage_example": "Hattira aaspatre yelli ide?"},
    {"unit": "health", "word": "Vishraanthi", "english": "Rest", "usage_example": "Swalpa vishraanthi thogo."},
    {"unit": "health", "word": "Vaanthi", "english": "Vomiting / Nausea", "usage_example": "Vaanthi aagthide, doctor ge hogi."},
]

# ---------------------------------------------------------------------------
# All units combined
# ---------------------------------------------------------------------------

ALL_UNITS: dict[str, list[SeedEntry]] = {
    # Level 1
    "greetings": GREETINGS,
    "numbers": NUMBERS,
    "family": FAMILY,
    "food": FOOD,
    "directions": DIRECTIONS,
    "transport": TRANSPORT,
    # Level 2
    "shopping": SHOPPING,
    "restaurants": RESTAURANTS,
    "phone_calls": PHONE_CALLS,
    "weather": WEATHER,
    "emotions": EMOTIONS,
    "health": HEALTH,
}

UNIT_LEVELS: dict[str, int] = {
    "greetings": 1, "numbers": 1, "family": 1,
    "food": 1, "directions": 1, "transport": 1,
    "shopping": 2, "restaurants": 2, "phone_calls": 2,
    "weather": 2, "emotions": 2, "health": 2,
}


async def seed_vocabulary(*, dry_run: bool = False) -> int:
    """Insert seed vocabulary into the database.

    Skips words that already exist (matched on ``VocabularyItem.word``).

    Returns the number of newly inserted items.
    """
    inserted = 0

    async with AsyncSessionLocal() as db:
        for unit_slug, entries in ALL_UNITS.items():
            level = UNIT_LEVELS[unit_slug]
            for entry in entries:
                result = await db.execute(
                    select(VocabularyItem).where(
                        VocabularyItem.word == entry["english"]
                    )
                )
                if result.scalar_one_or_none() is not None:
                    continue

                if dry_run:
                    logger.info(
                        "dry-run: would insert %s → %s",
                        entry["english"],
                        entry["word"],
                    )
                    inserted += 1
                    continue

                vocab_item = VocabularyItem(
                    word=entry["english"],
                    translations={
                        "roman": entry["word"],
                        "explanation": entry["usage_example"],
                    },
                    tags=[f"unit:{unit_slug}", f"level:{level}"],
                )
                db.add(vocab_item)
                inserted += 1

        if not dry_run:
            await db.commit()

    logger.info("seed_vocabulary: inserted %d items", inserted)
    return inserted
