# Visit Tigray: Global Destination-Platform Benchmark

Status: research note, v0.1. Access date for every source cited: **2026-11-12** unless stated otherwise.
Scope: the public functionality, UX, information architecture (IA) and innovation of 17 tourism, heritage and travel-commerce platforms, and what they mean for the Visit Tigray modules in `docs/PRODUCT_BLUEPRINT.md`.

---

## 1. Method and limitations

**How pages were examined.** Each page was fetched with the Firecrawl scrape tool. Most fetches used its *query* mode, where a language model answers a structured question ("list the navigation, languages, planner, map, AI assistant, booking…") over the fetched HTML. Some lookups used Firecrawl web search, and only the result excerpts were read. There was no hands-on interactive testing: no logins, no bookings, no chatbot conversations, no app installs.

**Limitations that affect how far the findings can be trusted:**

- **Extraction is not observation.** Query mode summarises the page. It can miss content that loads through JavaScript (several sites reported "navigation not visible" even though they obviously have navigation), and it can misread content. "Not visible" in this document means *not captured*, not *absent*.
- **Some fetches came from cache.** For several pages Firecrawl returned a copy cached between 2026-11-11 and 2026-11-12 (for example visitabudhabi.ae, visitdubai.com, visitsaudi.com, newzealand.com, visiticeland.com, tripadvisor.com and booking.com). All of these are less than 24 hours old.
- **Locale redirects.** Booking.com served its German edition (`index.de.html`). myswitzerland.com and japan.travel redirected to US-English editions.
- **Mostly homepages.** Deeper pages were sampled only where the benchmark needed them: AI assistants, safety, sustainability, permits and heritage.
- **Prior knowledge is labelled.** Statements tagged *[prior knowledge, not re-verified]* come from general background and were not confirmed on 2026-11-12.

**Pages reached** (HTTP 200 unless noted):

| # | Platform | URL(s) actually fetched |
|---|---|---|
| 1 | Visit Ethiopia | https://visitethiopia.et/ (two queries) |
| 2 | Experience Abu Dhabi | https://visitabudhabi.ae/en ; https://visitabudhabi.ae/en/plan-your-trip/essential-info/ask-abu-dhabi |
| 3 | Visit Dubai | https://www.visitdubai.com/en/ |
| 4 | Visit Saudi | https://www.visitsaudi.com/en |
| 5 | Tourism New Zealand | https://www.newzealand.com/int/ ; https://www.newzealand.com/us/feature/tiaki-care-for-new-zealand/ (https://www.newzealand.com/int/tiaki/ returned **404**) |
| 6 | Switzerland Tourism | https://www.myswitzerland.com/en/ (redirected to /en-us/) ; …/planning/about-switzerland/sustainability/ |
| 7 | Visit Iceland + SafeTravel | https://www.visiticeland.com/ ; https://www.visiticeland.com/ask/ ; https://map.visiticeland.com/ (content not extractable) ; https://safetravel.is/ |
| 8 | JNTO | https://www.japan.travel/en/ (redirected to /en/us/) ; https://www.japan.travel/en/safety-tips/ returned **404**; hotline and safety pages seen only as search excerpts (https://www.japan.travel/en/plan/hotline/ , https://www.japan.travel/en/japan-safe-travel-information/) |
| 9 | Visit Rwanda | https://www.visitrwanda.com/ (little extractable) ; https://visitrwanda.com/interests/gorilla-tracking/ (search excerpt) ; https://visitrwandabookings.rdb.rw/rdbportal/mountain-gorilla-tracking (search excerpt) ; https://tourismregulation.rw/en/entities/0/ |
| 10 | National Geographic Travel | https://www.nationalgeographic.com/travel |
| 11 | Google Arts & Culture | https://artsandculture.google.com/ ; https://artsandculture.google.com/search?q=Aksum |
| 12 | Google Maps | Help Center only: https://support.google.com/maps/answer/6291838?hl=en (the map app itself was **not** examined) |
| 13 | Tripadvisor | https://www.tripadvisor.com/ |
| 14 | Airbnb Experiences | https://www.airbnb.com/experiences (prices and ratings only; host and trust content not captured) |
| 15 | GetYourGuide | https://www.getyourguide.com/ |
| 16 | Booking.com | https://www.booking.com/ (served German edition) |
| 17 | UNESCO World Heritage Centre | https://whc.unesco.org/en/list/15 (Aksum) |

