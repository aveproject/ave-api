SERVICE_NAME = "AVE Reference API"
STANDARD_URL = "https://aveproject.org"
REPO_URL = "https://github.com/aveproject/ave"
API_VERSION = "1"

MSG_RECORD_NOT_FOUND = "No record found for ave_id {ave_id}"
MSG_MITIGATION_NOT_FOUND = "No mitigation object found for ave_id {ave_id}"
MSG_INITIAL_FETCH_FAILED = (
    "Initial cache fetch failed, starting with an empty cache, "
    "will retry on first request: {error}"
)
MSG_REFRESH_FAILED = (
    "Cache refresh failed, continuing to serve the last known-good cache: {error}"
)
MSG_INDEX_REFRESH_FAILED = (
    "Index could not refresh the cache, reporting the last known state: {error}"
)
MSG_LATEST_SHA256_MISMATCH = (
    "The latest records file does not match the sha256 in its manifest; "
    "the two were probably fetched from different commits"
)
MSG_LATEST_COUNT_MISMATCH = (
    "The latest records file does not hold the record_count in its manifest"
)
MSG_RELEASE_NOT_FOUND = (
    "No catalog release {tag} with ave-records.json, ave-records.manifest.json "
    "and SHA256SUMS; see /v1/releases for the releases that can be pinned"
)
MSG_RELEASE_UNVERIFIED = "Release {tag} failed verification and was not used: {reason}"
MSG_RELEASE_FETCH_FAILED = "Release {tag} could not be downloaded: {error}"
MSG_RELEASES_UNAVAILABLE = (
    "The list of releases could not be fetched from GitHub and none is cached yet"
)
MSG_RELEASES_REFRESH_FAILED = (
    "Releases refresh failed, continuing to serve the last known list: {error}"
)
