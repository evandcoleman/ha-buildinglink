"""Constants for the BuildingLink API client."""

AUTH_URL = "https://auth.buildinglink.com/connect/token"
AUTHORIZE_URL = "https://auth.buildinglink.com/connect/authorize"
AUTH_HOST = "https://auth.buildinglink.com"
API_HOST = "https://api.buildinglink.com"
EVENTLOG_HOST = "https://eventlog-us1.buildinglink.com"
MAINTENANCE_HOST = "https://maintenance-us1.buildinglink.com"
USERS_HOST = "https://users-us1.buildinglink.com"
FRONT_DESK_HOST = "https://frontdeskinstructions-us1.buildinglink.com"
LEGACY_HOST = "https://www.buildinglink.com"

CLIENT_ID = "ios-resident-app"
REDIRECT_URI = "com.buildinglink.resident://oidc-callback"
SCOPE = "offline_access internal_resident_app_apis openid uuids"

# Static keys embedded in the official iOS app (identify the client, not the user).
API_KEY = "hylwvvmjdgc45mt9kab1agriyvuh0nig9qx8djmu"  # *-us1.buildinglink.com
APIM_SUBSCRIPTION_KEY = "44bfe3e668e84af5b21ed663a5448595"  # api.buildinglink.com
USER_AGENT = (
    "ResidentApp/3.9.45 "
    "(com.buildinglink.BuildingLink; build:796; iOS 26.3) "
    "Alamofire/5.10.2"
)

DEFAULT_TOKEN_EXPIRY = 900  # 15 minutes