All 17 platforms were reached in some form. Coverage was thin for **Google Maps** (help documentation only), **Airbnb Experiences**, **Visit Rwanda's homepage** and **JNTO's safety pages** (excerpts only).

---

## 2. Per-site profiles

Each profile covers only what the cited page supports.

### 2.1 Visit Ethiopia (national peer)
- **Discovery:** featured destinations include Aksum, Adwa and the Adwa Victory Memorial, Al Nejash, "The Historic North and the Simien Mountains", Lalibela, Gondar and Harar. The homepage names a "3-Day Tigray Churches & Gheralta Trekking Tour" and refers to Mekelle and Hawzen. Debre Damo was not mentioned. (visitethiopia.et)
- **Planning and booking:** booking tabs for Hotel, Destinations, Car and Tour, with "Book Now" buttons. Travel tips cover general information, currency and payment, visa requirements and local SIM cards. (visitethiopia.et)
- **Events:** "Upcoming Events & Festivals", including Meskel, Irreecha and the Great Ethiopian Run. (visitethiopia.et)
- **AI:** a "VisitEthiopia assistant" chat widget that greets users with "Selam!" and offers quick-prompt chips such as food and injera, and festivals and culture. No source citations or disclaimers were captured. (visitethiopia.et)
- **Mapping:** outbound Google Maps links on listings. No language switcher, operator directory or B2B area was captured.

### 2.2 Experience Abu Dhabi
- **Planning:** "Build Your Itinerary" opens a "Create Itinerary" form with trip name, duration and activities. A Map link, Visa Info, Transport and Hotels pages, and an app download prompt are also present. (visitabudhabi.ae/en)
- **AI (Ask Abu Dhabi):** described as able to "answer your questions, recommend things to do" and "build you a personalised itinerary". It is labelled beta and warns that responses "may not always reflect real-time information", asking users to double-check opening hours, pricing and event dates. It states that it draws "all its insights from content published across the Experience Abu Dhabi website" and that it "cannot make bookings, process payments or access your personal account". No per-answer citation behaviour was observed. (…/ask-abu-dhabi)
- **Takeaway:** the clearest **scope statement** of any assistant in this set. It says what corpus the assistant uses and what it cannot do.

### 2.3 Visit Dubai
- **Planning:** a "Curate my holiday" entry point, a visa guide, public transport, "Places to stay", "Top 4 things to do this week" and "What's happening now". (visitdubai.com/en)
- **Conversational channel:** a WhatsApp chat link rather than an embedded chatbot. (visitdubai.com/en)
- **Commerce:** "Buy now" for Dubai Pass. Mapping is done through outbound Google Maps route links.

### 2.4 Visit Saudi
- **Discovery:** a seasonal campaign ("Plan Your Winter Experience", "What's On This Winter") with dated events and ticket links. (visitsaudi.com/en)
- **Mapping:** an Esri-powered destination map. (visitsaudi.com/en)
- **Accessibility:** an on-page toolbar with larger and smaller text, invert, grayscale, underlined links, speech-to-text, a reading guide, reduced motion, a big cursor and a reset option. This was the most extensive accessibility toolbar captured in the set. (visitsaudi.com/en)
- **Practical information:** "Know Before You Go" with visa regulations, a travel guide and getting around.

### 2.5 Tourism New Zealand
- **AI:** "ASK OUR AI", powered by the third-party GuideGeek, with linked privacy policy and contextual prompts on the Tiaki page ("What is the Tiaki Promise?"). No accuracy disclaimer was captured on that page. (newzealand.com/int/ ; …/tiaki-care-for-new-zealand/)
- **Planning and commerce:** "Great itineraries", a travel guide, packaged holidays, and flight search with partner airlines. (newzealand.com/int/)
- **Cultural framing:** the Tiaki Promise commits visitors to "care for land, sea and nature", "travel safely" and "respect the culture and local communities". It uses te reo Māori concepts in context, such as *taonga* and *tangata whenua*. (…/tiaki-care-for-new-zealand/)
- **Editions:** International and United States English editions. The page carries a `googlebot: noindex` on /int/, so market editions are managed deliberately.
- *[prior knowledge, not re-verified]:* Qualmark is New Zealand's official quality assurance mark for operators, and Tiaki is backed jointly by government and industry.

