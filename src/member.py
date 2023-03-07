"""
    For getting basic info about the user
"""

# Local
from exceptions import LunaboxdError, PageNotFound
from find import Find
import letterboxd
from session import LunaboxdSession
import util

# Webscraping
from bs4 import BeautifulSoup


# --- Rich --- START

from rich.console import Console
from rich.table import Table

console = Console(theme = util.style_theme)

# --- Rich --- END


@util.custom_repr
class UserInfo:

    def __init__(self, username: str) -> None:
        self.session = LunaboxdSession.load()

        # Check that username is valid
        try:
            # The user's profile was not found - assume they do not exist
            self.session.request('GET', f"{username}/")
        except PageNotFound:
            raise ValueError(f"Invalid username: {username}")

        self.username = username
        self._get_profile_soup()

    def __str__(self):
        name_str = f"{self.username} ({self.display_name})"
        if self.badge: name_str += f" [{self.badge}]"
        return name_str

    def display_table(self) -> None:
        """ Displays film information in a table """
        
        # Create the table and main columns
        table = Table(show_header = True, show_lines = False, style='purple')
        table.add_column('', justify = 'right', style = f'info')

        column_2 = f"{self.display_name} ([green]{self.username}[/green])"
        if self.badge: column_2 += f" [{letterboxd.badge_grader(self.badge)}]"
        table.add_column(column_2)

        # Fill table rows with attributes
        table.add_row('films', f"{self.profile_statistics['films']}")
        table.add_row('this year', f"{self.profile_statistics['this year']}")
        table.add_row('year projection', f"{self.year_projection}")
        table.add_row('rating average', f"{letterboxd.rating_grader(self.rating_average)}")
        table.add_row('following', f"{self.profile_statistics['following']}")
        table.add_row('followers', f"{self.profile_statistics['followers']}")
        table.add_row('followers you know', ', '.join(self.followers_you_know))
        table.add_row('favourites', f"{', '.join((i[1] for i in self.favourites))}")

        console.print(table)

    def __index__(self):
        return self.username

    def __hash__(self):
        return hash(self.__index__)

    """
    ** Alternative Constructors
    """

    @classmethod
    def from_display_name(cls, display_name: str):
        person = Find().search(display_name, 'members', limit=1)

        if not person:
            raise LunaboxdError(f"Could not find username based on :display_name: given")
        return cls( person[0]['username'] )

    """
    ** Soup getters
    """

    def _get_profile_soup(self) -> None:
        """ 
        Get the BeautifulSoup for the user's profile page
        Update the :self.soup_profile: variable accordingly
        """
        response = self.session.request('GET', f"{self.username}/")
        profile_soup = BeautifulSoup(response.text, 'lxml')
        self.soup_profile = profile_soup

    """
    ** Actions
    """

    # ============ No longer functional - Letterboxd introduced spam protection :( ============ #
    
    # def _action(self, action: str) -> None:
    #     """
    #     Make a request based on the given parameters
        
    #     > Parameters <
    #     --------------
    #     :action:
    #         a string representing a part of the suburl for the request
    #             example: 'follow'
    #     """
    #     suburl = f"{self.username}/{action}/"
    #     self.session.request('POST', suburl)
    
    # def follow(self) -> None:
    #     # 
    #     """ Execute POST request to follow the user """
    #     self._action('follow')

    # def unfollow(self) -> None:
    #     """ Execute POST request to unfollow the user """
    #     self._action('unfollow')

    # def block(self) -> None:
    #     """ Execute POST request to block the user. """
    #     self._action('block')

    # def unblock(self) -> None:
    #     """ Execute POST request to unblock the user. """
    #     self._action('unblock')

    """
    ** Attributes
    """

    @property
    def display_name(self) -> str:
        """
        Makes a request to the user's profile and gets the display name

        NOTE:
        - As a free user on Letterboxd, you can't change your :username:
        However, you can change your :display_name:
        - So the :display_name: on a user's profile may differ from their :username:
        - You can see the :username: by looking in the URL (letterbox.com/USERNAME/)

        > Returns <
        -----------
        display_name (str)
        """
        return self.soup_profile.find('h1', class_='title-1').text

    @property
    def badge(self) -> str | None:
        """
        Letterboxd users have a badge that represents their membership level
        (free = None | pro = pro | patron = patron)
        """
        badge = self.soup_profile.find('span', class_='badge')
        return None if not badge else badge.text

    @property
    def profile_statistics(self):
        """ Films | This Year | Lists | Following | Followers """
        profile_statistics = self.soup_profile.find_all('h4', class_='profile-statistic')
        return {
            util.remove_special_chars(i.find('span', class_='definition').text.lower()): letterboxd.shortnum_to_int(i.find('span', class_='value').text) for i in profile_statistics
            }

    @property
    def favourites(self) -> list[tuple]:
        """
        Gets the user's favourite films

        > Returns <
        -----------
        [(fav1_id, fav1_name), (fav2_id, fav2_name), ...]
        """

        divs = self.soup_profile.find('section', id='favourites').find_all('div', attrs={'data-film-id': True})
        return [
            (
                int(i.get('data-film-id')), # film_id
                i.find('img').get('alt') # film name
                
            ) for i in divs
        ]

    """
    ** Network
    """

    @property
    def following(self) -> list:
        """ Returns a list of users (usernames) the user is following """
        return self._get_people('following')

    @property
    def followers(self) -> list:
        """ Returns a list of users (usernames) the user is followed by """
        return self._get_people('followers')

    @property
    def followers_you_know(self) -> list:
        return self._get_people('followers-you-know')
            
    @property
    def mutuals(self) -> list:
        """
        Returns a list of mutuals
        """
        following = set(self.following)
        followers = set(self.followers)
        return list(following.intersection(followers))
        
    def _get_people(self, suburl: str) -> list:
        """ 
        Scrapes the profile links (original usernames) on a page
            of a given user's followers/following page

        > Parameters <
        --------------
        :soup:
            the soup of the page for a user's following / followers
        
        > Returns <
        -----------
        :people: 
        """           
        results = list()
        page_num = 1
        while True:
            response = self.session.request("GET", f"{self.username}/{suburl}/page/{page_num}")
            soup = BeautifulSoup(response.text, 'lxml')
            people = [person.find('a').get('href').replace('/', '') for person in soup.find_all("td", class_="table-person")]
            results.extend(people)

            if not soup.find('a', class_='next'):
                break
            page_num += 1

        return results

    """
    ** Ratings
    """

    @property
    def rating_distribution(self) -> dict:
        """
        Scrapes the users's Letterboxd profile
        Gets num_times they've rated a film each score (0.5 to 5.0)
        Returns a dict of score: quantity (e.g. 3.5: 17)

        > Returns <
        -----------
        ratings_distribution
            Example: {0.5: 44, 1.0: 108... 5.0: 91}
        """
        # BUG: Not working

        # Find histogram
        ratings_histogram = self.soup_profile.find(
            'div',
            class_=['rating-histogram clear rating-histogram-exploded']
        ).find('ul')

        # There are 10 li tags, 1 for each score 0.5 -> 5.0
        # Within the li tags, there's a link (provided that the user has rated >=1 film that score)
        rating_distribution = {}

        for rating_score in letterboxd.RATINGS_RANGE:
            tag = ratings_histogram.find(lambda tag: tag.get('title') and letterboxd.num_to_star_rating(rating_score) in tag.get('title'))
            rating_distribution[rating_score] = int(tag.text.split()[0]) if tag and tag.text else 0

        return rating_distribution

    def display_rating_distribution(self) -> str:
        symbol_list = util.symbol_list(self.rating_distribution.values(), 25)
        symbol_dict =  dict(zip(self.rating_distribution.keys(), symbol_list))
        return '\n'.join([f"{k}: {v}" for k, v in symbol_dict.items()])


    @property
    def rating_total(self) -> int:
        """ Total number of films that user has rated """
        return sum(self.rating_distribution.values())

    @property 
    def rating_average(self) -> float:
        """ The average rating score the user gives """
        ROUND_TO = 2
        return round(sum([s*q for s,q in self.rating_distribution.items()])/self.rating_total, ROUND_TO)

    """
    ** Misc
    """

    @property
    def year_projection(self) -> int:
        """ Estimates how many films the user will watch this year """
        
        watched_this_year = self.profile_statistics.get('this year')
        if not watched_this_year:
            return 0

        day_of_year = util.day_of_year()
        return int(( watched_this_year / day_of_year ) * 365)


class Myself(UserInfo):
    """ Subclass for Userinfo to quickly get the UserInfo for the session user """

    def __init__(self):
        self.session = LunaboxdSession.load()
        self.username = self.session.username
        self._get_profile_soup()



# Testing code
if __name__ == '__main__':
    pass

    n = UserInfo('LostInStyle')
    pass

