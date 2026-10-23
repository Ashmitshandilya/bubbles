"""Builds data/cities.json for the Stars lens: Indian cities and towns above about 100,000 people plus world capitals, each with latitude,
longitude (degrees east positive), an IANA time zone and the standard UTC offset in minutes (used when the machine has no tz database).
Coordinates are rounded to 0.1 degree, which is about 11 km: far finer than the lens needs. Run: python data/make_cities.py
"""
import json
from pathlib import Path

IST = ("Asia/Kolkata", 330)
# name, state or country, lat, lon
INDIA = [
    ("Mumbai", "Maharashtra", 19.1, 72.9), ("Delhi", "Delhi", 28.6, 77.2), ("Bengaluru", "Karnataka", 13.0, 77.6), ("Hyderabad", "Telangana", 17.4, 78.5),
    ("Ahmedabad", "Gujarat", 23.0, 72.6), ("Chennai", "Tamil Nadu", 13.1, 80.3), ("Kolkata", "West Bengal", 22.6, 88.4), ("Surat", "Gujarat", 21.2, 72.8),
    ("Pune", "Maharashtra", 18.5, 73.9), ("Jaipur", "Rajasthan", 26.9, 75.8), ("Lucknow", "Uttar Pradesh", 26.8, 80.9), ("Kanpur", "Uttar Pradesh", 26.4, 80.3),
    ("Nagpur", "Maharashtra", 21.1, 79.1), ("Indore", "Madhya Pradesh", 22.7, 75.9), ("Thane", "Maharashtra", 19.2, 72.97), ("Bhopal", "Madhya Pradesh", 23.3, 77.4),
    ("Visakhapatnam", "Andhra Pradesh", 17.7, 83.2), ("Patna", "Bihar", 25.6, 85.1), ("Vadodara", "Gujarat", 22.3, 73.2), ("Ghaziabad", "Uttar Pradesh", 28.7, 77.4),
    ("Ludhiana", "Punjab", 30.9, 75.9), ("Agra", "Uttar Pradesh", 27.2, 78.0), ("Nashik", "Maharashtra", 20.0, 73.8), ("Faridabad", "Haryana", 28.4, 77.3),
    ("Meerut", "Uttar Pradesh", 29.0, 77.7), ("Rajkot", "Gujarat", 22.3, 70.8), ("Kalyan", "Maharashtra", 19.2, 73.1), ("Vasai-Virar", "Maharashtra", 19.4, 72.8),
    ("Varanasi", "Uttar Pradesh", 25.3, 83.0), ("Srinagar", "Jammu and Kashmir", 34.1, 74.8), ("Aurangabad", "Maharashtra", 19.9, 75.3), ("Dhanbad", "Jharkhand", 23.8, 86.4),
    ("Amritsar", "Punjab", 31.6, 74.9), ("Navi Mumbai", "Maharashtra", 19.0, 73.0), ("Prayagraj", "Uttar Pradesh", 25.4, 81.8), ("Howrah", "West Bengal", 22.6, 88.3),
    ("Ranchi", "Jharkhand", 23.3, 85.3), ("Gwalior", "Madhya Pradesh", 26.2, 78.2), ("Jabalpur", "Madhya Pradesh", 23.2, 79.9), ("Coimbatore", "Tamil Nadu", 11.0, 76.96),
    ("Vijayawada", "Andhra Pradesh", 16.5, 80.6), ("Jodhpur", "Rajasthan", 26.3, 73.0), ("Madurai", "Tamil Nadu", 9.9, 78.1), ("Raipur", "Chhattisgarh", 21.3, 81.6),
    ("Kota", "Rajasthan", 25.2, 75.8), ("Chandigarh", "Chandigarh", 30.7, 76.8), ("Guwahati", "Assam", 26.1, 91.7), ("Solapur", "Maharashtra", 17.7, 75.9),
    ("Hubballi-Dharwad", "Karnataka", 15.4, 75.1), ("Mysuru", "Karnataka", 12.3, 76.6), ("Tiruchirappalli", "Tamil Nadu", 10.8, 78.7), ("Bareilly", "Uttar Pradesh", 28.4, 79.4),
    ("Aligarh", "Uttar Pradesh", 27.9, 78.1), ("Tiruppur", "Tamil Nadu", 11.1, 77.3), ("Gurugram", "Haryana", 28.5, 77.0), ("Moradabad", "Uttar Pradesh", 28.8, 78.8),
    ("Jalandhar", "Punjab", 31.3, 75.6), ("Bhubaneswar", "Odisha", 20.3, 85.8), ("Salem", "Tamil Nadu", 11.7, 78.2), ("Warangal", "Telangana", 18.0, 79.6),
    ("Thiruvananthapuram", "Kerala", 8.5, 76.9), ("Guntur", "Andhra Pradesh", 16.3, 80.4), ("Bhiwandi", "Maharashtra", 19.3, 73.1), ("Saharanpur", "Uttar Pradesh", 29.97, 77.5),
    ("Gorakhpur", "Uttar Pradesh", 26.8, 83.4), ("Bikaner", "Rajasthan", 28.0, 73.3), ("Amravati", "Maharashtra", 20.9, 77.8), ("Noida", "Uttar Pradesh", 28.5, 77.4),
    ("Jamshedpur", "Jharkhand", 22.8, 86.2), ("Bhilai", "Chhattisgarh", 21.2, 81.4), ("Cuttack", "Odisha", 20.5, 85.9), ("Firozabad", "Uttar Pradesh", 27.2, 78.4),
    ("Kochi", "Kerala", 9.9, 76.3), ("Nellore", "Andhra Pradesh", 14.4, 79.99), ("Bhavnagar", "Gujarat", 21.8, 72.2), ("Dehradun", "Uttarakhand", 30.3, 78.0),
    ("Durgapur", "West Bengal", 23.5, 87.3), ("Asansol", "West Bengal", 23.7, 87.0), ("Rourkela", "Odisha", 22.3, 84.9), ("Nanded", "Maharashtra", 19.2, 77.3),
    ("Kolhapur", "Maharashtra", 16.7, 74.2), ("Ajmer", "Rajasthan", 26.4, 74.6), ("Akola", "Maharashtra", 20.7, 77.0), ("Gulbarga", "Karnataka", 17.3, 76.8),
    ("Jamnagar", "Gujarat", 22.5, 70.1), ("Ujjain", "Madhya Pradesh", 23.2, 75.8), ("Loni", "Uttar Pradesh", 28.8, 77.3), ("Siliguri", "West Bengal", 26.7, 88.4),
    ("Jhansi", "Uttar Pradesh", 25.4, 78.6), ("Ulhasnagar", "Maharashtra", 19.2, 73.2), ("Jammu", "Jammu and Kashmir", 32.7, 74.9), ("Sangli", "Maharashtra", 16.9, 74.6),
    ("Mangaluru", "Karnataka", 12.9, 74.9), ("Erode", "Tamil Nadu", 11.3, 77.7), ("Belgaum", "Karnataka", 15.8, 74.5), ("Ambattur", "Tamil Nadu", 13.1, 80.2),
    ("Tirunelveli", "Tamil Nadu", 8.7, 77.7), ("Malegaon", "Maharashtra", 20.6, 74.5), ("Gaya", "Bihar", 24.8, 85.0), ("Udaipur", "Rajasthan", 24.6, 73.7),
    ("Kakinada", "Andhra Pradesh", 17.0, 82.2), ("Davanagere", "Karnataka", 14.5, 75.9), ("Kozhikode", "Kerala", 11.3, 75.8), ("Maheshtala", "West Bengal", 22.5, 88.2),
    ("Rajahmundry", "Andhra Pradesh", 17.0, 81.8), ("Bokaro", "Jharkhand", 23.7, 86.2), ("South Dumdum", "West Bengal", 22.6, 88.4), ("Bellary", "Karnataka", 15.1, 76.9),
    ("Patiala", "Punjab", 30.3, 76.4), ("Gopalpur", "Odisha", 19.3, 84.9), ("Agartala", "Tripura", 23.8, 91.3), ("Bhagalpur", "Bihar", 25.2, 87.0),
    ("Muzaffarnagar", "Uttar Pradesh", 29.5, 77.7), ("Bhatpara", "West Bengal", 22.9, 88.4), ("Panihati", "West Bengal", 22.7, 88.4), ("Latur", "Maharashtra", 18.4, 76.6),
    ("Dhule", "Maharashtra", 20.9, 74.8), ("Rohtak", "Haryana", 28.9, 76.6), ("Korba", "Chhattisgarh", 22.4, 82.7), ("Bhilwara", "Rajasthan", 25.3, 74.6),
    ("Brahmapur", "Odisha", 19.3, 84.8), ("Muzaffarpur", "Bihar", 26.1, 85.4), ("Ahmednagar", "Maharashtra", 19.1, 74.7), ("Mathura", "Uttar Pradesh", 27.5, 77.7),
    ("Kollam", "Kerala", 8.9, 76.6), ("Avadi", "Tamil Nadu", 13.1, 80.1), ("Kadapa", "Andhra Pradesh", 14.5, 78.8), ("Anantapur", "Andhra Pradesh", 14.7, 77.6),
    ("Kamarhati", "West Bengal", 22.7, 88.4), ("Bilaspur", "Chhattisgarh", 22.1, 82.1), ("Shahjahanpur", "Uttar Pradesh", 27.9, 79.9), ("Bijapur", "Karnataka", 16.8, 75.7),
    ("Rampur", "Uttar Pradesh", 28.8, 79.0), ("Shivamogga", "Karnataka", 13.9, 75.6), ("Chandrapur", "Maharashtra", 19.97, 79.3), ("Junagadh", "Gujarat", 21.5, 70.5),
    ("Thrissur", "Kerala", 10.5, 76.2), ("Alwar", "Rajasthan", 27.6, 76.6), ("Bardhaman", "West Bengal", 23.2, 87.9), ("Kulti", "West Bengal", 23.7, 86.8),
    ("Kakinada", "Andhra Pradesh", 16.99, 82.2), ("Nizamabad", "Telangana", 18.7, 78.1), ("Parbhani", "Maharashtra", 19.3, 76.8), ("Tumkur", "Karnataka", 13.3, 77.1),
    ("Khammam", "Telangana", 17.2, 80.2), ("Ozhukarai", "Puducherry", 11.96, 79.8), ("Bihar Sharif", "Bihar", 25.2, 85.5), ("Panipat", "Haryana", 29.4, 77.0),
    ("Darbhanga", "Bihar", 26.2, 85.9), ("Bally", "West Bengal", 22.65, 88.3), ("Aizawl", "Mizoram", 23.7, 92.7), ("Dewas", "Madhya Pradesh", 22.97, 76.1),
    ("Ichalkaranji", "Maharashtra", 16.7, 74.5), ("Karnal", "Haryana", 29.7, 77.0), ("Bathinda", "Punjab", 30.2, 74.9), ("Jalna", "Maharashtra", 19.8, 75.9),
    ("Eluru", "Andhra Pradesh", 16.7, 81.1), ("Barasat", "West Bengal", 22.7, 88.5), ("Kirari Suleman Nagar", "Delhi", 28.7, 77.06), ("Purnia", "Bihar", 25.8, 87.5),
    ("Satara", "Maharashtra", 17.7, 74.0), ("Puducherry", "Puducherry", 11.9, 79.8), ("Imphal", "Manipur", 24.8, 93.9), ("Shillong", "Meghalaya", 25.6, 91.9),
    ("Gangtok", "Sikkim", 27.3, 88.6), ("Panaji", "Goa", 15.5, 73.8), ("Itanagar", "Arunachal Pradesh", 27.1, 93.6), ("Kohima", "Nagaland", 25.7, 94.1),
    ("Port Blair", "Andaman and Nicobar", 11.7, 92.7), ("Shimla", "Himachal Pradesh", 31.1, 77.2), ("Haridwar", "Uttarakhand", 29.9, 78.2), ("Leh", "Ladakh", 34.2, 77.6),
]
# name, country, lat, lon, IANA zone, standard UTC offset minutes (capitals; where a country has several zones the capital's is used)
WORLD = [
    ("Washington, D.C.", "United States", 38.9, -77.0, "America/New_York", -300), ("New York", "United States", 40.7, -74.0, "America/New_York", -300),
    ("Los Angeles", "United States", 34.1, -118.2, "America/Los_Angeles", -480), ("Chicago", "United States", 41.9, -87.6, "America/Chicago", -360),
    ("San Francisco", "United States", 37.8, -122.4, "America/Los_Angeles", -480), ("Houston", "United States", 29.8, -95.4, "America/Chicago", -360),
    ("London", "United Kingdom", 51.5, -0.1, "Europe/London", 0), ("Manchester", "United Kingdom", 53.5, -2.2, "Europe/London", 0),
    ("Ottawa", "Canada", 45.4, -75.7, "America/Toronto", -300), ("Toronto", "Canada", 43.7, -79.4, "America/Toronto", -300), ("Vancouver", "Canada", 49.3, -123.1, "America/Vancouver", -480),
    ("Canberra", "Australia", -35.3, 149.1, "Australia/Sydney", 600), ("Sydney", "Australia", -33.9, 151.2, "Australia/Sydney", 600), ("Melbourne", "Australia", -37.8, 145.0, "Australia/Melbourne", 600),
    ("Abu Dhabi", "United Arab Emirates", 24.5, 54.4, "Asia/Dubai", 240), ("Dubai", "United Arab Emirates", 25.2, 55.3, "Asia/Dubai", 240),
    ("Singapore", "Singapore", 1.35, 103.8, "Asia/Singapore", 480), ("Kathmandu", "Nepal", 27.7, 85.3, "Asia/Kathmandu", 345), ("Dhaka", "Bangladesh", 23.8, 90.4, "Asia/Dhaka", 360),
    ("Colombo", "Sri Lanka", 6.9, 79.9, "Asia/Colombo", 330), ("Islamabad", "Pakistan", 33.7, 73.1, "Asia/Karachi", 300), ("Karachi", "Pakistan", 24.9, 67.0, "Asia/Karachi", 300),
    ("Thimphu", "Bhutan", 27.5, 89.6, "Asia/Thimphu", 360), ("Kabul", "Afghanistan", 34.5, 69.2, "Asia/Kabul", 270), ("Male", "Maldives", 4.2, 73.5, "Indian/Maldives", 300),
    ("Doha", "Qatar", 25.3, 51.5, "Asia/Qatar", 180), ("Riyadh", "Saudi Arabia", 24.7, 46.7, "Asia/Riyadh", 180), ("Muscat", "Oman", 23.6, 58.4, "Asia/Muscat", 240),
    ("Kuwait City", "Kuwait", 29.4, 48.0, "Asia/Kuwait", 180), ("Manama", "Bahrain", 26.2, 50.6, "Asia/Bahrain", 180), ("Tehran", "Iran", 35.7, 51.4, "Asia/Tehran", 210),
    ("Baghdad", "Iraq", 33.3, 44.4, "Asia/Baghdad", 180), ("Amman", "Jordan", 31.95, 35.9, "Asia/Amman", 120), ("Beirut", "Lebanon", 33.9, 35.5, "Asia/Beirut", 120),
    ("Jerusalem", "Israel", 31.8, 35.2, "Asia/Jerusalem", 120), ("Ankara", "Turkey", 39.9, 32.9, "Europe/Istanbul", 180), ("Istanbul", "Turkey", 41.0, 29.0, "Europe/Istanbul", 180),
    ("Cairo", "Egypt", 30.0, 31.2, "Africa/Cairo", 120), ("Nairobi", "Kenya", -1.3, 36.8, "Africa/Nairobi", 180), ("Addis Ababa", "Ethiopia", 9.0, 38.7, "Africa/Addis_Ababa", 180),
    ("Lagos", "Nigeria", 6.5, 3.4, "Africa/Lagos", 60), ("Abuja", "Nigeria", 9.1, 7.5, "Africa/Lagos", 60), ("Accra", "Ghana", 5.6, -0.2, "Africa/Accra", 0),
    ("Pretoria", "South Africa", -25.7, 28.2, "Africa/Johannesburg", 120), ("Johannesburg", "South Africa", -26.2, 28.0, "Africa/Johannesburg", 120), ("Cape Town", "South Africa", -33.9, 18.4, "Africa/Johannesburg", 120),
    ("Kampala", "Uganda", 0.35, 32.6, "Africa/Kampala", 180), ("Dar es Salaam", "Tanzania", -6.8, 39.3, "Africa/Dar_es_Salaam", 180), ("Port Louis", "Mauritius", -20.2, 57.5, "Indian/Mauritius", 240),
    ("Paris", "France", 48.9, 2.35, "Europe/Paris", 60), ("Berlin", "Germany", 52.5, 13.4, "Europe/Berlin", 60), ("Rome", "Italy", 41.9, 12.5, "Europe/Rome", 60),
    ("Madrid", "Spain", 40.4, -3.7, "Europe/Madrid", 60), ("Lisbon", "Portugal", 38.7, -9.1, "Europe/Lisbon", 0), ("Dublin", "Ireland", 53.3, -6.3, "Europe/Dublin", 0),
    ("Amsterdam", "Netherlands", 52.4, 4.9, "Europe/Amsterdam", 60), ("Brussels", "Belgium", 50.85, 4.35, "Europe/Brussels", 60), ("Zurich", "Switzerland", 47.4, 8.5, "Europe/Zurich", 60),
    ("Vienna", "Austria", 48.2, 16.4, "Europe/Vienna", 60), ("Stockholm", "Sweden", 59.3, 18.1, "Europe/Stockholm", 60), ("Oslo", "Norway", 59.9, 10.75, "Europe/Oslo", 60),
    ("Copenhagen", "Denmark", 55.7, 12.6, "Europe/Copenhagen", 60), ("Helsinki", "Finland", 60.2, 24.9, "Europe/Helsinki", 120), ("Warsaw", "Poland", 52.2, 21.0, "Europe/Warsaw", 60),
    ("Prague", "Czechia", 50.1, 14.4, "Europe/Prague", 60), ("Budapest", "Hungary", 47.5, 19.0, "Europe/Budapest", 60), ("Athens", "Greece", 38.0, 23.7, "Europe/Athens", 120),
    ("Moscow", "Russia", 55.75, 37.6, "Europe/Moscow", 180), ("Kyiv", "Ukraine", 50.45, 30.5, "Europe/Kyiv", 120),
    ("Beijing", "China", 39.9, 116.4, "Asia/Shanghai", 480), ("Shanghai", "China", 31.2, 121.5, "Asia/Shanghai", 480), ("Hong Kong", "China", 22.3, 114.2, "Asia/Hong_Kong", 480),
    ("Tokyo", "Japan", 35.7, 139.7, "Asia/Tokyo", 540), ("Seoul", "South Korea", 37.6, 127.0, "Asia/Seoul", 540), ("Bangkok", "Thailand", 13.75, 100.5, "Asia/Bangkok", 420),
    ("Kuala Lumpur", "Malaysia", 3.1, 101.7, "Asia/Kuala_Lumpur", 480), ("Jakarta", "Indonesia", -6.2, 106.8, "Asia/Jakarta", 420), ("Manila", "Philippines", 14.6, 121.0, "Asia/Manila", 480),
    ("Hanoi", "Vietnam", 21.0, 105.85, "Asia/Ho_Chi_Minh", 420), ("Yangon", "Myanmar", 16.8, 96.15, "Asia/Yangon", 390), ("Phnom Penh", "Cambodia", 11.55, 104.9, "Asia/Phnom_Penh", 420),
    ("Wellington", "New Zealand", -41.3, 174.8, "Pacific/Auckland", 720), ("Auckland", "New Zealand", -36.85, 174.8, "Pacific/Auckland", 720), ("Suva", "Fiji", -18.1, 178.4, "Pacific/Fiji", 720),
    ("Mexico City", "Mexico", 19.4, -99.1, "America/Mexico_City", -360), ("Sao Paulo", "Brazil", -23.55, -46.6, "America/Sao_Paulo", -180), ("Brasilia", "Brazil", -15.8, -47.9, "America/Sao_Paulo", -180),
    ("Buenos Aires", "Argentina", -34.6, -58.4, "America/Argentina/Buenos_Aires", -180), ("Santiago", "Chile", -33.45, -70.7, "America/Santiago", -240), ("Lima", "Peru", -12.05, -77.05, "America/Lima", -300),
    ("Bogota", "Colombia", 4.7, -74.1, "America/Bogota", -300), ("Port of Spain", "Trinidad and Tobago", 10.65, -61.5, "America/Port_of_Spain", -240), ("Georgetown", "Guyana", 6.8, -58.15, "America/Guyana", -240),
    ("Paramaribo", "Suriname", 5.85, -55.2, "America/Paramaribo", -180),
]


def build() -> list[dict]:
    rows = []
    seen = set()
    for name, state, lat, lon in INDIA:
        key = (name, "India")
        if key in seen:
            continue
        seen.add(key)
        rows.append({"name": name, "region": state, "country": "India", "lat": round(lat, 2), "lon": round(lon, 2), "tz": IST[0], "offset": IST[1]})
    for name, country, lat, lon, tz, offset in WORLD:
        rows.append({"name": name, "region": country, "country": country, "lat": lat, "lon": lon, "tz": tz, "offset": offset})
    return rows


if __name__ == "__main__":
    out = Path(__file__).with_name("cities.json")
    rows = build()
    out.write_text(json.dumps(rows, ensure_ascii=False, separators=(",", ":")), encoding="utf8")
    print(len(rows), "places written to", out)
