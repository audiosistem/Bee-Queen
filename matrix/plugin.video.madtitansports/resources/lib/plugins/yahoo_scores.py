import xbmc, xbmcaddon, xbmcgui, requests
from bs4 import BeautifulSoup
from ..plugin import Plugin, run_hook
from tabulate import tabulate

CACHE_TIME = 0  # change to wanted cache time in seconds

sports = [
    "mlb", "nhl", "nba", "nfl",
    "college-football",
    "college-basketball",
    "college-womens-basketball"
]

suffixes = {
    "mlb": "WILDCARD",
    "nhl": "CONFERENCE",
    "nba": "CONFERENCE",
    "nfl": "PLAYOFFS",
    "college-football": "CONFERENCE",
    "college-basketball": "CONFERENCE",
    "college-womens-basketball": "CONFERENCE"
}

headers = {
    "mlb": ['Team', 'W', 'L', 'GB', "Home","Away", "Streak", "L10"],
    "nhl": ['Team', 'Played', 'W', 'L', 'OTL', 'PTS','ROW','HOME','ROAD','L10','STREAK','ODDS'],
    "nba": ['Team', 'W', 'L', 'Pct', 'GB', "Home","DIV","CONF","L10", "STREAK","ODDS"],
    "nfl": ['Team', 'W', 'L', 'Pct',"DIV","HOME","AWAY", "DIV","CONF","L5","STREAK"],

    "college-football": ['Team', 'W', 'L', 'Pct', 'Conf', 'Home', 'Away', 'Streak', 'L5'],
    "college-basketball": ['Team', 'W', 'L', 'Pct', 'Conf', 'Home', 'Away', 'Streak', 'L10'],
    "college-womens-basketball": ['Team', 'W', 'L', 'Pct', 'Conf', 'Home', 'Away', 'Streak', 'L10']
}

def notification(notify_message: str) -> None:
    class Notify(xbmcgui.WindowXMLDialog):
        KEY_NAV_BACK = 92
        TEXTBOX = 300
        CLOSEBUTTON = 302
        
        def onInit(self):
            self.getControl(self.TEXTBOX).setText(notify_message)
            
        def onAction(self, action):
            if action.getId() == self.KEY_NAV_BACK:
                self.Close()
    
        def onClick(self, controlId):
            if controlId == self.CLOSEBUTTON:
                self.Close()

        def Close(self):
            self.close()
    
    d = Notify('notify.xml', xbmcaddon.Addon().getAddonInfo('path'), 'Default', '720p')
    d.doModal()
    del d

def scoreboard(sport):
    res = []

    r = requests.get(f"https://sports.yahoo.com/{sport}/scoreboard").text
    soup = BeautifulSoup(r, "html.parser")

    game_lists = soup.find_all('ul')
    for game_list in game_lists:
        games = game_list.find_all('li')
        for game in games:
            team_elements = game.find_all('span', {'data-tst': 'first-name'})
            if len(team_elements) >= 2:
                team1_name = team_elements[0].text + ' ' + team_elements[0].find_next('div', {'class': 'Fw(n) Fz(12px)'}).text
                team2_name = team_elements[1].text + ' ' + team_elements[1].find_next('div', {'class': 'Fw(n) Fz(12px)'}).text

                score_elements = game.find_all('span', {'class': 'YahooSans Fw(700)! Va(m) Fz(24px)!'})
                score1 = score_elements[0].text.strip() if score_elements else ''
                score2 = score_elements[1].text.strip() if len(score_elements) >= 2 else ''

                inning_element = game.find('div', {'class': 'Ta(end) Cl(b) Fw(b) YahooSans Fw(700)! Fz(11px)!'})
                inning = inning_element.find('span').text.strip()

                network_element = game.find('div', {'class': 'Ta(start) D(b) C(secondary-text)'})
                network = network_element.find_all('span')[-1].text.strip() if network_element else ''

                res.append({
                    'team1': team1_name,
                    'team2': team2_name,
                    'score1': score1,
                    'score2': score2,
                    'inning': inning,
                    'network': network,
                })

    return res

