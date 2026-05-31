from .api import tmdb_cached, TTL_DETAILS


def get_person_details(person_id):
    return tmdb_cached(f'person/{person_id}', ttl=TTL_DETAILS)


def get_person_credits(person_id):
    return tmdb_cached(f'person/{person_id}/combined_credits', ttl=TTL_DETAILS)


def search_person(name):
    return tmdb_cached('search/person', {'query': name}, ttl=TTL_DETAILS)