### 2.6 Switzerland Tourism
- **Journeys:** the "Grand Tour of Switzerland" and the "Grand Train Tour of Switzerland" as signature routes. (myswitzerland.com/en-us/)
- **Live operational data:** a "Snow and piste report" with "Daily updated information on 250 winter sports stations". (myswitzerland.com/en-us/)
- **Sustainability label:** Swisstainable has three levels: I *committed*, II *engaged* and III *leading*, with III externally verified. The page says plainly that Swisstainable is a programme, "not an independent certification". Hotel and restaurant listings can be filtered by `swisstainable-level1/2/3`. (…/sustainability/)
- **Accessibility honesty:** an explicit screen-reader notice that a section relies on video and mouse interaction and "is therefore not very accessible to screen readers". (myswitzerland.com/en-us/)

### 2.7 Visit Iceland and SafeTravel
- **IA:** the most complete planning taxonomy captured. It covers Safetravel, visa, geography, northern lights, volcanic eruptions, the "Iceland Academy", regions, scenic routes, national parks, trip suggestions, sustainable travel, LGBTQ+ travel and events. (visiticeland.com)
- **Mapping:** "Map your journey" at map.visiticeland.com, whose meta description says users can "plan your trip from A-Ö, fill it with things to do, and create an itinerary to share". The map interface itself was not extractable. A 3D topographic map is also linked. (visiticeland.com ; map.visiticeland.com)
- **AI (Ask Iceland):** suggested questions include "Is it safe to drive in Iceland in winter?". Its disclaimer reads "in beta and may make mistakes. Check current weather, road conditions and opening hours". Users are told conversations are stored and warned "don't include personal details". No source citations and no named provider were captured. (visiticeland.com/ask/)
- **SafeTravel integration:** the tourism site links Safetravel prominently in its main navigation. safetravel.is is run by ICE-SAR, the Icelandic Association for Search and Rescue. It offers "Submit a travel plan", a "Check Conditions" travel-conditions map, the 112 emergency number, and an app that sends GPS location to 112. The alert format was not captured. (safetravel.is)
- **Takeaway:** the safety authority is a **separate, authoritative operator**, and the tourism site defers to it rather than restating it.

### 2.8 Japan National Tourism Organization (japan.travel)
- **Languages:** 25+ language and market editions, including Arabic, Thai, Vietnamese, Bahasa Indonesia, Simplified and Traditional Chinese, and several English market editions. (japan.travel/en/)
- **Inclusive planning:** Accessible Tourism and Traveling With a Disability, a Vegetarian and Vegan Guide, Muslim Travelers guidance, and Wi-Fi and Connectivity. (japan.travel/en/)
- **Safety:** Safety Tips, Japan Safe Travel Information, a "Guide for when you are feeling ill", and the Japan Visitor Hotline, which runs "24 hours a day, 365 days a year". The hotline was seen as a search excerpt. (japan.travel/en/ ; japan.travel/en/plan/hotline/)
- **B2B:** Trade, Trade Newsletter and Tender Notice links. (japan.travel/en/)

### 2.9 Visit Rwanda
- **Community benefit messaging:** states that ten percent of permit and park-fee income is spent in partnership with local communities. (visitrwanda.com)
- **Scarce-permit handling:** "only 96 permits available each day"; a permit costs US $1,500; the minimum age is 15. Booking goes through the government Irembo or RDB portals or a reputable operator. (visitrwanda.com/interests/gorilla-tracking/, search excerpt). The RDB booking portal shows tiered fees: Foreigner $1,500, African citizen or resident $500, Rwandan or EAC citizen $200. (visitrwandabookings.rdb.rw, search excerpt)
- **Verified provider registry:** the gorilla page links "Tour Operators & Guides" to tourismregulation.rw. That registry is operated by RDB's Hospitality Quality Department. It covers restaurants and bars, accommodation, and tour operators, travel agents and guides. Each listing shows **license status** (for example *Licensed* or *Cancelled*), category, sub-category, province and district, and the registry is searchable. (tourismregulation.rw/en/entities/0/)
- **Takeaway:** this is the closest real-world analogue to Visit Tigray's verified provider directory. The **license-state** model comes from the regulator and is not a marketing badge.