def scoreboard_links(sport):
    res = []

    r = requests.get(f"https://sports.yahoo.com/{sport}/scoreboard").text
    soup = BeautifulSoup(r, "html.parser")

    game_lists = soup.find_all('ul')
    for game_list in game_lists:
        games = game_list.find_all('li')
        for game in games:
            team_elements = game.find_all('span', {'data-tst': 'first-name'})
            if len(team_elements) >= 2:
                team1_name = team_elements[0].text + ' ' + team_elements[0].find_next('div', {'class': 'Fw(n) Fz(12px)'}).text
                team2_name = team_elements[1].text + ' ' + team_elements[1].find_next('div', {'class': 'Fw(n) Fz(12px)'}).text

                score_elements = game.find_all('span', {'class': 'YahooSans Fw(700)! Va(m) Fz(24px)!'})
                score1 = score_elements[0].text.strip() if score_elements else ''
                score2 = score_elements[1].text.strip() if len(score_elements) >= 2 else ''

                inning_element = game.find('div', {'class': 'Ta(end) Cl(b) Fw(b) YahooSans Fw(700)! Fz(11px)!'})
                inning = inning_element.find('span').text.strip() if inning_element else 'n/a'

                network_element = game.find('div', {'class': 'Ta(start) D(b) C(secondary-text)'})
                network = network_element.find_all('span')[-1].text.strip() if network_element else 'Network N/A'
                
                image_element = game.find('img')
                image_source = image_element['src'] if image_element and 'src' in image_element.attrs else 'Image N/A'

                res.append({
                    'title': f'{team1_name} vs {team2_name} | {score1} - {score2} |\nInning: {inning}  TV:{network}',
                    'thumbnail': image_source,
                    'fanart': "https://thumbs.dreamstime.com/b/digital-timing-scoreboard-football-match-team-vs-team-b-strategy-broadcast-graphic-template-presentation-score-game-res-120317998.jpg",
                    'type': 'dir',
                    'search_json': team1_name.lower(),
                    'link': f'https://magnetic.website/MAD_TITAN_SPORTS/SPORTS/LEAGUE/titansports_{sport}.json'
                })

    return res

def scoreboard_table(sport):
    res = scoreboard(sport)
    table_headers = ['Team 1', 'Team 2', 'Score 1', 'Score 2', 'Inning', 'Network']
    table = [list(d.values()) for d in res]
    table_str = tabulate(table, table_headers, tablefmt='grid')
    return table_str

