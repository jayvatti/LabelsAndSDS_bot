from os import access

from msal import ConfidentialClientApplication
import requests


app = ConfidentialClientApplication(
    client_id="34d78561-afe4-4890-85fc-e2b042be0176",
    client_credential="nmV8Q~8qRT7quSpKiY_OaAZvpWfZCtQkpF7KpciG",
    authority="https://login.microsoftonline.com/4130bd39-7c53-419c-b1e5-8758d6d63f21"
)

scopes = ["https://graph.microsoft.com/.default"]

flow = app.initiate_device_flow(scopes=scopes)
if "user_code" not in flow:
    raise ValueError("Failed to create device flow. Error: {}".format(flow))

print(flow["message"])

result = app.acquire_token_by_device_flow(flow)

if "access_token" in result:
    print("YAYY")
else:
    print("Authentication failed.")
    print("Error:", result.get("error"))
    print("Description:", result.get("error_description"))
