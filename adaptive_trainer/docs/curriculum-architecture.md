# Curriculum Architecture

> Source of truth for all curriculum content. Provided by curriculum consultant.

The whole system is organised around three interlocking structures: Rings (what you can do), Units (what you learn), and Atoms (individual teachable items). Everything flows downward from functional competency, not from grammar.

## RINGS: The Progression Ladder

Each ring is defined by a functional milestone — a real-world capability you can test in conversation. The learner's ring determines what the bot prioritises, but content from all completed rings continues to cycle through SRS review.

### Ring 0 — Survival Reflexes (target: 2 weeks, ~40 atoms)

**Milestone**: You can greet someone, say thank you, say you don't understand, ask "how much," and order one item at a shop or restaurant — entirely in Kannada.

**Units**:
1. Greetings & Politeness (namaskara, hegiddira, dhanyavadagalu, shubha dinaprachina, hogi bartini)
2. Emergency Toolkit (gottilla, kannada baralla swalpa swalpa, nidhanavaagi heli, ondh sala heli, help beku)
3. Numbers 1–20 + Money (ondu through ippattu, rupaayi, yeshtu)
4. First Transactions (ondu coffee kodi, bill kodi, illi/alli, beku/beda)

### Ring 1 — Transactional Independence (target: 6 weeks, ~150 atoms cumulative)

**Milestone**: You can navigate an auto ride, order a full meal, buy groceries, ask for directions, and handle basic phone exchanges — without switching to English or Hindi.

**Units**:
5. Transport (auto/cab beku, illi nilsi, mundhe hogi, balakke thirgi, yeshtu door)
6. Food & Ordering (menu kodi, spicy beda, oota aaytha, bill kodi, thumba chennagide)
7. Directions & Places (yelli ide, balakke, yedakke, mundhe, hinde, doora/hattira)
8. Shopping & Prices (idhu yeshtu, tumba jaasthi, swalpa kammi maadi, bere banna idya, bag kodi)
9. Time & Days (indu, naale, ninne, somvaara through shanivara, yeshtu gante)
10. Phone & Basic Courtesy (hello naanu Anish, nimage call maadthini, swalpa late aaguthde, sorry, parvaagilla)

### Ring 2 — Social Conversation (target: 8 weeks, ~400 atoms cumulative)

**Milestone**: You can introduce yourself, talk about your work, ask someone about their family, express preferences and simple opinions, and sustain a 3–5 minute casual exchange.

**Units**:
11. Self-Introduction (naanu, nanna hesaru, naanu Bengaluru-alli iddini, naanu kelsadthini)
12. Family & People (amma, appa, akka/anna/thamm/thangi, maneyalli yaaru idare)
13. Work & Daily Life (kelsa, office, yenu kelsa maadthira, naanu consultant)
14. Likes & Preferences (nanage ishta, nanage ishta illa, thumba chennagi, channagilla)
15. Question Words Deep Dive (yaaru, yaake, yavaga, yelli, hege, yaavudu)
16. Weather & Small Talk (bisi, thandi, mazhe barthide, indu chennagide)
17. Opinions & Feelings (nanage khushi aagide, bejaar aagide, sakkath, kashta)
18. Connectors & Flow (aadre, yaakandre, matthu, athava, adakke, nanthara)

### Ring 3 — Narrative Capability (target: 12 weeks, ~800 atoms cumulative)

**Milestone**: You can tell a story about something that happened, explain a plan, understand the gist of a Kannada conversation between native speakers, and handle unexpected situations.

**Units**:
19. Past Tense Narration (naanu hodhe, naanu noodhe, naanu tindhe, ninne enu aaytu)
20. Future & Plans (naale naanu hogthini, munde enu plan, maadbekanthi iddini)
21. Conditional & Hypothetical (andre, maadidre, bandre, gothidre)
22. Describing Things (dodda, chikka, hosa, halya, bisi, thandi, madhura, khara, mele, kelage)
23. Compound Sentences (…anthi helde, …antha gothidhe, …maadbeku andru)
24. Problem Solving (problem ide, sahaaya beku, doctor beku, phone kalelodhu hogide)
25. Comparison (idhu yavudu chenappaagi, avru nannindha dodda, idhu adu barahella)
26. Storytelling Practice (first…nanthara…koneyli, suddenly, adakke)

