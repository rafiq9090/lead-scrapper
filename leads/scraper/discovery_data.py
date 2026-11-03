"""Discovery reference tables: countries, locations, niches and exclusions."""

# Directories, scrapers, aggregators, and search engines to filter out (ensures 100% real businesses)
IGNORED_DOMAINS = {
    # Big Tech & Search
    "google.com", "yahoo.com", "bing.com", "duckduckgo.com", "apple.com", "microsoft.com",
    "wikipedia.org", "wikimedia.org", "schema.org", "w3.org", "mozilla.org", "github.com",
    "play.google.com",
    # Directories & Aggregators
    "yelp.com", "yellowpages.com", "tripadvisor.com", "mapquest.com", "angi.com", "bbb.org",
    "clutch.co", "crunchbase.com", "glassdoor.com", "indeed.com", "reddit.com", "pinterest.com",
    "amazon.com", "ebay.com", "houzz.com", "upwork.com", "fiverr.com", "zoominfo.com", "dnb.com",
    "manta.com", "f6s.com", "goodfirms.co", "themanifest.com", "g2.com", "capterra.com",
    "softwareadvice.com", "trustpilot.com", "expertise.com", "topdevelopers.co", "builtin.com",
    "owler.com", "superpages.com", "citysearch.com", "threebestrated.com", "localdatabase.com",
    "chamberofcommerce.com", "usnews.com", "forbes.com", "poidata.io", "curemeabroad.com",
    "dentistregister.co.uk", "bookimed.com", "gcr.org", "alldentists.co.uk", "bestdentalhospitals.com",
    "expatfocus.com", "dentaly.org", "whatclinic.com", "datagemba.com", "clinicguides.com",
    "topdoctors.co.uk", "londonjourney.co.uk", "yourlocal.guide", "nhs.uk",
    # Medical, Dental & Healthcare Aggregators
    "zocdoc.com", "webmd.com", "healthgrades.com", "vitals.com", "on-mend.com", "ratemds.com",
    "healthline.com", "1800dentist.com", "dentalplans.com", "opencare.com", "ada.org",
    # Social Media
    "facebook.com", "instagram.com", "linkedin.com", "twitter.com", "x.com", "youtube.com", "tiktok.com"
}

COUNTRY_CODES = {
    # North America
    "united states": "us", "usa": "us", "us": "us",
    "canada": "ca", "ca": "ca",
    "mexico": "mx", "mx": "mx",

    # Europe
    "united kingdom": "gb", "uk": "gb", "gb": "gb", "great britain": "gb",
    "germany": "de", "de": "de",
    "france": "fr", "fr": "fr",
    "netherlands": "nl", "nl": "nl", "holland": "nl",
    "ireland": "ie", "ie": "ie",
    "spain": "es", "es": "es",
    "italy": "it", "it": "it",
    "switzerland": "ch", "ch": "ch",
    "sweden": "se", "se": "se",
    "norway": "no", "no": "no",
    "denmark": "dk", "dk": "dk",
    "finland": "fi", "fi": "fi",
    "belgium": "be", "be": "be",
    "austria": "at", "at": "at",
    "poland": "pl", "pl": "pl",
    "portugal": "pt", "pt": "pt",
    "greece": "gr", "gr": "gr",
    "czech republic": "cz", "czechia": "cz", "cz": "cz",
    "romania": "ro", "ro": "ro",
    "hungary": "hu", "hu": "hu",

    # Asia & Pacific
    "australia": "au", "au": "au",
    "new zealand": "nz", "nz": "nz",
    "singapore": "sg", "sg": "sg",
    "japan": "jp", "jp": "jp",
    "south korea": "kr", "korea": "kr", "kr": "kr",
    "india": "in", "in": "in",
    "bangladesh": "bd", "bd": "bd",
    "pakistan": "pk", "pk": "pk",
    "malaysia": "my", "my": "my",
    "indonesia": "id", "id": "id",
    "philippines": "ph", "ph": "ph",
    "thailand": "th", "th": "th",
    "vietnam": "vn", "vn": "vn",
    "hong kong": "hk", "hk": "hk",
    "taiwan": "tw", "tw": "tw",

    # Middle East
    "united arab emirates": "ae", "uae": "ae", "ae": "ae",
    "saudi arabia": "sa", "sa": "sa", "ksa": "sa",
    "qatar": "qa", "qa": "qa",
    "kuwait": "kw", "kw": "kw",
    "bahrain": "bh", "bh": "bh",
    "oman": "om", "om": "om",
    "turkey": "tr", "turkiye": "tr", "tr": "tr",
    "israel": "il", "il": "il",

    # Latin America
    "brazil": "br", "br": "br",
    "argentina": "ar", "ar": "ar",
    "chile": "cl", "cl": "cl",
    "colombia": "co", "co": "co",
    "peru": "pe", "pe": "pe",

    # Africa
    "south africa": "za", "za": "za",
    "egypt": "eg", "eg": "eg",
    "nigeria": "ng", "ng": "ng",
    "kenya": "ke", "ke": "ke",
    "morocco": "ma", "ma": "ma",
}