### 2.10 National Geographic Travel
- **Storytelling:** sections include Best of the World, Destination Guides and National Geographic Traveller (UK), with slideshows and photo-led articles. (nationalgeographic.com/travel)
- **Commerce:** a "Book a Trip" link to National Geographic Expeditions. No AI features were captured, and bylines were not captured on the index page.

### 2.11 Google Arts & Culture
- **Formats:** stories, collections, Street View, zoomable images, 3D, games, pocket galleries and virtual tours. The tabs are Home, Explore, Play, Nearby, Favorites and The Lab. AI experiments appear in the Lab. (artsandculture.google.com)
- **Attribution model:** content is presented under named partner institutions. The meta description cites "over 2000 leading museums and archives".
- **Aksum search:** results included "Obelisk of Aksum, Rome", "Coin of King Joel", "Nine Saints" items, a Smithsonian National Museum of African Art story on Ethiopia, and Italian-language items, including a photograph titled for Marshal Badoglio's visit to the Axum air base. (artsandculture.google.com/search?q=Aksum)
- **Takeaway:** Tigray heritage is represented online mostly through **external institutions' collections**, and partly through colonial-era framing. This is a provenance and interpretation issue Visit Tigray should address directly (§5).

### 2.12 Google Maps (help documentation only)
- **Offline maps:** users download a chosen area. Offline, **only driving directions** work, and only when the whole route is inside the downloaded area. Transit, cycling and walking directions are unavailable offline. Maps expire, and the app tries to auto-update them over Wi-Fi when 15 days or fewer remain. Downloads can go to an SD card on Android 6+. Offline download is unavailable in some regions "because of contractual limitations, language support, address formats, or other reasons". (support.google.com/maps/answer/6291838)
- **Takeaway:** a global offline map leaves gaps on exactly the walking and trail routes that Tigray's cliff churches require.

### 2.13 Tripadvisor
- **Discovery:** "Find things to do by interest" (Outdoors, Food, Culture, Water) and an "Ask AISearch" entry. (tripadvisor.com)
- **Reputation:** bubble ratings with review counts, and the "Travelers' Choice Awards Best of the Best" badges. (tripadvisor.com)
- *[prior knowledge, not re-verified]:* forums, owner-response tools and Trips (saved itineraries).

### 2.14 Airbnb Experiences
- **Discovery:** categories such as Arts & culture, Outdoors, Mountains and Beach. Listings show "From $X / guest" pricing and two-decimal average ratings. (airbnb.com/experiences)
- Host credentials, filters and trust statements were **not captured**.

### 2.15 GetYourGuide
- **Reassurance:** "free cancellations on most activities, the option to pay later, and 24/7 support". (getyourguide.com)
- **Urgency cue:** "Likely to sell out". (getyourguide.com)
- **Localisation:** 40+ languages including Arabic and Hebrew (right-to-left), and 35+ currencies.

### 2.16 Booking.com (German edition)
- **Search:** a natural-language search field, "Mit Ihren eigenen Worten suchen" ("search in your own words"), alongside date and party pickers. (booking.com)
- **Loyalty and urgency:** Genius membership at "mind. 10%" off participating properties, and sale and deadline framing such as "Größter Sale des Jahres" and "Bis 7. Januar 2027 buchen". (booking.com)
- No sustainability badge or list-your-property link was captured on this fetch.

### 2.17 UNESCO World Heritage Centre (Aksum, property 15)
- **IA:** tabs for Description, Maps, Documents, Gallery, Video, Indicators and Assistance, in eight languages. Criteria (i) and (iv). The description is licensed **CC-BY-SA IGO 3.0**. (whc.unesco.org/en/list/15)
- **Candid conservation text:** small modern houses obscuring underground Aksumite structures, a new museum in the main Stelae Field with "highly negative visual impact", flooding in the Tomb of the Brick Arches, and vulnerability through lack of documentation, boundary and management plan. (whc.unesco.org/en/list/15)
- *[prior knowledge, not re-verified]:* Aksum was inscribed in 1980.

