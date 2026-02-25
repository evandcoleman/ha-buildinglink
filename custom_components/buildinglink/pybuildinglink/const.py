"""Constants for the BuildingLink API client."""

AUTH_URL = "https://auth.buildinglink.com/connect/token"
LOGIN_URL = "https://www.buildinglink.com/v2/global/login/login.aspx"
OIDC_CALLBACK_URL = "https://www.buildinglink.com/v2/oidc-callback"
API_HOST = "https://api.buildinglink.com"
EVENTLOG_HOST = "https://eventlog-us1.buildinglink.com"
MAINTENANCE_HOST = "https://maintenance-us1.buildinglink.com"
USERS_HOST = "https://users-us1.buildinglink.com"
FRONT_DESK_HOST = "https://frontdeskinstructions-us1.buildinglink.com"
LEGACY_HOST = "https://www.buildinglink.com"

CLIENT_ID = "ios-resident-app"
USER_AGENT = (
    "ResidentApp/3.9.31 "
    "(com.buildinglink.BuildingLink; build:796; iOS 26.3) "
    "Alamofire/5.10.2"
)

DEFAULT_TOKEN_EXPIRY = 900  # 15 minutes