# Major metropolitan hubs by country to harvest up to 1,000 real leads
COUNTRY_MAJOR_CITIES = {
    "united kingdom": [
        "London", "Manchester", "Birmingham", "Leeds", "Glasgow", "Liverpool", "Bristol",
        "Edinburgh", "Sheffield", "Newcastle", "Belfast", "Cardiff", "Nottingham", "Leicester",
        "Southampton", "Cambridge", "Oxford", "Reading", "Aberdeen", "York", "Brighton",
        "Norwich", "Plymouth", "Coventry", "Derby", "Swansea", "Exeter", "Bath", "Milton Keynes",
        "Northampton", "Swindon", "Luton", "Warrington", "Bournemouth", "Stoke-on-Trent"
    ],
    "united states": [
        "New York", "Los Angeles", "Chicago", "Houston", "Phoenix", "Philadelphia",
        "San Antonio", "San Diego", "Dallas", "Austin", "San Jose", "Fort Worth",
        "Jacksonville", "Columbus", "Charlotte", "Indianapolis", "San Francisco", "Seattle",
        "Denver", "Washington", "Boston", "Nashville", "Detroit", "Portland", "Las Vegas",
        "Miami", "Atlanta", "Minneapolis", "Tampa", "Orlando", "Cleveland", "Raleigh", "Pittsburgh"
    ],
    "canada": [
        "Toronto", "Montreal", "Vancouver", "Calgary", "Edmonton", "Ottawa",
        "Winnipeg", "Quebec City", "Hamilton", "Kitchener", "London", "Victoria",
        "Halifax", "Oshawa", "Windsor", "Saskatoon", "Regina", "Barrie"
    ],
    "australia": [
        "Sydney", "Melbourne", "Brisbane", "Perth", "Adelaide", "Gold Coast",
        "Canberra", "Newcastle", "Wollongong", "Logan City", "Geelong", "Hobart",
        "Townsville", "Cairns", "Darwin", "Toowoomba", "Ballarat", "Bendigo"
    ],
    "united arab emirates": [
        "Dubai", "Abu Dhabi", "Sharjah", "Dubai Marina", "Jumeirah", "Al Barsha",
        "Business Bay", "Deira Dubai", "Bur Dubai", "Al Ain", "Ajman", "Ras Al Khaimah",
        "Dubai Healthcare City", "Downtown Dubai", "Al Reem Island", "JLT Dubai",
        "Al Nahda Dubai", "Mirdif Dubai", "Khalifa City Abu Dhabi", "Al Khalidiyah Abu Dhabi",
        "Al Wasl Dubai", "Al Safa Dubai", "Al Quoz Dubai", "Al Karama Dubai",
        "Al Majaz Sharjah", "Al Qusais Dubai", "Al Garhoud Dubai", "Fujairah", "Umm Al Quwain"
    ],
    "uae": [
        "Dubai", "Abu Dhabi", "Sharjah", "Dubai Marina", "Jumeirah", "Al Barsha",
        "Business Bay", "Deira Dubai", "Bur Dubai", "Al Ain", "Ajman", "Ras Al Khaimah",
        "Dubai Healthcare City", "Downtown Dubai", "Al Reem Island", "JLT Dubai",
        "Al Nahda Dubai", "Mirdif Dubai", "Khalifa City Abu Dhabi", "Al Khalidiyah Abu Dhabi",
        "Al Wasl Dubai", "Al Safa Dubai", "Al Quoz Dubai", "Al Karama Dubai",
        "Al Majaz Sharjah", "Al Qusais Dubai", "Al Garhoud Dubai", "Fujairah", "Umm Al Quwain"
    ],
    "ae": [
        "Dubai", "Abu Dhabi", "Sharjah", "Dubai Marina", "Jumeirah", "Al Barsha",
        "Business Bay", "Deira Dubai", "Bur Dubai", "Al Ain", "Ajman", "Ras Al Khaimah",
        "Dubai Healthcare City", "Downtown Dubai", "Al Reem Island", "JLT Dubai",
        "Al Nahda Dubai", "Mirdif Dubai", "Khalifa City Abu Dhabi", "Al Khalidiyah Abu Dhabi",
        "Al Wasl Dubai", "Al Safa Dubai", "Al Quoz Dubai", "Al Karama Dubai",
        "Al Majaz Sharjah", "Al Qusais Dubai", "Al Garhoud Dubai", "Fujairah", "Umm Al Quwain"
    ],
    "germany": [
        "Berlin", "Munich", "Hamburg", "Frankfurt", "Cologne", "Stuttgart", "Düsseldorf",
        "Leipzig", "Dortmund", "Essen", "Bremen", "Dresden", "Hanover", "Nuremberg", "Bonn"
    ],
    "france": [
        "Paris", "Marseille", "Lyon", "Toulouse", "Nice", "Nantes", "Strasbourg",
        "Montpellier", "Bordeaux", "Lille", "Rennes", "Reims", "Toulon", "Grenoble"
    ],
    "netherlands": [
        "Amsterdam", "Rotterdam", "The Hague", "Utrecht", "Eindhoven", "Groningen", "Tilburg"
    ],
    "ireland": [
        "Dublin", "Cork", "Galway", "Limerick", "Waterford", "Drogheda", "Dundalk", "Swords"
    ],
    "spain": [
        "Madrid", "Barcelona", "Valencia", "Seville", "Zaragoza", "Malaga", "Murcia", "Palma", "Bilbao", "Alicante"
    ],
    "italy": [
        "Rome", "Milan", "Naples", "Turin", "Palermo", "Genoa", "Bologna", "Florence", "Bari", "Catania", "Verona"
    ],
    "switzerland": [
        "Zurich", "Geneva", "Basel", "Bern", "Lausanne", "Lucerne", "St. Gallen", "Lugano"
    ],
    "sweden": [
        "Stockholm", "Gothenburg", "Malmo", "Uppsala", "Vasteras", "Orebro", "Linkoping", "Helsingborg"
    ],
    "norway": [
        "Oslo", "Bergen", "Trondheim", "Stavanger", "Drammen", "Fredrikstad", "Kristiansand", "Tromso"
    ],
    "denmark": [
        "Copenhagen", "Aarhus", "Odense", "Aalborg", "Esbjerg", "Randers", "Kolding", "Horsens"
    ],
    "finland": [
        "Helsinki", "Espoo", "Tampere", "Vantaa", "Oulu", "Turku", "Jyvaskyla", "Lahti"
    ],
    "belgium": [
        "Brussels", "Antwerp", "Ghent", "Charleroi", "Liege", "Bruges", "Namur", "Leuven"
    ],
    "austria": [
        "Vienna", "Graz", "Linz", "Salzburg", "Innsbruck", "Klagenfurt", "Villach", "Wels"
    ],
    "poland": [
        "Warsaw", "Krakow", "Lodz", "Wroclaw", "Poznan", "Gdansk", "Szczecin", "Bydgoszcz", "Lublin", "Katowice"
    ],
    "portugal": [
        "Lisbon", "Porto", "Vila Nova de Gaia", "Amadora", "Braga", "Coimbra", "Funchal", "Setubal", "Faro"
    ],
    "greece": [
        "Athens", "Thessaloniki", "Patras", "Heraklion", "Larissa", "Volos", "Ioannina", "Chania"
    ],
    "czech republic": [
        "Prague", "Brno", "Ostrava", "Plzen", "Liberec", "Olomouc", "Ceske Budejovice"
    ],
    "romania": [
        "Bucharest", "Cluj-Napoca", "Timisoara", "Iasi", "Constanta", "Craiova", "Brasov"
    ],
    "hungary": [
        "Budapest", "Debrecen", "Szeged", "Miskolc", "Pecs", "Gyor"
    ],
    "singapore": [
        "Singapore Central", "Jurong", "Tampines", "Woodlands", "Bedok", "Ang Mo Kio"
    ],
    "japan": [
        "Tokyo", "Yokohama", "Osaka", "Nagoya", "Sapporo", "Fukuoka", "Kobe", "Kyoto", "Kawasaki", "Saitama"
    ],
    "south korea": [
        "Seoul", "Busan", "Incheon", "Daegu", "Daejeon", "Gwangju", "Suwon", "Ulsan", "Changwon"
    ],
    "saudi arabia": [
        "Riyadh", "Jeddah", "Mecca", "Medina", "Dammam", "Khobar", "Tabuk"
    ],
    "india": [
        "Mumbai", "Delhi", "Bengaluru", "Hyderabad", "Chennai", "Kolkata",
        "Pune", "Ahmedabad", "Jaipur", "Surat", "Lucknow", "Chandigarh"
    ],
    "bangladesh": [
        "Dhaka", "Chattogram", "Sylhet", "Khulna", "Rajshahi", "Bogura", "Cumilla"
    ],
    "pakistan": [
        "Karachi", "Lahore", "Faisalabad", "Rawalpindi", "Gujranwala", "Peshawar", "Multan", "Islamabad"
    ],
    "malaysia": [
        "Kuala Lumpur", "George Town", "Johor Bahru", "Ipoh", "Shah Alam", "Petaling Jaya"
    ],
    "indonesia": [
        "Jakarta", "Surabaya", "Bandung", "Medan", "Bekasi", "Tangerang", "Depok", "Semarang", "Bali"
    ],
    "philippines": [
        "Manila", "Quezon City", "Davao City", "Cebu City", "Taguig", "Makati", "Pasig"
    ],
    "thailand": [
        "Bangkok", "Nonthaburi", "Chiang Mai", "Hat Yai", "Udon Thani", "Phuket", "Pattaya"
    ],
    "vietnam": [
        "Ho Chi Minh City", "Hanoi", "Da Nang", "Hai Phong", "Can Tho", "Nha Trang"
    ],
    "hong kong": [
        "Hong Kong Island", "Kowloon", "New Territories", "Central Hong Kong", "Tsim Sha Tsui"
    ],
    "taiwan": [
        "Taipei", "New Taipei City", "Kaohsiung", "Taichung", "Tainan", "Taoyuan", "Hsinchu"
    ],
    "qatar": [
        "Doha", "Al Rayyan", "Al Wakrah", "Al Khor", "Lusail"
    ],
    "kuwait": [
        "Kuwait City", "Al Ahmadi", "Hawally", "Salmiya", "Al Farwaniyah"
    ],
    "bahrain": [
        "Manama", "Riffa", "Muharraq", "Hamad Town"
    ],
    "oman": [
        "Muscat", "Seeb", "Salalah", "Bawshar", "Sohar"
    ],
    "turkey": [
        "Istanbul", "Ankara", "Izmir", "Bursa", "Antalya", "Adana", "Konya", "Gaziantep"
    ],
    "israel": [
        "Jerusalem", "Tel Aviv", "Haifa", "Rishon LeZion", "Petah Tikva", "Ashdod", "Netanya"
    ],
    "mexico": [
        "Mexico City", "Guadalajara", "Monterrey", "Puebla", "Tijuana", "Leon", "Zapopan", "Merida", "Cancun"
    ],
    "new zealand": [
        "Auckland", "Wellington", "Christchurch", "Hamilton", "Tauranga", "Napier", "Dunedin"
    ],
    "brazil": [
        "Sao Paulo", "Rio de Janeiro", "Brasilia", "Salvador", "Fortaleza", "Belo Horizonte", "Curitiba", "Porto Alegre"
    ],
    "argentina": [
        "Buenos Aires", "Cordoba", "Rosario", "Mendoza", "La Plata", "Mar del Plata", "Salta"
    ],
    "chile": [
        "Santiago", "Valparaiso", "Concepcion", "La Serena", "Antofagasta"
    ],
    "colombia": [
        "Bogota", "Medellin", "Cali", "Barranquilla", "Cartagena", "Bucaramanga"
    ],
    "peru": [
        "Lima", "Arequipa", "Trujillo", "Chiclayo", "Cusco", "Piura"
    ],
    "south africa": [
        "Johannesburg", "Cape Town", "Durban", "Pretoria", "Port Elizabeth", "Bloemfontein"
    ],
    "egypt": [
        "Cairo", "Alexandria", "Giza", "Shubra El Kheima", "Port Said", "Suez", "Mansoura"
    ],
    "nigeria": [
        "Lagos", "Kano", "Ibadan", "Kaduna", "Port Harcourt", "Benin City", "Abuja"
    ],
    "kenya": [
        "Nairobi", "Mombasa", "Kisumu", "Nakuru", "Eldoret"
    ],
    "morocco": [
        "Casablanca", "Rabat", "Fes", "Marrakech", "Tangier", "Agadir"
    ]
}