---

## 3. Comparison matrix

Legend: **●** observed on the cited page · **◐** partial, or seen only as a search excerpt · **○** not captured (which does not prove absence) · **n/a** not applicable.

| Platform | Discovery IA | Trip planning | Storytelling | Mapping | AI assistant | Personalisation | Accessibility | Mobile / offline | Community / UGC | Ops / B2B / regulation | Safety / advisory |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Visit Ethiopia | ● destinations, events | ● booking tabs | ○ | ◐ outbound Google links | ● chat widget, no citations seen | ○ | ○ | ○ | ○ | ○ | ◐ visa / SIM tips |
| Experience Abu Dhabi | ● | ● itinerary builder | ○ | ● map link | ● scoped corpus, beta disclaimer, no booking | ● "personalised itinerary" | ○ | ● app | ○ | ○ | ◐ visa info |
| Visit Dubai | ● "this week" | ● "Curate my holiday" | ○ | ◐ outbound routes | ◐ WhatsApp channel | ◐ | ○ | ○ | ○ | ○ | ◐ visa guide |
| Visit Saudi | ● seasonal | ● packages | ○ | ● Esri map | ○ | ○ | ● extensive toolbar | ○ | ○ | ○ | ◐ |
| New Zealand | ● | ● itineraries, packages | ● Tiaki, Māori framing | ○ | ● third-party (GuideGeek) | ○ | ○ | ○ | ○ | ◐ | ○ |
| Switzerland | ● | ● Grand Tour | ● | ○ | ○ | ○ | ● honest screen-reader notice | ○ | ○ | ● Swisstainable levels and filters | ● snow/piste data |
| Iceland + SafeTravel | ● richest taxonomy | ● map-based planner | ● | ● planning map | ● beta, privacy warning | ○ | ○ | ● SafeTravel app → 112 | ○ | ○ | ● separate authority, travel plans |
| JNTO | ● | ● | ○ | ● regional maps | ○ | ○ | ● accessible tourism | ● Wi-Fi guide | ○ | ● trade, tenders | ● 24/7 hotline |
| Visit Rwanda | ◐ | ● permits via Irembo / RDB | ◐ | ○ | ○ | ○ | ○ | ○ | ○ | ● license-status registry | ○ |
| NatGeo Travel | ● | ○ | ● long-form, photo | ○ | ○ | ○ | ○ | ○ | ○ | ◐ expeditions sales | ○ |
| Google Arts & Culture | ● | n/a | ● stories, 3D, Street View | ● Nearby | ● Lab experiments | ● Favorites | ○ | ○ | ○ | ● institutional partners | n/a |
| Google Maps | n/a | ◐ | ○ | ● | ○ | ○ | ○ | ● offline (driving only) | ○ (prior: reviews) | ○ | ○ |
| Tripadvisor | ● interests | ◐ | ○ | ○ | ● "AISearch" | ○ | ○ | ○ | ● reviews, awards | ○ | ○ |
| Airbnb Experiences | ● categories | ○ | ○ | ○ | ○ | ○ | ○ | ○ | ● ratings | ○ | ○ |
| GetYourGuide | ● | ○ | ○ | ○ | ○ | ○ | ○ | ○ | ● ratings | ○ | ○ |
| Booking.com | ● | ○ | ○ | ○ | ● natural-language search | ● Genius | ○ | ○ | ○ | ○ | ○ |
| UNESCO WHC | ● | n/a | ● | ● Maps tab | ○ | ○ | ○ | ○ | ○ | ● Indicators, SOC | ● conservation threats |

---

## 4. Patterns worth adopting

