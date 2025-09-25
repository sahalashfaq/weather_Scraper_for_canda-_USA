import streamlit as st
import requests
import folium
from streamlit_folium import st_folium
import uuid
from xml.etree import ElementTree
from bs4 import BeautifulSoup
from urllib.parse import quote
# ------------------------
# Mail.tm Temporary Email
# ------------------------
def local_css(file_name):
    with open(file_name, "r", encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

local_css("style.css")

def get_temp_email():
    domain_resp = requests.get("https://api.mail.tm/domains").json()
    if "hydra:member" not in domain_resp or not domain_resp["hydra:member"]:
        raise Exception("No domains available from mail.tm")
    domain = domain_resp["hydra:member"][0]["domain"]

    username = f"user{uuid.uuid4().hex[:8]}@{domain}"
    password = uuid.uuid4().hex

    resp = requests.post("https://api.mail.tm/accounts", json={"address": username, "password": password})
    if resp.status_code == 201:
        return username, password
    else:
        raise Exception(f"Mail.tm error: {resp.text}")

# ------------------------
# Weather.gov Functions
# ------------------------
HEADERS = {"User-Agent": "WeatherStreamlitApp/1.0 (your_email@example.com)"}

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
# Canada Scraper (lat/lon based)
# ------------------------
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
            # 1. Overview
            for div in main_content.select("div.hidden-xs.row.no-gutters"):
                title = "Overview"
                text = div.get_text(separator="\n", strip=True)
                blocks.append({"title": title, "text": text})

            # 2. Forecast (last section.hidden-xs)
            sections = main_content.select("section.hidden-xs")
            if sections:
                forecast_section = sections[-1]
                heading = forecast_section.find("h2") or forecast_section.find("h3")
                title = heading.get_text(strip=True) if heading else "Forecast"
                text = forecast_section.get_text(separator="\n", strip=True)
                blocks.append({"title": title, "text": text})

            # 3. All .div-column
            for idx, div in enumerate(main_content.select("div.div-column")):
                heading = div.find("h2") or div.find("h3")
                title = heading.get_text(strip=True) 
                st.markdown(f"Section {idx+1}</p>",unsafe_allow_html=True)
                text = div.get_text(separator="\n", strip=True)
                blocks.append({"title": title, "text": text})

        # Quick summary
        current = {}
        temp = soup.select_one(".wxo-metric-hide")
        cond = soup.select_one(".wxo-condition")
        humid = soup.find("dt", string="Humidity:")
        wind = soup.find("dt", string="Wind:")

        current["temperature"] = temp.text.strip() if temp else "N/A"
        current["condition"] = cond.text.strip() if cond else "N/A"
        current["humidity"] = humid.find_next("dd").text.strip() if humid else "N/A"
        current["wind"] = wind.find_next("dd").text.strip() if wind else "N/A"

        return {
            "conditions": current,
            "forecast": [],
            "blocks": blocks
        }

    except Exception:
        return None


# ------------------------
# Other Scrapers (placeholders)
# ------------------------
def scrape_weather_uk(city):
    return {"forecast": [f"🇬🇧 UK MetOffice data: https://www.metoffice.gov.uk/weather/forecast"]}

def scrape_weather_australia(state, city):
    """
    Scrape forecast data from Australia's BoM website.
    Args:
        state (str): Province short code (e.g., qld, nsw, vic)
        city (str): City name (lowercase, e.g., brisbane, sydney)
    Returns:
        dict: Forecast data
    """
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
                dt = dl.find("dt")
                dd = dl.find("dd")
                if dt and dd:
                    details.append(f"{dt.get_text(strip=True)}: {dd.get_text(strip=True)}")

            forecasts.append({
                "day": title,
                "details": details
            })

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
    "australia": scrape_weather_australia,  # <- add this
    "aus": scrape_weather_australia,        # optional alias
    "europe": scrape_weather_ecmwf,
    "ecmwf": scrape_weather_ecmwf,
    "meteoalarm": scrape_weather_meteoalarm,
}

# ------------------------
# Streamlit App
# ------------------------
st.set_page_config(page_title="", layout="centered")

# --- Session state initialization ---
if "geo" not in st.session_state:
    st.session_state.geo = None
if "conditions" not in st.session_state:
    st.session_state.conditions = None
if "forecast" not in st.session_state:
    st.session_state.forecast = None
