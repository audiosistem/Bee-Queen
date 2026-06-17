# -*- coding: utf-8 -*-
"""Read-only browse endpoints: trending, related, search, certifications, recommendations, comments.

These are thin pagination/caching wrappers around `get_trakt`/`call_trakt`. The
only stateful piece is `trakt_recommendations`, which is authed and caches via
the trakt cache.
"""

from caches import trakt_cache
from caches.lists_cache import lists_cache_object
from caches.main_cache import cache_object
from modules.utils import get_datetime, replace_html_codes
from modules.utils import jsondate_to_datetime as js2date

from .core import call_trakt, get_trakt

__all__ = [
	"trakt_anime_certifications",
	"trakt_anime_most_favorited",
	"trakt_anime_most_watched",
	"trakt_anime_search",
	"trakt_anime_trending",
	"trakt_anime_trending_recent",
	"trakt_comments",
	"trakt_movies_most_favorited",
	"trakt_movies_most_watched",
	"trakt_movies_related",
	"trakt_movies_top10_boxoffice",
	"trakt_movies_trending",
	"trakt_movies_trending_recent",
	"trakt_recommendations",
	"trakt_tv_certifications",
	"trakt_tv_most_favorited",
	"trakt_tv_most_watched",
	"trakt_tv_related",
	"trakt_tv_search",
	"trakt_tv_trending",
	"trakt_tv_trending_recent",
]


def trakt_movies_related(imdb_id):
	string = "trakt_movies_related_%s" % imdb_id
	params = {"path": "movies/%s/related?extended=full", "path_insert": imdb_id, "params": {"limit": 20}}
	return lists_cache_object(get_trakt, string, params)


def trakt_movies_trending(page_no):
	string = "trakt_movies_trending_%s" % page_no
	params = {"path": "movies/trending/%s", "params": {"limit": 20}, "page_no": page_no}
	return lists_cache_object(get_trakt, string, params)


def trakt_movies_trending_recent(page_no):
	current_year = get_datetime().year
	years = "%s-%s" % (str(current_year - 1), str(current_year))
	string = "trakt_movies_trending_recent_%s" % page_no
	params = {"path": "movies/trending/%s", "params": {"limit": 20, "years": years}, "page_no": page_no}
	return lists_cache_object(get_trakt, string, params)


def trakt_movies_top10_boxoffice(page_no):
	string = "trakt_movies_top10_boxoffice"
	params = {"path": "movies/boxoffice/%s", "pagination": False}
	return lists_cache_object(get_trakt, string, params)


def trakt_movies_most_watched(page_no):
	string = "trakt_movies_most_watched_%s" % page_no
	params = {"path": "movies/watched/daily/%s", "params": {"limit": 20}, "page_no": page_no}
	return lists_cache_object(get_trakt, string, params)


def trakt_movies_most_favorited(page_no):
	string = "trakt_movies_most_favorited%s" % page_no
	params = {"path": "movies/favorited/daily/%s", "params": {"limit": 20}, "page_no": page_no}
	return lists_cache_object(get_trakt, string, params)


def trakt_recommendations(media_type):
	string = "trakt_recommendations_%s" % (media_type)
	params = {
		"path": "/recommendations/%s",
		"path_insert": media_type,
		"with_auth": True,
		"params": {"limit": 50, "ignore_collected": "true", "ignore_watchlisted": "true"},
		"pagination": False,
	}
	return trakt_cache.cache_trakt_object(get_trakt, string, params)


def trakt_tv_related(imdb_id):
	string = "trakt_tv_related_%s" % imdb_id
	params = {"path": "shows/%s/related?extended=full", "path_insert": imdb_id, "params": {"limit": 20}}
	return lists_cache_object(get_trakt, string, params)


def trakt_tv_trending(page_no):
	string = "trakt_tv_trending_%s" % page_no
	params = {"path": "shows/trending/%s", "params": {"limit": 20}, "page_no": page_no}
	return lists_cache_object(get_trakt, string, params)


def trakt_tv_trending_recent(page_no):
	current_year = get_datetime().year
	years = "%s-%s" % (str(current_year - 1), str(current_year))
	string = "trakt_tv_trending_recent_%s" % page_no
	params = {"path": "shows/trending/%s", "params": {"years": years, "limit": 20}, "page_no": page_no}
	return lists_cache_object(get_trakt, string, params)


