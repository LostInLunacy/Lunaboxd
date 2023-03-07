
"""
    Class for util functions that pertain to Letterboxd specifically
"""

# Local
from exceptions import LunaboxdError

# Data
import numpy as np
import inflect

# Type validation
from typing import Callable
from bs4 import BeautifulSoup

# For identifying and switching between singular and plural nouns
inflect_engine = inflect.engine()

# Colours
DARK_ORANGE = "#FF8C00"
GREY = "#808080"

def get_pretty_name(soup: BeautifulSoup):
    """ Returns the pretty title of the Letterboxd page """
    title_prettify = soup.find('h1', class_='title-1 prettify')
    if not title_prettify:
        return None
    pretty_name = title_prettify.text.replace(title_prettify.find('span').text, '').strip()
    return pretty_name


"""
** Numbers
"""

def shortnum_to_int(text: str) -> int:
    """
    Letterboxd often display numbers in shorthand (e.g. 15.3k == 15300)
    This function converts these numbers into an integer (e.g. 15300)
    """
    string = text.replace(',', '')
    
    # Create float of string object
    # Use a float because the number could be e.g. 15.3k
    pre_final = float(string.replace('K', ' ').replace('M', ' '))
    
    if 'K' in string: pre_final *= 1000    
    if 'M' in string: pre_final *= 1000000
    return int(pre_final)

def int_to_shortnum(num: int | float) -> str:
    """
    Convert an int to a short representation of a number based on Letterboxd style
    """
    if num >= (billion := 1_000_000_000):
        value = num / billion
        return f"{num / 1_000_000_000:.1f}b" if value < 10 else f"{num / 1_000_000_000:.0f}b"
    elif num >= (million := 1_000_000):
        value = num / million
        return f"{num / 1_000_000:.1f}m" if value < 10 else f"{num / 1_000_000:.0f}m"
    elif num >= (thousand := 1_000):
        value = num / thousand
        return f"{num / 1_000:.1f}k" if value < 10 else f"{num / 1_000:.0f}k"
    else:
        return str(num)

def noun_switch(noun: str):
    """ Convert a noun to its singular if plural else to its plural if singular """
    if (converted_to_singular := inflect_engine.singular_noun(noun)):
        return converted_to_singular
    elif (converted_to_plural := inflect_engine.plural_noun(noun)):
        return converted_to_plural
    raise Exception(f"Unable to convert noun: {noun}")

"""
** Ratings
"""

RATING_STAR = '★' # Used to represent a full star on Letterboxd (i.e. 2 points of rating)
RATING_HALF = '½' # Used to represent a half-star on Letterboxd (i.e. 1 point of rating)
RATING_HALF_ONLY = 'half-★' # For some reason, Letterboxd uses this instead of '½'
RATINGS_RANGE = np.arange(0.5, 5.5, 0.5) # Range of valid Letterboxd ratings
RATING_MIDDLE = np.mean(RATINGS_RANGE) # Mean of valid Letterboxd ratings


def num_to_star_rating(num:float) -> str:
    """
    Convert a string star rating to a float
    For example: 3.5 -> ★★★½
    """
    # For whatever reason, Letterboxd uses this format for a single half star, rather than a ½
    if num == 0.5: return RATING_HALF_ONLY

    num_int = int(num*2)
    if num_int not in range(1,11): raise ValueError(f"Invalid num: {num}. Must be in inclusive range: (0.5, 5.0)")

    star, half = divmod(num_int, 2)
    return f"{RATING_STAR*star}{RATING_HALF*half}"


def star_rating_to_num(star_rating:str) -> float:
    """
    Convert a float to a string star rating
    For example: ★★★½ -> 3.5
    """
    if star_rating == RATING_HALF_ONLY: return 0.5

    star_rating = star_rating.strip()
    if any(invalid_chars := [c for c in star_rating if c not in (RATING_STAR, RATING_HALF)]):
        raise ValueError(f"Invalid chars: {invalid_chars}")
    result = float(star_rating.count(RATING_STAR) + (0.5 * star_rating.count(RATING_HALF)))
    if result * 2 not in range(1,11):
        raise ValueError(f"Invalid result: {result}\nFrom star_rating: {star_rating}")
    return result


# Removing unwanted characters
remove_special_chars = lambda string, allowed=[]: ''.join(c for c in string if c.isalpha() or c.isdigit() or c.isspace() or c in allowed)

"""
** Strings
"""

def string_to_suburl(string:str) -> str:
    """
    Given a string,
        Returns that string as a valid Letterboxd suburl, for making a request

    Example:
        "Fun MoviE-posters!" -> "fun-movie-posters"
    """
    string = remove_special_chars(string.lower(), allowed=['-', ':'])
    string = string.replace(' ', '-').replace('--', '-')
    
    if not string:
        raise Exception("Could not convert string to suburl. Result was empty string.")
    return string


def mins_to_formatted_time(mins: int, hours: int = 0) -> str:
    """ Converts a time given by minutes / hours in to the Letterboxd format """
    hours = mins // 60 + hours
    mins = mins % 60
    
    hour_str = 'hr' if hours == 1 else 'hrs'
    min_str = 'min' if mins == 1 else 'mins'

    return f"{hours}{hour_str} {mins}{min_str}"


# Display a float | int with two decimal places
dp_two = lambda x: f"{x:.2f}" if isinstance(x, int|float) else x

"""
** Page navigation
"""

def get_last_page(soup) -> int:
    """ For Letterboxd pages with numbered page navigation, returns the last page """
    pagination = soup.find('div', class_='pagination')
    if not pagination:
        return 1
    return int(pagination.find_all('li', class_='paginate-page')[-1].find('a').text)

"""
** Styling
"""

def create_colour_func(colour_map: tuple, default_colour = GREY) -> Callable:
    def number_to_colour(number: int | float) -> str:
        if not number: return f"[{default_colour}]None[/{default_colour}]"
        for minimum, maximum, colour in colour_map:
            if minimum <= number <= maximum:
                return f"[{colour}]{dp_two(number)}[/{colour}]"
        return None
    return number_to_colour  

# --- Colour a badge based on its name ---

_colour_badges = {None: 'white', 'Pro': DARK_ORANGE, 'Patron': 'blue', 'HQ': 'purple'}

def badge_grader(badge: str | None):
    """ Colours a badge based on its name """
    colour = _colour_badges[badge]
    return f"[{colour}]{badge}[/{colour}]"


# --- Colours a rating based on its value ---

_colour_ratings = [
    (0, 1, 'brown'),
    (1, 2, 'red'),
    (2, 3, 'yellow'),
    (3, 4, 'green'),
    (4, 5, 'pink')
]

rating_grader = create_colour_func(_colour_ratings)

