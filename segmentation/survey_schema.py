"""Questions and answer options of the tourist behaviour survey, exactly as they appear in the Google Form.

The response spreadsheet uses these strings as column names and cell values, so every other
module reads them from here rather than repeating them.
"""

# ---- Answer options ----
CONSENT = "I am 18 or older, I have read the information above, and I agree to take part"
AGES = ["18–24", "25–34", "35–45", "46–60", "Over 60"]
RESIDENT, VISITOR, DIASPORA = (
    "I live in Sri Lanka and travel within the country",
    "I live overseas and visited Sri Lanka as a tourist",
    "I am a Sri Lankan living overseas and visited on holiday",
)
COUNTRIES = {
    "India": 20, "Russia": 10, "United Kingdom": 10, "Germany": 8, "China": 6, "France": 6,
    "Australia": 5, "Netherlands": 3, "United States": 4, "Bangladesh": 2, "Maldives": 2,
    "Canada": 3, "Italy": 2, "Poland": 2, "Spain": 2, "Switzerland": 2, "Japan": 2, "Israel": 1,
    "Ukraine": 1, "Other country in Asia": 3, "Other country in Europe": 4,
    "Other country in the Middle East": 1, "Other country in Africa": 0.3,
    "Other country in the Americas": 0.5, "Other country in Oceania": 0.5,
}
DIASPORA_COUNTRIES = {"United Kingdom": 4, "Australia": 4, "Canada": 3, "United States": 2,
                      "Italy": 2, "Other country in the Middle East": 3, "Germany": 1}
AGO = ["Within the last 3 months", "3–6 months ago", "6–12 months ago", "1–2 years ago"]
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August",
          "September", "October", "November", "December"]
WITH = ["Alone", "Partner or spouse", "Family with children", "Family (adults only)",
        "Friends", "Organised tour group", "Colleagues"]
PURPOSE = ["Holiday / leisure", "Visiting friends or relatives", "Religious visit or pilgrimage",
           "Health, wellness or Ayurveda", "Business combined with leisure",
           "Sport or adventure event", "Education or study tour"]
ARRANGED = ["I planned and booked everything myself",
            "I booked some parts through a travel agent or tour operator",
            "It was a full package tour",
            "Someone else (family, friends, employer) arranged it"]
SPEND = ["Under LKR 5,000 (about USD 17)", "LKR 5,000 – 10,000 (about USD 17 – 33)",
         "LKR 10,000 – 20,000 (about USD 33 – 67)", "LKR 20,000 – 40,000 (about USD 67 – 133)",
         "LKR 40,000 – 75,000 (about USD 133 – 250)", "Over LKR 75,000 (about USD 250)"]
SPLIT_ROWS = ["Accommodation", "Food and drink", "Transport within Sri Lanka",
              "Activities, tours and entrance fees", "Shopping and souvenirs"]
SPLIT_COLS = ["Little or none", "Some", "A large part"]
STAY = ["Luxury hotel or resort (4–5 star)", "Mid-range hotel", "Budget guesthouse or hostel",
        "Homestay", "Private villa, apartment or Airbnb", "Eco-lodge, camping or glamping",
        "With friends or family", "I did not stay overnight (day trip)"]
DISTRICTS = [
    "Ampara (Arugam Bay, Pottuvil)", "Anuradhapura", "Badulla (Ella, Haputale)",
    "Batticaloa (Pasikudah)", "Colombo", "Galle (Galle, Unawatuna, Hikkaduwa, Bentota)",
    "Gampaha (Negombo)", "Hambantota (Tangalle, Tissamaharama, Yala)", "Jaffna",
    "Kalutara (Kalutara, Beruwala)", "Kandy", "Kegalle (Pinnawala, Kitulgala)", "Kilinochchi",
    "Kurunegala", "Mannar", "Matale (Sigiriya, Dambulla)", "Matara (Mirissa, Weligama)",
    "Monaragala (Wellawaya)", "Mullaitivu", "Nuwara Eliya (Nuwara Eliya, Hatton, Horton Plains)",
    "Polonnaruwa (Polonnaruwa, Minneriya)", "Puttalam (Kalpitiya, Chilaw)",
    "Ratnapura (Sinharaja, Udawalawe)", "Trincomalee (Trincomalee, Nilaveli)", "Vavuniya",
]
D = {label.split(" (")[0]: label for label in DISTRICTS}
TRANSPORT = ["Private car or van with a driver", "Own or rented car (self-drive)",
             "Tour coach or group bus", "Train", "Public bus", "Tuk-tuk", "Motorbike or scooter",
             "Taxi or ride-hailing app (PickMe, Uber)", "Domestic flight"]
ACTIVITIES = ["Relaxing at the beach", "Surfing, diving, snorkelling or other water sports",
              "Wildlife safari or national park visit", "Whale or dolphin watching",
              "Hiking or trekking", "Ancient cities, forts and heritage sites",
              "Temples and religious sites", "Tea plantations or a scenic train journey",
              "Local food, cooking classes or food tours", "Ayurveda, spa, yoga or meditation",
              "Nightlife, bars or live entertainment", "Shopping", "Festivals or cultural events",
              "Village visits or community-based tourism", "Sightseeing and photography"]
STYLE = ["Culture and heritage", "Nature, wildlife and eco-tourism",
         "Adventure and outdoor activities", "Beach and relaxation", "Wellness and retreat",
         "A mix – no single style"]
IMPORTANCE = ["Keeping costs low", "Comfort and luxury", "Avoiding crowded places",
              "Protecting the environment", "Authentic local experiences",
              "Seeing as many places as possible", "Safety and security",
              "Easy and convenient transport"]
LEAD = ["Less than a week", "1–4 weeks", "1–3 months", "More than 3 months"]
SOURCES = ["Friends or family", "Social media (Instagram, TikTok, Facebook)",
           "YouTube or travel blogs", "Review sites (TripAdvisor, Google Maps reviews)",
           "Booking sites (Booking.com, Agoda, Airbnb)", "Travel agent or tour operator",
           "Guidebooks", "AI assistants or chatbots", "I did not plan – I decided as I went"]
FREQUENCY = ["This was my first", "Less than once a year", "About once a year",
             "2–3 times a year", "4 or more times a year"]
SEASONS = ["December – March", "April – June", "July – September", "October – November",
           "No preference"]
DECIDES = ["Weather", "School or work holidays", "Lower prices and fewer crowds",
           "Festivals or events", "Whenever an opportunity comes up"]

# ---- Question titles used as spreadsheet column names ----
Q_DAYS = "How many days did the trip last?"
Q_GROUP = "How many people travelled together, including you?"
Q_SPEND = "About how much did you spend per person, per day?"
Q_DISTRICTS = "Which districts did you visit on this trip?"
Q_STOPS = "In how many different towns or areas did you stay overnight?"
Q_TRANSPORT = "How did you travel between places?"
Q_ACTIVITIES = "Which of these did you do on this trip?"
Q_LEAD = "How far ahead did you plan this trip?"
Q_FREQUENCY = "How often do you take leisure trips within Sri Lanka?"
Q_SPLIT = "How much of your spending went on each of these? [{}]"
Q_IMPORTANCE = "How important was each of these when you planned and took the trip? [{}]"
Q_AGE = "Which age group are you in?"
Q_COUNTRY = "Which country do you live in?"
Q_DESCRIBES = "Which best describes you?"
Q_STYLE = "Which one best describes the style of this trip?"