if "email" not in st.session_state:
    try:
        st.session_state.email, st.session_state.email_pass = get_temp_email()
    except Exception as e:
        st.error(f"Could not create temp email: {e}")
        st.session_state.email, st.session_state.email_pass = None, None
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

# --- If we have geo info ---
if st.session_state.geo:
    geo = st.session_state.geo
    lat, lon = geo["lat"], geo["lon"]

    with st.spinner("Fetching weather data... Please wait"):
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

            elif country.lower() in ["canada"]:
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
                
                if country.lower() in ["australia", "aus"]:
                    # Ask user for state code if not already
                    state = st.text_input("Enter state code (e.g., qld, nsw, vic):", "qld")
                    city = st.text_input("Enter city (e.g., brisbane, sydney):", "brisbane")
                    
                    if state and city:
                        result = scrape_weather_australia(state.lower(), city.lower())
                        if result:
                            st.session_state.conditions = {"city": result["city"], "state": result["state"]}
                            st.session_state.forecast = result["forecasts"]
                        else:
                            st.error("Could not fetch Australian weather data.")
                
        except Exception as e:
                st.error(f"Failed to fetch weather data: {e}")

    # --- Map type selector ---
    st.subheader("Map of Location & Coverage Area")
    map_type = st.selectbox(
        "Choose map type:",
        ["OpenStreetMap", "CartoDB positron", "CartoDB dark_matter"]
    )

    m = folium.Map(location=[float(lat), float(lon)], zoom_start=9, tiles=map_type)
    folium.Marker(
        [lat, lon],
        popup=geo.get("display_name", "Selected Location"),
        tooltip="Your Location"
    ).add_to(m)

    if "area_geo" in st.session_state and st.session_state.area_geo:
        folium.GeoJson(
            st.session_state.area_geo,
            style_function=lambda x: {
                "fillColor": "#3186cc",
                "color": "blue",
                "weight": 2,
                "fillOpacity": 0.25,
            },
            tooltip="Forecast Coverage Area"
        ).add_to(m)

    st_folium(m, width=700, height=500)

    # --- Current Conditions ---
    if st.session_state.conditions:
        if country.lower() in ["united states", "usa", "us"]:
            c = st.session_state.conditions
            st.markdown('<p class="h1">Current Conditions (USA)</p>',unsafe_allow_html=True)
            st.markdown('<hr>',unsafe_allow_html=True)
            st.markdown(
                f"""
                **Weather** {c.get('textDescription', 'N/A')}  
                🌡️ Temperature: {c.get('temperature', {}).get('value', 'N/A')} °C  
                💨 Wind: {c.get('windSpeed', {}).get('value', 'N/A')} m/s {c.get('windDirection', {}).get('value', '')}°  
                💧 Humidity: {c.get('relativeHumidity', {}).get('value', 'N/A')} %  
                ⏱️ Observed: {c.get('timestamp', 'N/A')}
                """
            )
        elif country.lower() == "canada":

            if country.lower() == "canada" and "blocks" in st.session_state.conditions:
                st.subheader("Detailed Weather Data (Canada)")
                st.markdown('<hr>',unsafe_allow_html=True)
            
                for block in st.session_state.conditions["blocks"]:
                    st.markdown(f"### {block['title']}")
                    st.write(block["text"])  # clean text, no iframe, inline
                    st.markdown("---")
                        
            else:
                       st.write(st.session_state.conditions)
                       
        if country.lower() == "australia":
            state = st.text_input("Enter state code (e.g., qld, nsw, vic):", "qld")
            city = st.text_input("Enter city (e.g., brisbane, sydney):", "brisbane")
        
            if st.button("Get Forecast"):
                data = scrape_weather_australia(state, city)
        
                if "error" in data:
                    st.error(data["error"])
                else:
                    st.session_state.conditions = data["conditions"]
                    st.session_state.forecast = data["forecast"]

    # --- Forecast ---
    if st.session_state.forecast:
        st.markdown("<hr>",unsafe_allow_html=True)
        st.markdown("<p class='h2'>Forecast</p>",unsafe_allow_html=True)
        for p in st.session_state.forecast[:7]:
            if isinstance(p, dict):  # USA format
                st.markdown(
                    f"""
                    **{p['name']}**  
                    🌡️ {p['temperature']}°{p['temperatureUnit']}  
                    💨 {p['windSpeed']} {p['windDirection']}  
                    📝 {p['detailedForecast']}
                    """
                )
            else:  # Other countries
                st.write(p)
