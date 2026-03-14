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


class SeedEntry(TypedDict):
    word: str  # Kannada Roman transliteration
    english: str
    usage_example: str


# ---------------------------------------------------------------------------
# Ring 0 — Survival Kit (4 units, ~10 atoms each)
# ---------------------------------------------------------------------------

GREETINGS: list[SeedEntry] = [
    {"word": "Namaskara", "english": "Hello / Greetings", "usage_example": "Namaskara, hegiddira?"},
    {"word": "Hegiddira?", "english": "How are you?", "usage_example": "Hegiddira? Chennagiddira?"},
    {"word": "Nanna hesaru", "english": "My name is", "usage_example": "Nanna hesaru Anil."},
    {"word": "Dhanyavada", "english": "Thank you", "usage_example": "Thumba dhanyavada, sir."},
    {"word": "Hogi banni", "english": "Goodbye (go and come)", "usage_example": "Sari, hogi banni!"},
    {"word": "Shubha dinadalli", "english": "Good day / Good wishes", "usage_example": "Nimge shubha dinadalli."},
    {"word": "Shubha raatri", "english": "Good night", "usage_example": "Shubha raatri, naalae sigona."},
    {"word": "Houdhu", "english": "Yes", "usage_example": "Houdhu, naanu ready."},
    {"word": "Illa", "english": "No", "usage_example": "Illa, naanu baralla."},
    {"word": "Dayavittu", "english": "Please", "usage_example": "Dayavittu illi kootko."},
]

EMERGENCY_TOOLKIT: list[SeedEntry] = [
    {"word": "Help maadi", "english": "Help me", "usage_example": "Dayavittu help maadi!"},
    {"word": "Naanige gothilla", "english": "I don't know / understand", "usage_example": "Sorry, naanige gothilla."},
    {"word": "Nidhaanavaagi maathaadi", "english": "Please speak slowly", "usage_example": "Dayavittu nidhaanavaagi maathaadi."},
    {"word": "Doctor beku", "english": "Need a doctor", "usage_example": "Doctor beku, hushaarilla."},
    {"word": "Aaspatre yelli?", "english": "Where is the hospital?", "usage_example": "Hattira aaspatre yelli ide?"},
    {"word": "Police", "english": "Police", "usage_example": "Police ge call maadi."},
    {"word": "Hushaarilla", "english": "Not feeling well", "usage_example": "Naanige hushaarilla."},
    {"word": "Kannada barthilla", "english": "I don't speak Kannada", "usage_example": "Naanige Kannada barthilla."},
    {"word": "English barthaa?", "english": "Do you speak English?", "usage_example": "Nimge English barthaa?"},
    {"word": "Swalpa Kannada baratte", "english": "I know a little Kannada", "usage_example": "Naanige swalpa Kannada baratte."},
]

NUMBERS_MONEY: list[SeedEntry] = [
    {"word": "Ondu", "english": "One", "usage_example": "Ondu kaafi kodi."},
    {"word": "Eradu", "english": "Two", "usage_example": "Eradu dosa beku."},
    {"word": "Mooru", "english": "Three", "usage_example": "Mooru jana idivi."},
    {"word": "Nalku", "english": "Four", "usage_example": "Nalku gante aaytu."},
    {"word": "Aidu", "english": "Five", "usage_example": "Aidu nimisha thaali."},
    {"word": "Aaru", "english": "Six", "usage_example": "Aaru gantege barthini."},
    {"word": "Yelu", "english": "Seven", "usage_example": "Yelu dina beku."},
    {"word": "Entu", "english": "Eight", "usage_example": "Entu rupayi aaytu."},
    {"word": "Ombattu", "english": "Nine", "usage_example": "Ombattu gantege meeting ide."},
    {"word": "Hattu", "english": "Ten", "usage_example": "Hattu rupayi kodi."},
    {"word": "Ippattu", "english": "Twenty", "usage_example": "Ippattu rupayi aagatte."},
    {"word": "Nooru", "english": "Hundred", "usage_example": "Nooru rupayi aagatte."},
    {"word": "Saavira", "english": "Thousand", "usage_example": "Ondu saavira rupayi beku."},
    {"word": "Rupayi", "english": "Rupees", "usage_example": "Yeshtu rupayi aagatte?"},
    {"word": "Yeshtu aagatte?", "english": "How much will it cost?", "usage_example": "Idhu yeshtu aagatte?"},
]

