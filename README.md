[![PyPI version](https://badge.fury.io/py/voobly.svg)](https://badge.fury.io/py/voobly)

# python-voobly

Python 3 API for [Voobly](http://www.voobly.com), an online gaming platform. Makes requests to Voobly's public HTTP-based API.

## Prerequisites

- Active Voobly account
- API key provided by Voobly

## Install

`pip install voobly`

## Usage

See the [Voobly API documentation](http://www.voobly.com/pages/view/147/External-API-Documentation) for available parameters.

```python
import datetime
import voobly

# Establish a session. Use the API key provided by Voobly.
session = voobly.get_session("<your-api-key>", cache_expiry=datetime.timedelta(days=1))

# Validate API key
assert voobly.validate_key(session) == True

# Get top accounts on AoC "RM 1v1" ladder
top_accounts = voobly.get_ladder(session, 131)  # returns list

# Get lobby information for AoC
lobbies = voobly.get_lobbies(session, 13)  # returns list

# Look up a user ID based on username
uid = vooby.find_user("TheViper")  # returns 123211439

# Look up user IDs for multiple usernames
results = voobly.find_users(session, "TheViper", "MBLAoC")  # returns list

# Get user profile for "TheViper"
profile = voobly.get_user(session, 123211439)

# The following methods are helpers built from the previous.

# Get a user profile & ladder info based on username
user = voobly.user("TheViper", ladder_ids=[131, 132])  # returns dict

# Get a list of ladder IDs for AoC
ladders = voobly.ladders(session, 13)  # returns list
```

## Caveats

- A mapping of ladder names to ladder IDs is not available via the API.
- A mapping of game names to game IDs is not available via the API.
- `get_ladder` with a uid or uidlist does not return *global* ranking, only within results.


## Exception Handling

Exceptions raise a `VooblyError`, including connectivity issues, bad API key, and malformed results.

## Caching

To reduce load on the Voobly API, this module includes automatic HTTP request caching. The `cache_expiry` parameter of `get_session` determines how long requests are cached. This caching mechanism can be disabled if an external cache is implemented. Please use a maximum `cache_expiry` for your usecase. The default `cache_expiry` is 7 days.

## Development

### Lint

`tox`

### Release

`make release`

### Contributions

Contributions are welcome. Please submit a PR that passes `tox`.

## Disclaimer
Not affiliated with Voobly.
