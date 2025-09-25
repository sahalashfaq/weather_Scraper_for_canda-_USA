import streamlit as st
import requests
import folium
from streamlit_folium import st_folium
import uuid
import random
from bs4 import BeautifulSoup

# ------------------------
# Fake Temp Email Generator (instead of Mail.tm)
# ------------------------
def get_temp_email():
    realistic_domains = [
        "gmail.com", "yahoo.com", "outlook.com", "hotmail.com",
        "proton.me", "mail.com", "aol.com", "icloud.com"
    ]
    username = f"user{uuid.uuid4().hex[:6]}"
    fake_domain = random.choice(realistic_domains)
    return f"{username}@{fake_domain}", "nopassword"


# ------------------------
# Load local CSS
# ------------------------
def local_css(file_name):
    try:
        with open(file_name, "r", encoding="utf-8") as f:
            st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)
    except FileNotFoundError:
        pass


# ------------------------
# Weather.gov Functions (USA)
# ------------------------
HEADERS = {"User-Agent": "WeatherStreamlitApp/1.0 (contact@example.com)"}

def fetch_json(url):
    r = requests.get(url, headers=HEADERS)
    r.raise_for_status()
    return r.json()

def get_nws_metadata(lat, lon):
    return fetch_json(f"https://api.weather.gov/points/{lat},{lon}")

def get_current_conditions(stations_url):
    stations = fetch_json(stations_url).get("features", [])
    if not stations:
        return None
    station_id = stations[0]["properties"]["stationIdentifier"]
    obs_url = f"https://api.weather.gov/stations/{station_id}/observations/latest"
    return fetch_json(obs_url).get("properties", {})


# ------------------------
# Canada Scraper
# ------------------------
def scrape_weather_canada_by_coords(lat, lon):
    try:
        url = f"https://weather.gc.ca/en/location/index.html?coords={lat},{lon}"
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code != 200:
            return None

        soup = BeautifulSoup(resp.text, "html.parser")
        main_content = soup.select_one("#mainContent")

        blocks = []
        if main_content:
            for div in main_content.select("div.hidden-xs.row.no-gutters"):
                blocks.append({"title": "Overview", "text": div.get_text("\n", strip=True)})

            sections = main_content.select("section.hidden-xs")
            if sections:
                forecast_section = sections[-1]
                heading = forecast_section.find("h2") or forecast_section.find("h3")
                title = heading.get_text(strip=True) if heading else "Forecast"
                blocks.append({"title": title, "text": forecast_section.get_text("\n", strip=True)})

            for div in main_content.select("div.div-column"):
                heading = div.find("h2") or div.find("h3")
                title = heading.get_text(strip=True) if heading else "Section"
                blocks.append({"title": title, "text": div.get_text("\n", strip=True)})

        current = {}
        temp = soup.select_one(".wxo-metric-hide")
        cond = soup.select_one(".wxo-condition")
        humid = soup.find("dt", string="Humidity:")
        wind = soup.find("dt", string="Wind:")

        current["temperature"] = temp.text.strip() if temp else "N/A"
        current["condition"] = cond.text.strip() if cond else "N/A"
        current["humidity"] = humid.find_next("dd").text.strip() if humid else "N/A"
        current["wind"] = wind.find_next("dd").text.strip() if wind else "N/A"

        return {"conditions": current, "blocks": blocks, "forecast": []}
    except Exception:
        return None


# ------------------------
# Other Scrapers (Placeholders)
# ------------------------
def scrape_weather_uk(city):
    return {"forecast": [f"🇬🇧 UK MetOffice: https://www.metoffice.gov.uk/weather/forecast"]}

def scrape_weather_australia(state, city):
    try:
        url = f"https://www.bom.gov.au/{state}/forecasts/{city}.shtml"
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"})
        if resp.status_code != 200:
            return {"error": f"Failed to fetch {url} (status {resp.status_code})"}

        soup = BeautifulSoup(resp.text, "html.parser")
        forecasts = []
        for day_div in soup.select("div.day"):
            day_title = day_div.find("h2")
            title = day_title.get_text(strip=True) if day_title else "Unknown Day"
            details = []
            for dl in day_div.find_all("dl"):
                dt, dd = dl.find("dt"), dl.find("dd")
                if dt and dd:
                    details.append(f"{dt.get_text(strip=True)}: {dd.get_text(strip=True)}")
            forecasts.append({"day": title, "details": details})

        return {"conditions": {"city": city.title(), "state": state.upper()}, "forecast": forecasts}
    except Exception as e:
        return {"error": str(e)}

def scrape_weather_ecmwf(city):
    return {"forecast": [f"ECMWF global: https://www.ecmwf.int/en/forecasts"]}

def scrape_weather_meteoalarm(city):
    return {"forecast": [f"Meteoalarm alerts: https://www.meteoalarm.org"]}


country_scrapers = {
    "canada": scrape_weather_canada_by_coords,
    "united kingdom": scrape_weather_uk,
    "uk": scrape_weather_uk,
    "australia": scrape_weather_australia,
    "aus": scrape_weather_australia,
    "europe": scrape_weather_ecmwf,
    "ecmwf": scrape_weather_ecmwf,
    "meteoalarm": scrape_weather_meteoalarm,
}


# ------------------------
# Streamlit App
# ------------------------
st.set_page_config(page_title="Weather Tool", layout="centered")
local_css("style.css")

# --- Session state init ---
if "geo" not in st.session_state:
    st.session_state.geo = None
if "conditions" not in st.session_state:
    st.session_state.conditions = None
if "forecast" not in st.session_state:
    st.session_state.forecast = None
