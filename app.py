from flask import Flask, render_template, request
import requests
import populartimes
from datetime import datetime
import keys

app = Flask(__name__)

API_KEY = keys.API_KEY

def get_coordinates(address):
    """Get latitude and longitude for a given address."""
    address_url = f"https://maps.googleapis.com/maps/api/geocode/json?address={address}&key={API_KEY}"
    response = requests.get(address_url)
    data = response.json()

    if data['status'] == 'OK':
        location = data['results'][0]['geometry']['location']
        return location['lat'], location['lng']
    else:
        print("Error fetching coordinates:", data.get('error_message', 'Unknown error'))
        return None, None

def get_nearby_restaurants(lat, lng):
    """Get a list of nearby restaurants for given coordinates."""
    places_url = f"https://maps.googleapis.com/maps/api/place/nearbysearch/json?location={lat},{lng}&radius=3000&type=bar&key={API_KEY}"
    response = requests.get(places_url)
    data = response.json()

    if data['status'] == 'OK':
        restaurants = [
            {
                'name': place['name'],
                'address': place.get('vicinity', 'N/A'),
                'lat': place['geometry']['location']['lat'],
                'lng': place['geometry']['location']['lng'],
                'place_id': place.get('place_id')  # Include place_id
            }
            for place in data['results']
        ]
        return restaurants
    else:
        print("Error fetching Places:", data.get('error_message', 'Unknown error'))
        return []

def get_place_id(name):
    """Get the place_id for a given restaurant name."""
    find_place_url = f"https://maps.googleapis.com/maps/api/place/findplacefromtext/json?input={name}&inputtype=textquery&fields=place_id&key={API_KEY}"
    response = requests.get(find_place_url)
    data = response.json()

    if data['status'] == 'OK' and data.get('candidates'):
        return data['candidates'][0]['place_id']
    else:
        print("Error fetching place_id:", data.get('error_message', 'Unknown error'))
        return None

def get_place_details(name, lat, lng):
    """Get additional details about a place using the Google Places API."""
    place_id = get_place_id(name)
    if not place_id:
        return None

    # Step 2: Use Place Details API to get detailed information
    details_url = f"https://maps.googleapis.com/maps/api/place/details/json?place_id={place_id}&fields=name,rating,formatted_address,opening_hours,secondary_opening_hours&key={API_KEY}"
    details_response = requests.get(details_url)
    details_data = details_response.json()

    if details_data['status'] == 'OK' and details_data.get('result'):
        place = details_data['result']

        # Extract happy hour information if available
        happy_hour = None
        if 'secondary_opening_hours' in place:
            for secondary_hours in place['secondary_opening_hours']:
                if secondary_hours.get('type') == 'HAPPY_HOUR':
                    happy_hour = secondary_hours.get('weekday_text', [])

        return {
            'name': place.get('name'),
            'rating': place.get('rating', 'N/A'),
            'address': place.get('formatted_address', 'N/A'),
            'opening_hours': place.get('opening_hours', {}).get('weekday_text', []),
            'happy_hour': happy_hour,
            'place_id': place_id
        }
    else:
        print("Error fetching place details:", details_data.get('error_message', 'Unknown error'))
        return None

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        user_address = request.form["address"]
        lat, lng = get_coordinates(user_address)

        if lat is not None and lng is not None:
            restaurants = get_nearby_restaurants(lat, lng)
            return render_template("index.html", restaurants=restaurants, address=user_address)
        else:
            return render_template("index.html", error="Could not fetch coordinates for the given address.")
    
    return render_template("index.html", restaurants=None)

@app.route("/details")
def details():
    """Render the details page for a specific restaurant."""
    name = request.args.get("name")
    address = request.args.get("address")
    lat = request.args.get("lat")
    lng = request.args.get("lng")
    place_id = request.args.get("place_id")  # Ensure place_id is passed

    if not place_id:
        place_id = get_place_id(name)
        if not place_id:
            return "Error: Could not fetch place_id for the given name.", 400

    # Fetch additional details using the Google Places API
    place_details = get_place_details(name, lat, lng)

    # Fetch popularity data using populartimes
    try:
        popularity_data = populartimes.get_id(API_KEY, place_id)
    except populartimes.crawler.PopulartimesException as e:
        print(f"Error fetching popularity data: {e}")
        popularity_data = None

    # Get the current day and hour
    current_time = datetime.now()
    current_day_index = current_time.weekday()  # 0 = Monday, 1 = Tuesday, ..., 6 = Sunday
    current_hour = current_time.hour

    # Extract today's popularity data
    today_popularity = None
    is_most_popular = False
    if popularity_data and "populartimes" in popularity_data:
        today_popularity = popularity_data["populartimes"][current_day_index]["data"]
        # Check if the current hour is the most popular time of the day
        if today_popularity and current_hour < len(today_popularity):
            is_most_popular = today_popularity[current_hour] == max(today_popularity)

    return render_template(
        "details.html",
        name=name,
        address=address,
        lat=lat,
        lng=lng,
        api_key=API_KEY,
        place_details=place_details,
        popularity_data=popularity_data,
        today_popularity=today_popularity,
        current_hour=current_hour,
        is_most_popular=is_most_popular,
        current_day_index=current_day_index,
        current_time=current_time
    )

if __name__ == "__main__":
    app.run(debug=True)