1. **A scope statement for the AI assistant.** *Exemplar: Experience Abu Dhabi.* State publicly which corpus the assistant uses, that it is beta, and what it cannot do (no bookings, no payments, no account access). Visit Tigray should add **per-answer citations**, which none of the assistants observed (Abu Dhabi, Iceland, New Zealand, Ethiopia) were seen to provide.
2. **Privacy warnings at the point of input.** *Exemplar: Ask Iceland.* Its "don't include personal details" notice, together with a disclosure that conversations are stored, is short and honest.
3. **An external safety authority, linked prominently.** *Exemplar: Visit Iceland → SafeTravel (ICE-SAR).* The tourism site defers to the rescue authority for conditions, travel-plan filing and emergency contact, and does not author safety content itself.
4. **A regulator-backed provider registry with license states.** *Exemplar: Rwanda's tourismregulation.rw.* It shows *Licensed* and *Cancelled* status by province and district, and the tourism site links to it from the point of decision (the permit page).
5. **Tiered, honestly described quality labels with filters.** *Exemplar: Swisstainable levels I–III.* The site openly states that the programme "is not an independent certification", and listings can be filtered by level.
6. **Inclusive-needs planning content.** *Exemplar: JNTO.* It covers accessible tourism, dietary and faith needs, connectivity, and a 24/7 visitor hotline.
7. **Honest accessibility notices.** *Exemplars: Switzerland's screen-reader notice and Saudi's accessibility toolbar.* Visit Tigray should prefer fixing components to WCAG 2.2 AA over overlay toolbars, but adopt the honesty of saying when an element is not yet accessible.
8. **Responsible-travel promise in the local language.** *Exemplar: New Zealand's Tiaki.* It frames visitor conduct through Indigenous concepts used in context. A Tigrinya-framed visitor promise, written with custodians, is a direct analogue.
9. **Signature journeys.** *Exemplars: Grand Tour of Switzerland, Iceland scenic routes.* Named, curated routes give the deterministic planner sensible starting templates.
10. **Transparent tiered pricing for scarce permits.** *Exemplar: Rwanda RDB.* A published resident, regional and foreign fee table, plus a daily cap, is a fair model for capacity-limited church or site visits if the Bureau ever introduces them.
11. **Heritage records that state threats candidly.** *Exemplar: UNESCO Aksum.* An open-licence description, documents and indicators, and frank conservation-threat language. Visit Tigray heritage pages should link to the authoritative UNESCO record and respect its CC-BY-SA IGO 3.0 terms when quoting.
12. **Clear institution-level attribution.** *Exemplar: Google Arts & Culture.* Every item is presented under a named partner institution.

---

## 5. Gaps and opportunities where Visit Tigray can exceed the benchmark

**5.1 Regional intelligence.** The national site (visitethiopia.et) treats Tigray as one tour product and one part of "The Historic North". Visit Tigray can model the region at sub-zone granularity: Central, Eastern (Gheralta, Hawzen), Southern, North-Western and Mekelle. It can also carry church-cluster access notes, seasonal feasibility and custodian contact pathways. None of the national sites examined exposes this depth for a sub-region.

**5.2 Cultural authenticity and custodial consent.** None of the platforms examined showed a visible mechanism for **custodial approval** of how sacred sites are described or photographed. Google Arts & Culture attributes items to institutions, but its Aksum results include externally held objects and colonial-era imagery with no visible community voice. Visit Tigray can make custodial approval a first-class, auditable state, using `custodial_approvals` and the revocation workflows in the blueprint. Each heritage page could carry a visible badge: "Description reviewed by [custodial body] on [date]".

**5.3 Tigrinya / Ge'ez-script support.** JNTO offers 25+ editions and GetYourGuide 40+ languages. Neither offers Tigrinya, and none of the 17 platforms examined showed Tigrinya or Ge'ez script support. That none offers Tigrinya is an inference from the language lists captured; the lists were not exhaustive for every site. Opportunity:
- Tigrinya as a primary authored language, not a machine-translated afterthought.
- Ethiopic-capable fonts subset for low bandwidth.
- Ge'ez numerals where culturally expected.
- Ethiopian-calendar dates for festivals (Meskel, Timket and Ashenda) shown alongside Gregorian dates.
- Transliteration-tolerant search (Aksum, Axum and አክሱም resolve to the same place).
- Tigrinya pronunciation audio.

**5.4 Offline operation in low-connectivity settings.** Google Maps offline supports **driving only** and is unavailable in some regions. Iceland's SafeTravel relies on the app reaching 112. Visit Tigray's offline-first PWA can pre-cache region packs containing heritage text, citations, walking and trail approach notes, custodian etiquette, emergency contacts and the user's itinerary. Each pack carries an explicit **"last verified" timestamp**. When the device is offline, the AI guide should fall back to retrieval-only answers from the cached, cited corpus rather than generation.