if "email" not in st.session_state:
    st.session_state.email, st.session_state.email_pass = get_temp_email()

# --- Sidebar Email ---
with st.sidebar:
    st.subheader("📧 Your Temp Email")
    if st.session_state.email:
        st.code(st.session_state.email, language="bash")
    else:
        st.warning("No temp email available")

# --- Location Form ---
with st.form("location_form"):
    country = st.text_input("Country", value="United States")
    province = st.text_input("State / Province", value="California")
    city = st.text_input("City", value="Los Angeles")
    submitted = st.form_submit_button("Get Weather Data")

reset = st.button("Reset Location")
if reset:
    st.session_state.geo = None
    st.session_state.conditions = None
    st.session_state.forecast = None
    st.rerun()

# --- If form submitted ---
if submitted:
    st.session_state.geo = None
    st.session_state.conditions = None
    st.session_state.forecast = None
    st.session_state.area_geo = None

    location_str = f"{city}, {province}, {country}"
    with st.spinner("Finding location..."):
        try:
            geo_url = f"https://nominatim.openstreetmap.org/search?q={location_str}&format=jsonv2&limit=1"
            geo = requests.get(geo_url, headers={"User-Agent": "WeatherApp"}).json()
            if not geo:
                st.error("Location not found.")
                st.stop()
            st.session_state.geo = geo[0]
        except Exception as e:
            st.error(f"Geocoding failed: {e}")
            st.session_state.geo = None

# --- If we have geo ---
if st.session_state.geo:
    geo = st.session_state.geo
    lat, lon = geo["lat"], geo["lon"]

    with st.spinner("Fetching weather data..."):
        try:
            if country.lower() in ["united states", "usa", "us"]:
                meta = get_nws_metadata(lat, lon).get("properties", {})
                forecast_url = meta.get("forecast")
                stations_url = meta.get("observationStations")
                area_url = meta.get("forecastZone")

                if stations_url:
                    st.session_state.conditions = get_current_conditions(stations_url)
                if forecast_url:
                    forecast = fetch_json(forecast_url)
                    st.session_state.forecast = forecast.get("properties", {}).get("periods", [])
                if area_url:
                    st.session_state.area_geo = fetch_json(area_url).get("geometry", {})

            elif country.lower() == "canada":
                result = scrape_weather_canada_by_coords(lat, lon)
                if result:
                    st.session_state.conditions = result
                    st.session_state.forecast = result.get("forecast")
                else:
                    st.error("Could not fetch Canadian weather data.")

            else:
                scraper = country_scrapers.get(country.lower())
                if scraper:
                    result = scraper(city)
                    if result:
                        st.session_state.conditions = result
                        st.session_state.forecast = result.get("forecast")
                    else:
                        st.error(f"Could not fetch weather data for {country}.")
                else:
                    st.warning(f"Weather scraping for {country} not yet supported.")
        except Exception as e:
            st.error(f"Failed to fetch weather data: {e}")

    # --- Map ---
    st.subheader("🗺️ Map of Location & Coverage Area")
    map_type = st.selectbox("Choose map type:", ["OpenStreetMap", "CartoDB positron", "CartoDB dark_matter"])
    m = folium.Map(location=[float(lat), float(lon)], zoom_start=9, tiles=map_type)
    folium.Marker([lat, lon], popup=geo.get("display_name", "Selected Location"), tooltip="Your Location").add_to(m)
    if "area_geo" in st.session_state and st.session_state.area_geo:
        folium.GeoJson(st.session_state.area_geo,
                       style_function=lambda x: {"fillColor": "#3186cc", "color": "blue", "weight": 2, "fillOpacity": 0.25},
                       tooltip="Forecast Coverage Area").add_to(m)
    st_folium(m, width=700, height=500)

    # --- Current Conditions ---
    if st.session_state.conditions:
        if country.lower() in ["united states", "usa", "us"]:
            c = st.session_state.conditions
            st.markdown("### 🌡️ Current Conditions (USA)")
            st.write(f"**Weather:** {c.get('textDescription', 'N/A')}")
            st.write(f"🌡️ Temp: {c.get('temperature', {}).get('value', 'N/A')} °C")
            st.write(f"💨 Wind: {c.get('windSpeed', {}).get('value', 'N/A')} m/s {c.get('windDirection', {}).get('value', '')}°")
            st.write(f"💧 Humidity: {c.get('relativeHumidity', {}).get('value', 'N/A')} %")
            st.write(f"⏱️ Observed: {c.get('timestamp', 'N/A')}")

        elif country.lower() == "canada":
            if "blocks" in st.session_state.conditions:
                st.markdown("### 🌡️ Detailed Weather (Canada)")
                for block in st.session_state.conditions["blocks"]:
                    st.markdown(f"**{block['title']}**")
                    st.write(block["text"])
                    st.markdown("---")
            else:
                st.write(st.session_state.conditions)

        elif country.lower() in ["australia", "aus"]:
            if "error" in st.session_state.conditions:
                st.error(st.session_state.conditions["error"])
            else:
                st.write(st.session_state.conditions)

    # --- Forecast ---
    if st.session_state.forecast:
        st.markdown("### 📅 Forecast")
        for p in st.session_state.forecast[:7]:
            if isinstance(p, dict) and "name" in p:  # USA format
                st.markdown(f"**{p['name']}**")
                st.write(f"🌡️ {p['temperature']}°{p['temperatureUnit']}")
                st.write(f"💨 {p['windSpeed']} {p['windDirection']}")
                st.write(f"📝 {p['detailedForecast']}")
                st.markdown("---")
            else:
                st.write(p)
