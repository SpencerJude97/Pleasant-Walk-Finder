import requests

f = open("API_Key.txt")
API_Key = f.read()
f.close()

response = requests.get("https://weather.visualcrossing.com/VisualCrossingWebServices/rest/services/timeline/bath,uk?key=" + API_Key)
print(response.status_code)
print(response.json())