def trakt_tv_most_watched(page_no):
	string = "trakt_tv_most_watched_%s" % page_no
	params = {"path": "shows/watched/daily/%s", "params": {"genres": "-anime", "limit": 20}, "page_no": page_no}
	return lists_cache_object(get_trakt, string, params)


def trakt_tv_most_favorited(page_no):
	string = "trakt_tv_most_favorited_%s" % page_no
	params = {"path": "shows/favorited/daily/%s", "params": {"genres": "-anime", "limit": 20}, "page_no": page_no}
	return lists_cache_object(get_trakt, string, params)


def trakt_tv_certifications(certification, page_no):
	string = "trakt_tv_certifications_%s_%s" % (certification, page_no)
	params = {"path": "shows/collected/all%s", "params": {"genres": "-anime", "certifications": certification, "limit": 20}, "page_no": page_no}
	return lists_cache_object(get_trakt, string, params)


def trakt_tv_search(query, page_no):
	def _process(dummy_arg):
		return call_trakt("search/show", params={"genres": "-anime", "query": query, "limit": 20}, with_auth=False, pagination=True, page_no=page_no)

	string = "trakt_tv_search_%s_%s" % (query, page_no)
	return cache_object(_process, string, "dummy_arg", False, 24)


def trakt_anime_trending(page_no):
	string = "trakt_anime_trending_%s" % page_no
	params = {"path": "shows/trending/%s", "params": {"genres": "anime", "limit": 20}, "page_no": page_no}
	return lists_cache_object(get_trakt, string, params)


def trakt_anime_trending_recent(page_no):
	current_year = get_datetime().year
	years = "%s-%s" % (str(current_year - 1), str(current_year))
	string = "trakt_anime_trending_recent_%s" % page_no
	params = {"path": "shows/trending/%s", "params": {"genres": "anime", "limit": 20, "years": years}, "page_no": page_no}
	return lists_cache_object(get_trakt, string, params)


def trakt_anime_most_watched(page_no):
	string = "trakt_anime_most_watched_%s" % page_no
	params = {"path": "shows/watched/daily/%s", "params": {"genres": "anime", "limit": 20}, "page_no": page_no}
	return lists_cache_object(get_trakt, string, params)


def trakt_anime_most_favorited(page_no):
	string = "trakt_anime_most_favorited_%s" % page_no
	params = {"path": "shows/favorited/daily/%s", "params": {"genres": "anime", "limit": 20}, "page_no": page_no}
	return lists_cache_object(get_trakt, string, params)


def trakt_anime_certifications(certification, page_no):
	string = "trakt_anime_certifications_%s_%s" % (certification, page_no)
	params = {"path": "shows/collected/all%s", "params": {"certifications": certification, "genres": "anime", "limit": 20}, "page_no": page_no}
	return lists_cache_object(get_trakt, string, params)


def trakt_anime_search(query, page_no):
	def _process(dummy_arg):
		return call_trakt("search/show", params={"genres": "anime", "query": query, "limit": 20}, with_auth=False, pagination=True, page_no=page_no)

	string = "trakt_anime_search_%s_%s" % (query, page_no)
	return cache_object(_process, string, "dummy_arg", False, 24)


def trakt_comments(media_type, imdb_id):
	def _process(foo):
		data = get_trakt(params)
		for count, item in enumerate(data, 1):
			try:
				rating = "%s/10 - " % item["user_rating"] if item["user_rating"] else ""
				comment = template % (
					count,
					rating,
					item["user"]["username"].upper(),
					js2date(item["created_at"], date_format, True).strftime("%d %B %Y"),
					replace_html_codes(item["comment"]),
				)
				if item["spoiler"]:
					comment = spoiler_template + comment
				all_comments_append(comment)
			except (KeyError, TypeError, AttributeError):
				pass
		return all_comments

	all_comments = []
	all_comments_append = all_comments.append
	template, spoiler_template, date_format = (
		"[B]%02d. [I]%s%s - %s[/I][/B][CR][CR]%s",
		"[B][COLOR red][CONTAINS SPOILERS][/COLOR][CR][/B]",
		"%Y-%m-%dT%H:%M:%S.000Z",
	)
	media_type = "movies" if media_type in ("movie", "movies") else "shows"
	string = "trakt_comments_%s %s" % (media_type, imdb_id)
	params = {"path": "%s/%s/comments", "path_insert": (media_type, imdb_id), "params": {"limit": 1000, "sort": "likes"}, "pagination": False}
	return cache_object(_process, string, "foo", False, 168)