# Sub-districts for major cities when a single city is targeted
CITY_DISTRICTS = {
    "chicago": ["Downtown", "Lincoln Park", "West Loop", "Lakeview", "River North", "Wicker Park", "South Loop", "Logan Square", "Hyde Park", "Uptown"],
    "new york": ["Manhattan", "Brooklyn", "Queens", "Bronx", "Staten Island", "Midtown", "Upper East Side", "Williamsburg", "Astoria"],
    "london": ["City of London", "Westminster", "Kensington", "Camden", "Islington", "Greenwich", "Hackney", "Southwark", "Richmond", "Chelsea"],
    "los angeles": ["Downtown", "Hollywood", "Santa Monica", "Beverly Hills", "Pasadena", "Westwood", "Glendale", "Long Beach"],
    "toronto": ["Downtown", "North York", "Scarborough", "Etobicoke", "Yorkville", "Midtown"],
    "dubai": ["Downtown", "Marina", "Jumeirah", "Deira", "Business Bay", "Al Barsha"],
    "sydney": ["CBD", "Parramatta", "North Sydney", "Bondi", "Surry Hills", "Chatswood"]
}

# Sub-specialty variations for high-volume lead harvesting
INDUSTRY_VARIATIONS = {
    "dentals": [
        "dentist", "dental clinic", "orthodontist", "cosmetic dentist",
        "private dentist", "dental surgery", "implant dentist", "pediatric dentist",
        "family dental", "teeth whitening clinic", "emergency dentist"
    ],
    "dental": [
        "dentist", "dental clinic", "orthodontist", "cosmetic dentist",
        "private dentist", "dental surgery", "implant dentist", "pediatric dentist",
        "family dental", "teeth whitening clinic", "emergency dentist"
    ],
    "logistics": [
        "logistics company", "freight forwarding", "transport services", "warehouse logistics",
        "trucking company", "supply chain solutions", "cargo logistics", "courier express",
        "3pl provider", "shipping company", "distribution services"
    ],
    "clinic": [
        "medical clinic", "private clinic", "health centre", "family clinic",
        "specialist clinic", "urgent care", "wellness clinic", "outpatient clinic"
    ],
    "lawyer": [
        "law firm", "solicitors", "attorney", "legal services",
        "commercial lawyer", "corporate law firm", "injury lawyer", "estate solicitors"
    ],
    "real estate": [
        "estate agents", "realtor", "property management", "real estate agency",
        "commercial property", "letting agents", "property consultants"
    ],
    "car": [
        "car repair", "auto repair", "car dealership", "car dealer",
        "auto mechanic", "car service", "car body shop", "used cars"
    ],
    "cars": [
        "car repair", "auto repair", "car dealership", "car dealer",
        "auto mechanic", "car service", "car body shop", "used cars"
    ],
    "cars shop": [
        "car repair", "auto repair", "car dealership", "car dealer",
        "auto mechanic", "car service", "car body shop", "used cars"
    ],
    "car shop": [
        "car repair", "auto repair", "car dealership", "car dealer",
        "auto mechanic", "car service", "car body shop", "used cars"
    ],
    "auto": [
        "auto repair", "car mechanic", "car dealership", "auto service", "auto body shop"
    ],
    "restaurant": [
        "restaurant", "fine dining", "bistro", "cafe", "grill restaurant", "gastropub", "catering company"
    ]
}



# Resolve aliases to the same country/city data, including Bangladesh.
COUNTRY_CODES.update({'bangladesh': 'bd', 'bd': 'bd'})
COUNTRY_MAJOR_CITIES['bangladesh'] = ['Dhaka', 'Chattogram', 'Sylhet', 'Khulna', 'Rajshahi']
for _alias, _code in COUNTRY_CODES.items():
    if _alias not in COUNTRY_MAJOR_CITIES:
        _canonical = next((name for name in COUNTRY_MAJOR_CITIES if COUNTRY_CODES.get(name) == _code), None)
        if _canonical:
            COUNTRY_MAJOR_CITIES[_alias] = COUNTRY_MAJOR_CITIES[_canonical]
