import requests
from geopy.geocoders import Nominatim


# weather features the user can prioritise when finding a walk
preferences = {
    "temp": {
        "name": "Temperature",      
        "value": 20,  # user's chosen preferred value
        "weight": 0.5,  # user's chosen importance of the feature
        "scale": 10.0,  # constant value to normalise feature error calculations
        "unit": "°C"
    },
    "humidity": {
        "name": "Humidity",
        "value": 40,
        "weight": 0.5,
        "scale": 2.0,
        "unit": "%"
    }
}

settings = {
    "unit_system": "uk",    
    "algorithm_steps": 3,   # number of steps taken in walk-finder algorithm
    "algorithm_distance": 0.1   # distance of potential locations from initial location in walk-finder algorithm
}

# the features the user assigns a non-zero weighting to
elements = []


# get user's API key
with open("API_Key.txt") as f:
    API_Key = f.read().strip()


# main menu displayed on startup
def Menu():

    # user's choice of action from the menu
    menu_option = None

    while menu_option != 3:

        menu_option = None
        
        # possible actions
        print("\n         MENU")
        print("[1] Set weather preferences")
        print("[2] Find a walk")
        print("[3] Quit")

        try:
            menu_option = int(input("Option: "))
        except ValueError:
            input("\nEnter a number.\n")        

        if menu_option == 1:
            Set_Preferences()
        elif menu_option == 2:
            Find_Walk()


# menu to allow user to view and alter feature values and weightings
def Set_Preferences():

    # user's choice of action from preferences menu
    pref_option = None

    while pref_option != 4:
        
        pref_option = None

        # current feature values and weightings
        print(f"\nCurrent preferences:")
        print(f"  Temperature: {preferences['temp']['value']} (weighting: {preferences['temp']['weight']})")
        print(f"  Humidity: {preferences['humidity']['value']} (weighting: {preferences['humidity']['weight']})")
        input()

        # possible actions - alterations user can make
        print("Choose a preference to change:")
        print("[1] Temperature")
        print("[2] Humidity")
        print("[3] Weightings")
        print("[4] Return")
        
        try:
            pref_option = int(input("Option: "))
        except ValueError:
            input("\nEnter a number.")

        if pref_option == 1:
            try:
                preferences["temp"]["value"] = float(input("\nChoose a preferred temperature (°C) for walks. "))
            except ValueError:
                input("\nEnter a temperature.")   

        if pref_option == 2:
            try:
                preferences["humidity"]["value"] = float(input("\nChoose a preferred humidity for walks. "))
            except ValueError:
                input("\nEnter a humidity.")  
            
        if pref_option == 3:
            try:
                # user chooses temperature weighting
                preferences["temp"]["weight"] = float(input("\nChoose a weighting for temperature (out of 1.0). "))
                # humidity is automatically weighted such that weightings sum to one  
                preferences["humidity"]["weight"] = 1 - preferences["temp"]["weight"]
                input(f"The weighting for humidity will be {preferences['humidity']['weight']}")
                Set_Elements()
            except ValueError:
                input("\nEnter a weighting.")            
            
        print()
    


def Set_Elements():
    # assigns all features with non-zero weightings to `elements`
    elements.clear()
    for name, item in preferences.items():
        if item["weight"] != 0:
            elements.append(name)


# find the best location for a walk given the user's location and weather preferences
def Find_Walk():

    user_town = str(input("\nWhich town or city are you in? "))
    user_country = str(input("Which country are you in? "))    

    # get weather data for user's current location
    response = Request(user_town, user_country)
    
    if response.status_code != 200:
        # print error message and return to main menu if response was not successfully processed
        print()
        input(response.text)
        print()
        return

    # convert returned data to dict
    data = response.json()

    # direction last selected
    prev = None
    
    for _ in range(settings["algorithm_steps"]):
        # apply one step of algorithm, replacing previous data and direction with that of new location
        data, prev = Check_Potentials(data, prev)

    # get name of settlement at location in final response output
    geolocator = Nominatim(user_agent="settlement_selector")
    location = geolocator.reverse((data["latitude"], data["longitude"]), exactly_one=True)
    address = location.raw["address"]
    settlement = (
        address.get("city")
        or address.get("town")
        or address.get("village")
        or address.get("hamlet")
    )

    # print name of settlement that matches user's preference, listing values of relevant (non-zero weighted) features
    print(f"\nYou could go on a walk in {settlement} where:")
    for elem in elements:
        elem_data = preferences[elem]
        print(f"  {elem_data['name']}: {data['days'][0][elem]}{elem_data['unit']}")
    input()


# requests relevant data from API, using either settlement/country names or lat/lng values
def Request(town_or_lat, country_or_lng):

    # convert list of non-zero weighted features to string for use in request url
    str_elements = ""
    for name, item in preferences.items():
        if item["weight"] != 0:
            str_elements += (f"{name},")
    str_elements = str_elements[:-1]

    units = settings["unit_system"]

    # request data at given location, for today's date, for relevant features
    return requests.get(f"https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline/{town_or_lat},{country_or_lng}/today?key={API_Key}&unitGroup={units}&include=current&elements={str_elements}")


# a single step of the walk-finder algorithm
def Check_Potentials(base, prev=None):

    # if initial location was best at last step, just return initial location
    if prev == 0:
        return (base, 0)
    
    lat = base["latitude"]
    lng = base["longitude"]

    # initialise list of weather data for potential locations with that of initial location
    potentials = [base]

    dist = settings["algorithm_distance"]

    # append data for locations in four cardinal directions from initial location
    if prev != 2:   # do not check the direction of the previous step's initial location
        potentials.append(Request(lat-dist, lng).json())
    if prev != 1:
        potentials.append(Request(lat+dist, lng).json())
    if prev != 4:
        potentials.append(Request(lat, lng-dist).json())
    if prev != 3:
        potentials.append(Request(lat, lng+dist).json())

    # index of best location in `potentials`, initialised as that of initial location
    best = 0
    # the current best cost value, initialised as that of initial location
    best_cost = Cost(potentials[0])

    # get index and cost of best location
    for i in (range(1, len(potentials))):
        cost = Cost(potentials[i])
        if cost < best_cost:
            best_cost = cost
            best = i

    return (potentials[best], best)


def Cost(data):
    cost = 0

    for elem in elements:
        # the data for the location currently being considered
        elem_data = preferences[elem]
        # sum of weighted, normalised error values for all considered features
        cost += elem_data["weight"] * abs(data["days"][0][elem] - elem_data["value"]) / elem_data["scale"]
        
    return cost


# initialise list of non-zero weighted features
Set_Elements()

# display main menu
Menu()