### Ring 4 — Expressive Fluency (ongoing, 1000+ atoms)

**Milestone**: You can argue, joke, understand Kannada media, and navigate register differences.

**Units**:
27. Bengaluru Slang & Colloquial (guru, maccha, sakkath, mass, scene, settingsu)
28. Formal Register (thaavu, neevu vs neenu, sarkari Kannada patterns)
29. Idioms & Proverbs (commonly used ones)
30. Media Comprehension (news headlines, film dialogue patterns, song lyrics gist)
31. Humour & Wordplay
32. Cultural Context (festivals, food culture, regional references)

## ATOMS: The Building Blocks

Every teachable item is an "atom" stored with this data:

- **phrase_kannada** (romanised): "ondu coffee kodi"
- **phrase_english**: "one coffee please"
- **unit_id**: 4 (First Transactions)
- **ring**: 0
- **tags**: [food, request, polite]
- **audio_hint**: phonetic guidance or voice note reference
- **usage_context**: "Use at any restaurant or coffee shop. Works for tea too — just swap coffee for chaha."
- **grammar_note** (optional): "kodi = please give (imperative polite). You'll see this verb everywhere."
- **related_atoms**: [yeshtu, beda, beku]

The SRS system tracks per learner: ease_factor, interval, repetitions, next_review_date, times_correct, times_incorrect.

## LESSON LOGIC: How the Bot Generates a Session

When a user types "lesson" (or it's their scheduled time), the bot:

1. Checks the learner's current ring and current unit.
2. Pulls 3–5 NEW atoms from the current unit that haven't been introduced yet.
3. Pulls 2–3 REVIEW atoms that are due in SRS from any previous unit.
4. Generates a lesson that introduces new atoms in context (a mini-scenario), then runs 3–4 exercises mixing new and review items.

Exercise types (cycle through these, never repeat the same type twice in a session):
- **Translate to English**: Bot sends a Kannada phrase, learner replies with meaning.
- **Translate to Kannada**: Bot sends English, learner replies in romanised Kannada.
- **Fill the blank**: A sentence with one word missing.
- **Situational prompt**: "You're in an auto. Tell the driver to stop here." Learner responds freely, bot evaluates.
- **Listen & respond**: Bot sends a voice note, learner replies.
- **Multiple choice**: For early ring items where free recall is too hard.

A unit is "mastered" when all its atoms have ease_factor > 2.0 and interval > 6 days. The bot then moves the learner to the next unit. A ring is "complete" when all its units are mastered, confirmed by a gateway conversation test.

## GATEWAY TESTS

At the end of each ring, the bot runs a roleplay conversation that tests whether the learner can actually do the functional milestone. For Ring 0, it might simulate a shop interaction. For Ring 1, a full auto ride from negotiation to arrival. For Ring 2, a casual "getting to know you" conversation. The bot plays the other person and evaluates fluency, accuracy, and whether the learner needed to fall back to English.

If they pass, the ring counter advances and the daily lesson ratio shifts: 60% new ring, 30% previous ring, 10% older rings.

If they don't pass, the bot identifies which units had breakdowns and increases review frequency on those atoms.

## WHATSAPP-SPECIFIC DESIGN

Each lesson message should be scannable in under 60 seconds. Use WhatsApp formatting: bold for Kannada phrases, plain for English. Voice notes for pronunciation. Images for context-setting (a photo of a menu, a street scene). Stickers or emoji for encouragement (keep affective filter low). The bot should feel like a patient Bengaluru friend texting you, not a classroom.
