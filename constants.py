SERVICE_NAME = "AVE Reference API"
STANDARD_URL = "https://aveproject.org"
REPO_URL = "https://github.com/aveproject/ave"

MSG_RECORD_NOT_FOUND = "No record found for ave_id {ave_id}"
MSG_MITIGATION_NOT_FOUND = "No mitigation object found for ave_id {ave_id}"
MSG_INITIAL_FETCH_FAILED = (
    "Initial cache fetch failed, starting with an empty cache, "
    "will retry on first request: {error}"
)
MSG_REFRESH_FAILED = (
    "Cache refresh failed, continuing to serve the last known-good cache: {error}"
)
