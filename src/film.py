"""
    For getting information about a film on Letterboxd
        For example, year, genre
"""

# Local
from exceptions import LunaboxdError
import letterboxd
from session import LunaboxdSession
import util

# Web scraping
from bs4 import BeautifulSoup
import requests

# Collections
from collections import defaultdict

# Type validation
from typing import Self

# Data
import re

# Math
from scipy.stats import beta # Used for bayesian average calculation

# Debugging
import logging


# --- Rich --- START

from rich.console import Console
from rich.table import Table

console = Console(theme = util.style_theme)

# --- Rich --- END


@util.custom_repr
class Film:

    # The prefix to the short_link to a film's page
    short_link_prefix = 'https://boxd.it/'

    def __init__(self, path: str) -> None:
        """
        > Parameters <
        --------------
        :path:
            the path to the film on Letterboxd (e.g. black-swan)
        
        NOTE: sometimes, these paths have years in
        For example if there are two films named Boat, one may have the path boat,
        while the other may have the path boat-2013, representing the year of its release
        """
        self.session = LunaboxdSession.load()

        # Path to the film
        self.path = letterboxd.string_to_suburl(path)

        # Get the soups from which information about the film can be extracted
        self.get_soups()

    @classmethod
    def from_id(cls, film_id: int) -> Self:
        """ 
        ** Alternative Constructor ** 
        Return an instance of Film given that film's URI
            (the unique characters in its short link)
        """
        # When you go the this url:
            # /film/film:101
            # Where 101 is the film's id
            # Then you will be automatically redirected to the film's page with the normal url (e.g. '/film/frozen/')
        return cls(path = f"film:{film_id}")
    
    @classmethod
    def from_uri(cls, film_uri: str) -> Self:
        """
        ** Alternative Constructor **
        Return an instance of Film given that film's URI
            (the unique characters in its short link)
        """
        response = requests.get(f"{cls.short_link_prefix}{film_uri}")
        pattern = r"https:\/\/letterboxd\.com\/film\/([^/]+)\/"
        suburl = util.find_one(pattern, response.url)
        return cls(path = suburl)

    def __str__(self):

        # --- Define functions frequently used in string ---

        # Round integer to 2 decimal places
        dp_two = lambda x: f"{x:.2f}" if isinstance(x, int|float) else x
        
        # Display a shortened version of the array if necessary
        preview_arr = util.preview_array

        # Display numbers with a comma as 1,000 separator
        thous_sep = util.thousand_separator
        
        # --- Return string ---

        return f'''\
        \n\tPath: {self.path}\
        \n\tShort: {self.short_link}\
        \n\tId_: {self.id_}\
        \n\tName: {self.name}\
        \n\tRelease_Year: {self.year}\
        \n\tGenres: {preview_arr(self.genres)}\
        \n\tLength: {letterboxd.mins_to_formatted_time(len(self))}\
        \n\tDescription: {self.description}\
        \n\tLanguages: {preview_arr(self.language)}\
        \n\tRegions: {preview_arr(self.region)}\
        \n\tDirectors: {preview_arr(self.crew["Director"])}\
        \n\tProducers: {preview_arr(self.crew["Producer"])}\
        \n\tWriters: {preview_arr(self.crew["Writer"])}\
        \n\tStudios: {preview_arr(self.studio)}\
        \n\tCast: {preview_arr(self.cast)}\
        \n\tViews: {thous_sep(self.views)}\
        \n\tLikes: {thous_sep(self.likes)}\
        \n\tLists: {thous_sep(self.lists)}\
        \n\tFans: {thous_sep(self.fans)}\
        \n\tRatings: | L: {dp_two(self.rating_letterboxd)} | T: {dp_two(self.rating_true)} | B: {dp_two(self.rating_bayesian)} | I: {self.rating_ironic}\
        \n\tRatings_Friends: | B: {dp_two(self.rating_friends_bayesian)}\
        \n\tPoster: {bool(self.img_poster)}\
        \n\tBanner: {bool(self.img_banner)}\
        \n\tAlternative Titles: {preview_arr(self.alternative_titles)}'''
    
    def display_table(self) -> None:
        """ Displays film information in a table """

        # Aliases for utility functions
        preview_array = util.preview_array
        grader = letterboxd.rating_grader
        
        # Create the table and main columns
        table = Table(show_header = True, style = 'purple', show_lines = True)
        table.add_column('', justify = 'right', style = f'info')
        table.add_column(self.pretty_name)

        # Fill table rows with attributes
        table.add_row('id', f"{self.id_}")
        table.add_row('short', self.short_link)
        table.add_row('year', str(self.year))
        table.add_row('genres', ', '.join(self.genres))
        table.add_row('length', letterboxd.mins_to_formatted_time(len(self)))
        table.add_row('description', self.description_short())
        table.add_row('languages', ', '.join(self.language))
        table.add_row('Region(s)', ', '.join(self.region))
        table.add_row('Studio(s)', ', '.join(self.studio))
        table.add_row('Producer(s)', f"{preview_array(self.crew.get('Producer'))}")
        table.add_row('Director(s)', f"{preview_array(self.crew.get('Director'))}")
        table.add_row('Writer(s)', f"{preview_array(self.crew.get('Writer'))}")
        table.add_row('Actor(s)', f"{preview_array(self.cast)}")
        table.add_row('Views', letterboxd.int_to_shortnum(self.views))
        table.add_row('Likes', letterboxd.int_to_shortnum(self.likes))
        table.add_row('Lists', letterboxd.int_to_shortnum(self.lists))
        table.add_row('Fans', letterboxd.int_to_shortnum(self.fans))
        table.add_row('Ratings', f"L: {grader(self.rating_letterboxd)} | T: {grader(self.rating_true)} | B: {grader(self.rating_bayesian)} | F: {grader(self.rating_friends_bayesian)} | I: {self.rating_ironic}")

        # Print the table to screen
        console.print(table)

    def __index__(self) -> int:
        return self.id_

    def __hash__(self):
        return hash(self.__index__())

    def __len__(self) -> int:
        return self.length

    """
    ** Suburls
    """

    @property
    def suburl_film_main(self) -> str:
        """ Returns the suburl of the film page, which contains most attributes we can scrape """
        return f"film/{self.path}/"

    @property
    def suburl_film_stats(self) -> str:
        """ 
        Returns the suburl for a stats page containing information 
        about the film's number of views, likes, and appearances in lists 
        """
        return f"esi/film/{self.path}/stats"

    @property
    def suburl_film_rating(self) -> str:
        """ 
        Returns the suburl for a stats page containing information 
        about the film's rating
        """
        return f"csi/film/{self.path}/rating-histogram/"

    @property
    def suburl_film_rating_friends(self) -> str:
        """ 
        Returns the suburl for a stats page containing information 
        about the film's rating amongst your friends
        """
        return f"csi/film/{self.path}/friend-activity/?esiAllowUser=true"

    """
    ** Soup Getters
    """

    def get_soups(self) -> None:
        """ 
        Updates/Sets the instance variables that store soup related to the film
        From which film information is scraped
        """

        quick_soup = lambda response: BeautifulSoup(response.text, 'lxml')

        def get_soup_main() -> BeautifulSoup:
            response = self.session.request('GET', self.suburl_film_main)
            
            response_suburl = response.url.replace(f"{self.session.URL_MAIN}film/", '').rstrip('/')
            
            # The request was redirected - so set the path to the redirected url
            if response_suburl != self.path:
                logging.debug(f"Request was redirected. Changing path\nBefore: {self.path}\nAfter: {response_suburl}")
                self.path = response_suburl
            
            return quick_soup(response)

        def get_soup_stats() -> BeautifulSoup:
            response = self.session.request('GET', self.suburl_film_stats)
            return quick_soup(response)

        def get_soup_rating() -> BeautifulSoup:
            response = self.session.request('GET', self.suburl_film_rating)
            return quick_soup(response)

        def get_soup_rating_friends() -> BeautifulSoup:
            response = self.session.request('GET', self.suburl_film_rating_friends)
            return quick_soup(response)
        
        # Main attributes for the film - year, genre, crew, etc.
        self.soup_main = get_soup_main()

        # Views, Lists, Likes
        self.soup_stats = get_soup_stats()
        
        # Film's rating
        self.soup_rating = get_soup_rating()
        
        # Film's rating by your friends
        self.soup_rating_friends = get_soup_rating_friends()

    """
    ** Soup Magnifiers

    Specific parts of the soup that are accessed multiple times
    So I made properties for convenience's sake
    """

    @property
    def soup_main_pageWrapper(self) -> BeautifulSoup:
        """ Used for getting the film's id_ and length """
        return self.soup_main.select_one('div#film-page-wrapper')

    @property
    def soup_main_filmData(self) -> BeautifulSoup:
        """ Used for getting the film's name and year """
        pattern = re.compile(r"var filmData = \{(.*?)\};")
        script = self.soup_main.find('script', text=pattern)
        filmData = pattern.search(script.text).group(1).strip()
        return filmData

    @property
    def soup_main_tabDetails(self) -> BeautifulSoup:
        """ Used for getting the film's language, studio, etc. """
        return self.soup_main.select_one('div#tab-details')

    """
    ** Actions
    """

    def _action(self, action:str, **kwargs) -> None:
        """ 
        Makes a request based on the given parameters 
        
        > Parameters <
        --------------
        :action:
            a string representing a part of the suburl for the request
                example: 'add-to-watchlist'
        """
        suburl = f"{self.suburl_film_main}{action}/"
        self.session.request('POST', suburl=suburl, **kwargs)

    def action_watched_add(self) -> None:
        """ Mark the film as watched """
        # Example suburl: /film/alpha-and-omega/mark-as-watched/
        self._action('mark-as-watched')

    def action_watched_remove(self) -> None:
        """ Unmark the film as watched """
        # Example suburl: /film/alpha-and-omega/mark-as-not-watched/
        self._action('mark-as-not-watched')

    def action_watchlist_add(self) -> None:
        """ Add the film to your watchlist """
        # Example suburl: /film/alpha-and-omega/add-to-watchlist/
        self._action('add-to-watchlist')

    def action_watchlist_remove(self) -> None:
        """ Remove the film from your watchlist """
        # Example suburl: /film/alpha-and-omega/remove-from-watchlist/
        self._action('remove-from-watchlist')

    def action_rate(self, rating:int) -> None:
        """ Give the film a rating (1-10) | 0 to remove rating """
        if not (isinstance(rating, int) & rating in range(0,11)):
            raise ValueError(f"Invalid rating: {rating}")
        self._action('rate', data={'rating': rating})

    def action_unrate(self) -> None:
        """ Unrate a film """
        self.action_rate(0)

    def action_list_add(self, list_id:int|str):
        """ Add the film to a List given the id of that List """
        self.session.request('POST', 's/add-film-to-list', data={'filmId': self.id_, 'filmListId': list_id})

    """
    ** Film attributes **
    """

    @property
    def id_(self) -> int:
        """ Returns the film's id """
        return int(self.soup_main_pageWrapper.find('div', class_='film-poster').get('data-film-id'))

    @property
    def short_link(self) -> str:
        """ Gets the short link to a film's page """
        short_link = self.soup_main.find('input', id=f'url-field-{self.id_}').get('value')
        if self.short_link_prefix not in short_link:
            raise LunaboxdError(f"Unexpected short_url: {short_link}\nMissing prefix: {self.short_link_prefix}")
        return short_link
        
    @property
    def uri(self) -> str:
        """ Extract the URI from the short_link """
        return self.short_link.replace(self.short_link_prefix, '')

    @property
    def url(self) -> str:
        """ Returns the full URL of the film """
        return f"{self.session.URL_MAIN}{self.suburl_film_main}"

    @property
    def name(self) -> str:
        """ Returns the film's title """
        pattern = r"name: \"(.*?)\","
        match = util.find_one(pattern, self.soup_main_filmData)
        if not match: raise LunaboxdError(f"Could not get film_name for {self.path}")
        return match.replace('\\', '')
    
    @property
    def pretty_name(self) -> str:
        """ Returns the title of the film """
        title = self.soup_main.find('h1', class_='headline-1').text
        return util.from_xml_char_reference(title)

    @property
    def description(self) -> str:
        """ Returns the film's description """
        description = self.soup_main.find("div", class_="review")
        if not description: return ''
        return ''.join([i.text for i in description.find_all('p')]).strip()

    def description_short(self, max_chars: int = 250) -> str:
        """ Return a shorter version of the description if the description length exceeds :max_chars: """
        return util.truncate_string(self.description, max_chars)

    @property
    def year(self) -> int:
        """ Return's the film's release year, if one exists. Otherwise returns None """
        pattern = r'(?:releaseYear: ")(\d{4})'
        match = re.findall(pattern, self.soup_main_filmData)
        return int(match[0]) if match else None

    @property
    def genres(self) -> list[str]:
        """ Returns the genres a film has """
        tab_genres = self.soup_main.find('div', id='tab-genres')
        
        # Get the genre name of each genre_link on the film page
        pattern = r"/films/genre/([-\w\s:]+)/"
        genre_links = tab_genres.find_all('a', class_='text-slug', attrs={'href': re.compile(pattern)})
        return sorted([util.find_one(pattern, link.get('href')).title() for link in genre_links])

    @property
    def is_short(self) -> bool:
        """ Returns True if the film is considered a short_film by Letterboxd """
        return len(self) < 40

    @property
    def length(self) -> int:
        """ Returns the length of the film in minutes """
        footer = self.soup_main_pageWrapper.find('p', class_=['text-link', 'text-footer'])
        pattern = r"([\d,]+)"
        match = util.find_one(pattern, footer.text).replace(',', '')
        return int(match) if match else None

    @property
    def language(self) -> list[str]:
        results = self._get_tab_detail('films/language')
        
        # Get unique results
        # Why? E.g. Black Swan lists English twice (as original language and spoken language)
        return list(set(results))

    @property
    def alternative_titles(self) -> list[str]:
        if not (title_header := self.soup_main_tabDetails.find('h3', text='Alternative Titles')):
            return list()

        # Get the text for alternative titles
        text = title_header.select_one('h3:contains("Alternative Titles") + div p')

        # They are split by commas, so split them by such when converting to a list
        return [] if not text else text.split(',')

    @property
    def region(self) -> list[str]:
        return self._get_tab_detail('films/country')

    @property
    def crew(self) -> dict:
        """ 
        Returns a dict containing the crew of a film

        Example:
            {'Director': ['Tommy Wiseau'], 'Producers': ['Tommy Wiseau', 'Drew Caffrey', ...], ...}
        """
        tab_crew = self.soup_main.find('div', id='tab-crew')

        if not tab_crew: return {}

        hrefs = [i.get('href') for i in tab_crew.find_all('a')]
        
        ## Build a dictionary of crew members
        crew = defaultdict(list)
        def get_crew_member(href):
            role, *person = href.split('/')[1:]
            role = role.title()
            person = '/'.join(person).rstrip('/').replace('-', ' ').title()
            crew[role].append(person)
        [get_crew_member(i) for i in hrefs]
        
        return crew

    @property
    def cast(self) -> list[str]:
        """ Returns a list containing the cast of a film. """
        tab_cast = self.soup_main.find('div', id='tab-cast')
        if not tab_cast: return []
        cast_list = tab_cast.find('div', class_='cast-list')
        return [i.text for i in cast_list.find_all('a')]

    @property
    def studio(self):
        return self._get_tab_detail('studio')

    ## Util

    def _get_tab_detail(self, pattern_substring) -> list:
        if not (tab_details := self.soup_main_tabDetails):
            # The tab does not exist - the information does not either
            return list()

        pattern = rf"(?:{pattern_substring}/)([-\w\s:]+)/"
        if not (links := tab_details.find_all('a', attrs={'href': re.compile(pattern)})):
            # Does not have a link containing data - the information is missing
            return list()

        # Return the first (only) match
        return [util.find_one(pattern, link.get('href')) for link in links]

    """
    ** Images **
    """

    @property
    def img_poster(self) -> str:
        """ Returns the URL for the poster if available, else None """
        script = self.soup_main.find('script', attrs={'type': 'application/ld+json'})
        pattern = r'(?:"image":")(https://a.ltrbxd.com/[\/\d\w\-\.\?=]+)"'
        return util.find_one(pattern, script.text)

    @property
    def img_banner(self) -> str:
        """ Returns the URL of the banner if available, else None """
        div = self.soup_main.find('div', id='backdrop')
        if not div: return None
        return div.get('data-backdrop')

    @property
    def img_twitter(self) -> str:
        """ Returns the URL of the film's twitter image """
        return self.soup_main.find('meta', attrs={'name': 'twitter:image'}).get('content')
        
    """
    ** User interactions **
    """

    @property
    def fans(self):
        """ 
        Returns the number of fans a film has on Letterboxd
            NOTE: this figure is rounded
        """
        pattern = r"([\w\d\.]+) fans"
        match = util.find_one(pattern, self.soup_rating.text)
        return letterboxd.shortnum_to_int(match) if match else 0

    @property
    def views(self):
        title = self.soup_stats.find('a', class_='icon-watched').get('title')
        pattern = r"(?:Watched by )([\d,]+)"
        return int(util.find_one(pattern, title).replace(',', ''))

    @property
    def lists(self):
        title = self.soup_stats.find('a', class_='icon-list').get('title')
        pattern = r"(?:Appears in )([\d,]+)"
        return int(util.find_one(pattern, title).replace(',', ''))

    @property
    def likes(self):
        title = self.soup_stats.find('a', class_='icon-liked').get('title')
        pattern = r"(?:Liked by )([\d,]+)"
        return int(util.find_one(pattern, title).replace(',', ''))

    """
    ** Ratings **
    """

    @property
    def has_letterboxd_rating(self) -> bool:
        return self.ratings_number_of >= 30

    @property
    def ratings(self) -> dict:
        soup = self.soup_rating

        def get_rating(i):

            # Get the star_rating that corresponds to the i (e.g. 2.5 -> ★★½)
            star_rating = 'half-★' if i == 0.5 else letterboxd.num_to_star_rating(i)
            
            # Match any links with the exact star rating score of i
            link = soup.find('a', title=re.compile(fr"[^{letterboxd.RATING_STAR}{letterboxd.RATING_HALF}-]{star_rating} rating"))
            
            # If not found, no ratings for this score
            if not link: return 0

            # Return the number of ratings for this score
            return int(link.get('title').split()[0].replace(',', ''))
        
        ratings_dict = {int(k*2):get_rating(k) for k in letterboxd.RATINGS_RANGE}
        return ratings_dict

    @property
    def ratings_number_of(self) -> int:
        """ Returns the total number of ratings the film has received from users """
        return sum(self.ratings.values())

    @property
    def _ratings_total_score(self):
        """ Computes the combined score of all ratings """
        if not self.ratings_number_of: 
            return 0
        return sum([s*q for s,q in self.ratings.items()]) 

    ## Ways of calculating overall score

    @property
    def rating_letterboxd(self) -> float|None:
        """ Return the ratings_score a film has been assigned by Letterboxd. """
        # Not enough ratings to be given an overall ratings score by Letterboxd
        if not self.has_letterboxd_rating: 
            return None

        pattern = r"Weighted average of ([\d\.]+) based on"
        title = self.soup_rating.find('a', attrs={'title': re.compile(pattern)}).get('title')
        # Worry not about KeyError because films w/o letterboxd_rating already returned None
        return float(re.findall(pattern, title)[0])

    @property
    def rating_true(self) -> int | float:
        """ Returns the true mean average rating score """
        if not (rat_num := self.ratings_number_of):
            # No ratings have been received - there is no true average
            return None
        return (self._ratings_total_score / rat_num) * 0.5

    @property
    def rating_bayesian(self):
        """ Returns bayesian average rating score"""
        return self._get_bayesian_average(self.ratings, no_rating_fallback=letterboxd.RATING_MIDDLE)

    ## Friends' ratings

    @property
    def ratings_friends(self):
        results = [i.text for i in self.soup_rating_friends.find_all('span', class_='-micro')]
        friends_ratings = [letterboxd.star_rating_to_num(i) for i in results]
        return {i: friends_ratings.count(i/2) for i in range(1, 11)}

    @property
    def rating_friends_bayesian(self):
        return self._get_bayesian_average(self.ratings_friends, no_rating_fallback=None)

    ## Misc.

    @property
    def rating_ironic(self) -> bool:
        """
        Judge if a film has 'ironic-rating' (i.e. people are giving high scores as a joke)
            based on the film's mode most frequent rating scores being 0.5 and 5.0
        """
        ratings = self.ratings
        minimum_number_of_ratings = 3

        return all((
            sorted([util.key_max(ratings), util.key_max(ratings, 2)]) == [1,10],
            ratings[1] >= minimum_number_of_ratings,
            ratings[10] >= minimum_number_of_ratings
        ))

    ## Util

    @staticmethod
    def _get_bayesian_average(d:dict, no_rating_fallback:float|int|None, a0=9):
        """ 
        Given a dict of ratings
        Return the overall bayesian average of these
        """
        if not d or not any (d.values()): 
            return no_rating_fallback

        up = sum([d[n] * ((n-1)/9) for n in range(1,11)])
        down = sum([d[n] * ((9-(n-1))/9) for n in range(1,11)])
        return ( beta.ppf(0.05, up + a0, down + a0)  *4.5 ) + 0.5


# Testing code
if __name__ == '__main__':
    pass

    f = Film.from_uri('tTAK')
    f.display_table()