**5.5 Heritage stewardship.**
- *Source provenance:* every historical claim links to a dated `source_documents` record (blueprint §5). No assistant observed did this.
- *Contested-history attribution:* where scholarly or community accounts differ (dating, the Nine Saints traditions, Aksumite chronology), present the competing accounts side by side, each with its attribution, and do not merge them into one narrative. UNESCO's candid threat language is a model for tone.
- *Sensitive-site coordinate protection:* no public platform examined showed coordinate generalisation for sensitive sites. Visit Tigray should store precise coordinates privately and publish generalised ones (for example a 1–5 km grid or "near Hawzen") for restricted churches, manuscript repositories and fragile rock art. Precise directions should be released only through a licensed guide or custodian.

**5.6 Honest travel-advisory handling.** Abu Dhabi and Iceland tell users to "double-check" but give no structured advisory state. Visit Tigray can:
- display a dated advisory banner per destination, with source attribution (Bureau, national authority, or embassy advisories linked rather than paraphrased);
- show **"not verified"** whenever feeds are stale (blueprint §5);
- never let the AI guide or planner assert that a site is "safe" or "open".

The incident manager can hide a location within minutes (blueprint §7). This is a capability none of the benchmarked sites publicly demonstrates.

---

## 6. Things to explicitly NOT copy