FIRST_TRANSACTIONS: list[SeedEntry] = [
    {"word": "Ondu kaafi kodi", "english": "Give me one coffee", "usage_example": "Ondu kaafi kodi, please."},
    {"word": "Eradu dosa kodi", "english": "Give me two dosas", "usage_example": "Eradu masala dosa kodi."},
    {"word": "Bill kodi", "english": "Give the bill", "usage_example": "Bill kodi, hogbekku."},
    {"word": "Parcel maadi", "english": "Pack it / Takeaway", "usage_example": "Eradu idli parcel maadi."},
    {"word": "Neeru kodi", "english": "Give water", "usage_example": "Swalpa neeru kodi."},
    {"word": "Beku", "english": "Want / Need", "usage_example": "Ondu chaaha beku."},
    {"word": "Beda", "english": "Don't want", "usage_example": "Illa beda, saaku."},
    {"word": "Yeshtu?", "english": "How much?", "usage_example": "Idhu yeshtu?"},
    {"word": "UPI maadthini", "english": "I'll pay by UPI", "usage_example": "UPI maadthini, okay aa?"},
    {"word": "Cash", "english": "Cash payment", "usage_example": "Cash kodi, change ide aa?"},
]

# ---------------------------------------------------------------------------
# Ring 1 — Daily Survival (6 units, ~12 atoms each)
# ---------------------------------------------------------------------------

TRANSPORT: list[SeedEntry] = [
    {"word": "Bus", "english": "Bus", "usage_example": "Majestic ge bus yavdu?"},
    {"word": "Auto", "english": "Auto rickshaw", "usage_example": "Auto maadbeku, Koramangala ge."},
    {"word": "Metro", "english": "Metro train", "usage_example": "Metro station yelli ide?"},
    {"word": "Nildana", "english": "Bus stop / Stand", "usage_example": "Mundina nildana yavdu?"},
    {"word": "Illi nilsi", "english": "Stop here", "usage_example": "Driver, illi nilsi."},
    {"word": "Hogbekku", "english": "I need to go", "usage_example": "Naanu MG Road ge hogbekku."},
    {"word": "Station yelli?", "english": "Where is the station?", "usage_example": "Metro station yelli ide?"},
    {"word": "Ticket", "english": "Ticket", "usage_example": "Eradu ticket kodi."},
    {"word": "Yeshtu aagatte?", "english": "How much will it cost?", "usage_example": "Indiranagar ge yeshtu aagatte?"},
    {"word": "Bega", "english": "Quickly / Fast", "usage_example": "Bega hogi, late aagthide."},
    {"word": "Taxi", "english": "Taxi / Cab", "usage_example": "Taxi book maadidini."},
    {"word": "Irangthini", "english": "I'll get off", "usage_example": "Mundina stop nalli irangthini."},
]

FOOD_ORDERING: list[SeedEntry] = [
    {"word": "Menu kodi", "english": "Give the menu", "usage_example": "Menu kodi, please."},
    {"word": "Oota", "english": "Meal / Food", "usage_example": "Oota aaytha?"},
    {"word": "Dosa", "english": "Dosa (crepe)", "usage_example": "Masala dosa kodi."},
    {"word": "Idli", "english": "Idli (steamed cake)", "usage_example": "Eradu idli chutney jote kodi."},
    {"word": "Roti", "english": "Flatbread", "usage_example": "Mooru roti palya jote kodi."},
    {"word": "Anna", "english": "Rice", "usage_example": "Anna saaru haakolli."},
    {"word": "Kaafi", "english": "Coffee", "usage_example": "Ondu kaafi kodi."},
    {"word": "Neeru", "english": "Water", "usage_example": "Neeru kodi, please."},
    {"word": "Spicy kammi", "english": "Less spicy", "usage_example": "Spicy kammi maadi, please."},
    {"word": "Table beku", "english": "Need a table", "usage_example": "Naalkjanakke table beku."},
    {"word": "Yenu special?", "english": "What's the special?", "usage_example": "Indu yenu special ide?"},
    {"word": "Thumba chennaagittu", "english": "It was very tasty", "usage_example": "Oota thumba chennaagittu!"},
]

DIRECTIONS: list[SeedEntry] = [
    {"word": "Yelli", "english": "Where", "usage_example": "Bus stop yelli ide?"},
    {"word": "Illi", "english": "Here", "usage_example": "Illi banni."},
    {"word": "Alli", "english": "There", "usage_example": "Alli nodri, aa building."},
    {"word": "Balake", "english": "Right side", "usage_example": "Balake tirugri."},
    {"word": "Edake", "english": "Left side", "usage_example": "Edake hogi."},
    {"word": "Neravagi", "english": "Straight", "usage_example": "Neravagi hogi, signal hattira sigatte."},
    {"word": "Hattira", "english": "Near / Close", "usage_example": "Station hattira ide."},
    {"word": "Doora", "english": "Far", "usage_example": "Thumba doora illa, hattira ide."},
    {"word": "Mundhe", "english": "Ahead / In front", "usage_example": "Mundhe hogi, signal ide."},
    {"word": "Hinde", "english": "Behind / Back", "usage_example": "Hinde nodri, alli ide."},
    {"word": "Pakka", "english": "Next to / Beside", "usage_example": "Bank pakka ide."},
    {"word": "Yelli ide?", "english": "Where is it?", "usage_example": "ATM yelli ide?"},
]