def standings(sport):
    res = []

    response = requests.get(
        f"https://sports.yahoo.com/{sport}/standings/?selectedTab={suffixes[sport]}",
        headers={"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36"}
    )
    soup = BeautifulSoup(response.content, 'html.parser')
    tbody_tags = soup.find_all('tbody')

    def safe_text(el, default='N/A'):
        try:
            return el.text.strip()
        except Exception:
            return default

    def td_get(record_elements, idx, default='N/A'):
        # return text of record_elements[idx] if exists else default
        if idx < len(record_elements):
            return safe_text(record_elements[idx], default)
        return default

    for tbody in tbody_tags:
        # try to derive a heading for this tbody
        heading = None
        try:
            thead = tbody.find_previous_sibling("thead")
            if thead:
                # sometimes heading is in a span, sometimes in a th
                span = thead.find("span")
                if span and span.text.strip():
                    heading = span.text.strip()
                else:
                    th = thead.find("th")
                    heading = th.text.strip() if th and th.text.strip() else None
        except Exception:
            heading = None

        if sport in ["mlb", "nfl"]:
            if heading:
                res.append({'team_name': heading})
        else:
            if heading:
                res.append({'team_name': heading})

        rows = tbody.find_all('tr')
        for row in rows:
            # find team name (anchor with class C(primary-text))
            team_element = row.find('a', class_="C(primary-text)")
            team_name = team_element['title'].strip() if team_element and team_element.has_attr('title') else safe_text(team_element, 'Team N/A')

            # find the relevant <td> cells - may vary in count
            record_elements = row.find_all('td', class_="Bdb(primary-border) Ta(end) Px(cell-padding-x)")
            # fallback: if no cells found with that class try any td
            if not record_elements:
                record_elements = row.find_all('td')

            # Use td_get to safely fetch values by index
            # Provide defaults for each expected column so output shape is stable
            wins = td_get(record_elements, 0, 'N/A')
            losses = td_get(record_elements, 1, 'N/A')
            percentage = td_get(record_elements, 2, 'N/A')
            games_behind = td_get(record_elements, 3, 'N/A')
            home = td_get(record_elements, 4, 'N/A')
            away = td_get(record_elements, 5, 'N/A')
            streak = td_get(record_elements, 6, 'N/A')
            rs = td_get(record_elements, 7, 'N/A')
            ra = td_get(record_elements, 8, 'N/A')
            l10 = td_get(record_elements, 9, 'N/A')
            odds = td_get(record_elements, 10, 'N/A')
            # additional columns if present
            one = td_get(record_elements, 11, 'N/A')
            two = td_get(record_elements, 12, 'N/A')

            # Build per-sport dicts (use previous field names; missing values will be 'N/A')
            if sport == "mlb":
                res.append({
                    'team_name': team_name,
                    'wins': wins,
                    'losses': losses,
                    'games_behind': games_behind,
                    'home': home,
                    'away': away,
                    'streak': streak,
                    'l10': l10,
                    'one': one,
                    'two': two,
                })

            elif sport == "nhl":
                res.append({
                    'team_name': team_name,
                    'wins': wins,
                    'losses': losses,
                    'percentage': percentage,
                    'games_behind': games_behind,
                    'home': home,
                    'away': away,
                    'ra': ra,
                    'l10': l10,
                    'odds': odds,
                    'one': one,
                    'two': two,
                })

            elif sport == "nba":
                res.append({
                    'team_name': team_name,
                    'wins': wins,
                    'losses': losses,
                    'percentage': percentage,
                    'games_behind': games_behind,
                    'home': home,
                    'away': away,
                    'streak': streak,
                    'rs': rs,
                    'odds': odds,
                    'one': one,
                    'two': two,
                })

            elif sport == "nfl":
                res.append({
                    'team_name': team_name,
                    'wins': wins,
                    'losses': losses,
                    'percentage': percentage,
                    'games_behind': games_behind,
                    'streak': streak,
                    'rs': rs,
                    'ra': ra,
                    'l10': l10,
                    'odds': odds,
                    'one': one,
                    'two': two,
                })
            else:
                # default generic row
                res.append({
                    'team_name': team_name,
                    'wins': wins,
                    'losses': losses,
                    'percentage': percentage,
                    'games_behind': games_behind,
                    'home': home,
                    'away': away,
                    'streak': streak,
                    'rs': rs,
                    'ra': ra,
                    'l10': l10,
                    'odds': odds,
                    'one': one,
                    'two': two,
                })

    return res

    
def standings_table(sport):
    res = standings(sport)
    table = [list(r.values()) for r in res]
    table_str = tabulate(table, headers[sport], tablefmt='grid')
    return table_str


class YahooScores(Plugin):
    name = "yahoo_scores" 
    priority = 100

    def process_item(self, item):
        if self.name in item:
            sport = item[self.name]
            thumbnail = item.get("thumbnail", "")
            fanart = item.get("fanart", "")
            list_item = xbmcgui.ListItem(item.get("title", item.get("name", "")), offscreen=True)
            list_item.setArt({
                "thumb": "https://static.vecteezy.com/system/resources/thumbnails/010/174/501/small/3d-text-effect-alphabet-and-number-3d-text-effect-free-png.png",
                "fanart": "https://thumbs.dreamstime.com/b/digital-timing-scoreboard-football-match-team-vs-team-b-strategy-broadcast-graphic-template-presentation-score-game-res-120317998.jpg"
            })
            item["list_item"] = list_item
            item["is_dir"] = True
            item["link"] = self.name + "/" + sport
            return item
    
    def routes(self, plugin):
        @plugin.route(f"/{self.name}/scoreboard/<sport>")
        def yahoo_scoreboard(sport: str):
            res = scoreboard_table(sport)
            notification(res)
        
        @plugin.route(f"/{self.name}/standings/<sport>")
        def yahoo_standings(sport: str):
            res = standings_table(sport)
            notification(res)
        
        @plugin.route(f"/{self.name}/links/<sport>")
        def yahoo_links(sport: str):
            jen_list = scoreboard_links(sport)
            jen_list = [run_hook("process_item", item) for item in jen_list]
            jen_list = [run_hook("get_metadata", item) for item in jen_list]
            run_hook("display_list", jen_list)