1. **Proprietary design systems and brand assets.** Logos, typefaces, campaign layouts and taglines (such as "100% Pure New Zealand") and named programmes (Tiaki, Swisstainable, Genius, Travelers' Choice) are trademarks. Adopt the *pattern*, not the name or look.
2. **Copyrighted media.** Do not reuse photos, video, map tiles or Google Arts & Culture images. Partner-institution items carry their own rights. UNESCO text may be reused only under CC-BY-SA IGO 3.0 with attribution and share-alike. Images on UNESCO pages are not covered by that licence by default *[prior knowledge, not re-verified]*.
3. **Restricted data.** Do not scrape Tripadvisor, Booking.com, Airbnb or GetYourGuide listings or reviews. Do not cache Google Maps tiles or Places content outside Google's terms. Firecrawl flagged a Booking.com data provider, but using it would not make the data rights-cleared for redistribution.
4. **Dark patterns.** Avoid scarcity and urgency cues ("Likely to sell out" on GetYourGuide), countdown sale framing ("Biggest sale of the year", "book by" deadlines on Booking.com) and loyalty-gated price signalling. Rwanda's "96 permits per day" is a **true capacity fact** stated plainly. Visit Tigray should show capacity only when it is real and verified.
5. **Unverifiable AI claims.** Do not market the guide as "knows everything" or "personalised" beyond what is implemented. Do not hand the assistant to an opaque third party without disclosing it; New Zealand's GuideGeek is at least named. Do not present AI output without citations or a beta and limitations notice.
6. **Overlay-only accessibility.** An accessibility toolbar (as on Visit Saudi) does not replace accessible components. Visit Tigray should meet WCAG 2.2 AA natively.
7. **Mixing rating systems with awards.** Tripadvisor's review-derived awards mix popularity with endorsement. Visit Tigray's photography awards must stay jury-judged under the blueprint §6 policy gate, separate from any rating.
8. **Outsourcing heritage voice.** Do not reproduce externally held or colonial-era framings of Aksum as the default narrative (see §2.11). Cite them as sources, with context.

---

## 7. Prioritised recommendations by module

Priority: **P0** before public launch · **P1** first release after launch · **P2** later.

| # | Pri | Module (blueprint domain) | Recommendation | Benchmark basis |
|---|---|---|---|---|
| 1 | P0 | Cultural AI concierge (2) | Publish an "About the guide" scope page covering corpus, beta status, what it cannot do, data retention, and "don't share personal details". Every answer shows inline citations to dated source records. Offline, answers are retrieval-only. Advisory and opening-hours questions are refused or deferred, with a link to the source. | Abu Dhabi, Iceland (exceed with citations) |
| 2 | P0 | Heritage archive (4) / Bureau Studio (10) | Store coordinates at two precisions, private and public. Gate precise ones behind custodial approval and licensed-guide roles, and log access. Show a "custodian-reviewed" badge with date. Provide a revocation workflow. | Gap in all 17 |
| 3 | P0 | Discovery (1) / Bureau Studio (10) | Advisory system: a dated banner per destination, with source attribution and a stale-feed "not verified" state. A link-out to official national and emergency authorities, SafeTravel-style, instead of paraphrasing them. A one-click location hide. | Iceland/SafeTravel, JNTO hotline |
| 4 | P0 | Platform i18n (1, 2, 10) | Tigrinya-first authoring workflow. Ethiopic font subsetting. Ethiopian and Gregorian dual calendar for events. Transliteration-tolerant search (Aksum/Axum/አክሱም). Tigrinya pronunciation audio. | JNTO/GYG breadth, no Tigrinya observed |
| 5 | P0 | Supplier marketplace (8) | A verified provider directory with explicit license state (Licensed, Suspended, Cancelled, Pending), zone and district, verification date and issuing authority. Status changes are audited. No paid placement in ranking. | Rwanda tourismregulation.rw |
| 6 | P1 | Offline PWA (cross-cutting) | Downloadable region packs (text, citations, walking-approach notes, etiquette, emergency contacts, saved itinerary) with "last verified" stamps and expiry and refresh rules. Cover walking routes, which Google Maps offline does not. | Google Maps offline limits |
| 7 | P1 | Intelligent planner (3) | Seed the planner with named signature journeys (for example a Gheralta church circuit and an Aksum–Yeha heritage route). Inclusive-needs inputs covering mobility, climbing ability for cliff churches, dietary needs and fasting periods. The deterministic validator flags unverified stops. | Grand Tour, Iceland routes, JNTO inclusive content |
| 8 | P1 | Heritage archive (4) | Show contested or alternative accounts side by side, each with its attribution. Link to the UNESCO record and to Indicators and state-of-conservation documents. Quote UNESCO text only under CC-BY-SA IGO 3.0. | UNESCO WHC |
| 9 | P1 | Discovery (1) / Governance (7) | A Tigrinya-framed responsible-visitor promise, co-written with custodians, covering dress, photography consent, fasting days and sacred-object handling. Surface it before itinerary export. | NZ Tiaki |
| 10 | P1 | Supplier marketplace (8) | A tiered quality or sustainability label that states what it is and is not, with external verification only at the top tier and a filter in the directory. | Swisstainable |
| 11 | P1 | Accessibility (cross-cutting) | Meet WCAG 2.2 AA natively. Add honest per-component notices where a feature (for example a 3D or virtual-travel exhibit) is not yet accessible, and keep a 2D or text fallback. | Switzerland notice, Saudi toolbar |
| 12 | P2 | Visitor memories (6) / Memory awards (7) | Keep community stories and photo awards jury-led and separate from ratings. Show rights declarations and maker credit on every published image. Give stories no urgency or vote-farming mechanics. | Contrast with Tripadvisor awards |
| 13 | P2 | Virtual travel (5) | Use curator-led stories credited to Tigrayan institutions and custodians, in a format like Google Arts & Culture stories, with download permissions per asset. | Google Arts & Culture |
| 14 | P2 | Bookings (9) | If permits or capacity-limited visits are introduced, publish a transparent resident, regional and foreign fee table and true daily caps, with no scarcity theatre. Stay behind the blueprint's legal feature gate. | Rwanda RDB |
| 15 | P2 | Bureau Studio (10) / Interoperability (12) | A trade and partner area (operator onboarding, data feeds, tenders) like JNTO's Trade section. Visit Ethiopia feeds only with permission. | JNTO, blueprint §12 |

**Top five, in order:** (1) a cited, scope-disclosed AI guide that is retrieval-only offline; (2) two-precision coordinates with custodial approval and revocation; (3) a dated, source-attributed advisory system with "not verified" states and SafeTravel-style deferral to authorities; (4) Tigrinya-first i18n with Ge'ez script, dual calendars and transliteration-tolerant search; (5) a regulator-style verified provider directory with explicit license states.