SHOPPING: list[SeedEntry] = [
    {"word": "Bele yeshtu?", "english": "How much is the price?", "usage_example": "Ee shirt bele yeshtu?"},
    {"word": "Thumba jaasti", "english": "Too expensive", "usage_example": "Thumba jaasti, kammi maadi."},
    {"word": "Kammi maadi", "english": "Reduce the price", "usage_example": "Swalpa kammi maadi, please."},
    {"word": "Kodi", "english": "Give (me)", "usage_example": "Aa neelanadu kodi."},
    {"word": "Beku", "english": "Want / Need", "usage_example": "Naanige ee size beku."},
    {"word": "Beda", "english": "Don't want", "usage_example": "Illa beda, bere nodthini."},
    {"word": "Chennaagide", "english": "It's nice / good", "usage_example": "Ee banna chennaagide."},
    {"word": "Bere banna", "english": "Different color", "usage_example": "Bere banna ide aa?"},
    {"word": "Size", "english": "Size", "usage_example": "Nanna size sigthilla."},
    {"word": "Cash/UPI", "english": "Cash or UPI payment", "usage_example": "UPI maadthini, okay aa?"},
]

TIME_DAYS: list[SeedEntry] = [
    {"word": "Gante", "english": "Hour / O'clock", "usage_example": "Eeshtu gante aaythu?"},
    {"word": "Nimisha", "english": "Minute", "usage_example": "Aidu nimisha thaali."},
    {"word": "Indhu", "english": "Today", "usage_example": "Indhu yenu plan?"},
    {"word": "Naalae", "english": "Tomorrow", "usage_example": "Naalae sigona."},
    {"word": "Ninne", "english": "Yesterday", "usage_example": "Ninne male banthu."},
    {"word": "Beligge", "english": "Morning", "usage_example": "Beligge bega barthini."},
    {"word": "Sanje", "english": "Evening", "usage_example": "Sanje sigona."},
    {"word": "Raatri", "english": "Night", "usage_example": "Raatri oota aaytha?"},
    {"word": "Somavaara", "english": "Monday", "usage_example": "Somavaara office ide."},
    {"word": "Shukravaara", "english": "Friday", "usage_example": "Shukravaara chutti beku."},
    {"word": "Shanivara", "english": "Saturday", "usage_example": "Shanivara free idhini."},
    {"word": "Bhanuvaara", "english": "Sunday", "usage_example": "Bhanuvaara rest maadthini."},
]

PHONE_COURTESY: list[SeedEntry] = [
    {"word": "Hello", "english": "Hello (phone greeting)", "usage_example": "Hello, yaaru maathaadhthiddira?"},
    {"word": "Yaaru?", "english": "Who is this?", "usage_example": "Yaaru maathaadhthiddira?"},
    {"word": "Call maadthini", "english": "I'll call", "usage_example": "Nanthara call maadthini."},
    {"word": "Message kalisthini", "english": "I'll send a message", "usage_example": "Nanthara message kalisthini."},
    {"word": "Busy idhini", "english": "I am busy", "usage_example": "Eega busy idhini, nanthara maathaadhona."},
    {"word": "Free aadmele", "english": "After I'm free", "usage_example": "Free aadmele call maadthini."},
    {"word": "Wrong number", "english": "Wrong number", "usage_example": "Sorry, wrong number."},
    {"word": "Network illa", "english": "No network", "usage_example": "Illi network illa, horate hogthini."},
    {"word": "Kshamisi", "english": "Excuse me / Sorry", "usage_example": "Kshamisi, yaaru beku?"},
    {"word": "Thumba thanks", "english": "Thanks a lot", "usage_example": "Thumba thanks, help maadidikke."},
]

# ---------------------------------------------------------------------------
# Ring-structured unit registry
# ---------------------------------------------------------------------------

UNIT_RINGS: dict[str, int] = {
    # Ring 0 — Survival Kit
    "greetings": 0,
    "emergency_toolkit": 0,
    "numbers_money": 0,
    "first_transactions": 0,
    # Ring 1 — Daily Survival
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
                )
                db.add(vocab)
                inserted += 1

        if not dry_run:
            await db.commit()

    logger.info("seed_vocabulary: inserted %d items", inserted)
    return inserted
