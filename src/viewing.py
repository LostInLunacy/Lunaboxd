"""
    On Letterboxd, the following come under the term 'viewing':
    - Diary entries
    - Reviews

    This module focuses on the scraping and updating of Viewings
"""

# Local
from exceptions import LetterboxdError
from session import LunaboxdSession
import util

# Data
import re
import pendulum

# Web scraping 
from bs4 import BeautifulSoup

# Type validation
from typing import Self

# Debugging
import logging


# --- Rich --- START

from rich.console import Console
from rich.table import Table

console = Console(theme = util.style_theme)

# --- Rich --- END


@util.custom_repr
class Viewing:
    """
    Provides information about a viewing given its suburl
    """
    
    def __init__(self, username: str, film_suburl: str, num: int | None = None) -> None:
        """
        suburl
            Example: 'dragon_needles/film/eagles-over-london/

            NOTE: for reference, this takes the format
                username/film/film_name
                
                If the person has two Viewings of the film, then second one will have a trail '/2'
                e.g. username/film/film_name/3
        """
        self.session = LunaboxdSession.load()

        self.username = username
        self.film_suburl = film_suburl
        self.num = num

        # logging.debug(f"Generated viewing suburl: {self.suburl}")

        # Get the soup from which viewing data can be gathered (via properties)
        self.update_soups()

    @classmethod
    def from_link(cls, suburl: str):
        
        split_suburl = suburl.strip('/').split('/')        
        num = int(split_suburl[3]) if len(split_suburl) == 4 else None
        username, _, film_suburl, *_ = split_suburl

        return cls(
            username = username,
            film_suburl = film_suburl,
            num = num
        )

    @property
    def suburl(self):
        return '/'.join((self.username, 'film', self.film_suburl)) + '/'
        
    @property
    def suburl_and_num(self):
        if not self.num:
            return self.suburl
        return f"{self.suburl}{self.num}/" 

    def __str__(self):
        if self.is_review and self.is_diary_entry:
            substr = "review & diary entry"
        elif self.is_review:
            substr = "review"
        elif self.is_diary_entry:
            substr = "diary entry" 
        return f"{self.username}'s {substr} for {self.film_name}"

    def display_table(self) -> None:
        """ Displays film information in a table """
        
        # Create the table and main columns
        table = Table(show_header = True, show_lines = False)
        table.add_column('', justify = 'right', style = f'info')
        

        is_review = f"[green]review[/green]" if self.is_review else ''
        is_diary = f"[blue]diary entry[/blue]" if self.is_diary_entry else ''
        categories = ' & '.join((is_review, is_diary))

        title = f"[purple]{self.username}[/purple]'s {categories} for [yellow]{self.film_name}[/yellow]"

        table.add_column(title, style='white')

        # Fill table rows with attributes
        table.add_row('viewingId', f"{self.viewingId}")
        table.add_row('filmId', f"{self.filmId}")
        table.add_row('film name', f"{self.film_name}")
        table.add_row('specified date', f"{self.specifiedDate}")
        table.add_row('date', f"{self.viewingDateStr}")
        table.add_row('rewatch', f"{self.rewatch}")
        rating = f"{self.rating/2}" if self.rating else ''
        table.add_row('rating', rating)
        table.add_row('liked', f"{self.liked}")
        table.add_row('tags', ', '.join(self.tag))
        table.add_row('spoilers', f"{self.containsSpoilers}")
        table.add_row('review', self.review_short())

        # Print the table to screen
        console.print(table)

    def __eq__(self, other):
        """ 
        Returns True if the ViewingId is equivalent to the object it is being compared to
        (i.e. they are the same viewing)
        """
        if not isinstance(other, Viewing, MyViewing):
            raise TypeError(f"Cannot compare {self.__class__.__name__} to {type(other)}")
        return self.viewingId == other.viewingId

    def __ne__(self, other):
        """ Returns False if the ViewingIds are equivalent else True """
        return not self == other

    """ 
    ** Actions
    """

    def _action(self, action: str, **kwargs) -> None:
        suburl = f's/viewing:{self.viewingId}/{action}'
        return self.session.request('POST', suburl, **kwargs)

    # NOTE: I couldn't figure out how to like a review, since this requires a Recaptcha token
        # that was seemingly inaccessible. 
    # Strange that liking a film review alerts the spam filter but commenting on one does not

    def action_unlike(self) -> None:
        response = self._action('like', data={'liked': False, 'gRecaptchaAction': 'viewing_like'})
        return response

    @util.type_check({'comment': str})
    def action_comment(self, comment: str):
        if not self.is_review:
            raise LetterboxdError("Replies can only be posted to reviews")
        if not comment:
            raise LetterboxdError("Comment cannot be empty")
        self._action('add-comment', data={'comment': comment})

    """
    ** Categorisation
    """

    @property
    def is_diary_entry(self) -> bool:
        """ Returns True if the viewing is a diary entry, else False """
        return self.specifiedDate

    @property
    def is_review(self) -> bool:
        """ Returns True if the viewing is a review, else False """
        return bool(self.review)

    """
    ** Refreshing
    """

    @property
    def data(self) -> dict:
        """ Dictionary of data used for making post requests to update review information """
        return {
            'viewingId': self.viewingId,
            'filmId': self.filmId,
            'specifiedDate': self.specifiedDate,
            'viewingDateStr': self.viewingDateStr,
            'review': self.review,
            'containsSpoilers': self.containsSpoilers,
            'rewatch': self.rewatch,
            'rating': self.rating,
            'liked': self.liked,
            'tag': self.tag
        }

    def update_soups(self) -> None:
        """ Update the soups so that data reflects the up to date viewing """
        make_soup = lambda suburl: BeautifulSoup(self.session.request('GET', suburl).text, 'lxml')

        self.soups = dict()
        self.soups['viewing_page'] = make_soup(self.suburl_and_num)
        self.soups['liked_src'] = make_soup(f"{self.suburl}activity/")

        logging.debug(f"Updated soups for viewing:{self.viewingId}")

    """
    ** Attributes
    """

    @property
    def viewingId(self) -> int:
        """ Returns the Viewing's id """
        return int(self.soups['viewing_page'].find_all('div', class_='js-csi')[1].get('data-src').split('/')[3])

    @property
    def filmId(self) -> int:
        """ Returns the filmId """
        return int(self.soups['viewing_page'].find('div', class_='film-poster').get('data-film-id'))

    @property
    def film_name(self) -> str:
        """ Returns the film name as a string """
        return self.soups['viewing_page'].find('div', class_='film-poster').find('img').get('alt')

    @property
    def specifiedDate(self) -> bool:
        """
        Returns True if the review has a specified date else False
        """
        return bool(self.soups['viewing_page'].find('p', class_='date-links').find('a'))

    @property
    def viewingDateStr(self) -> str:
        """
        Returns a string representation of the date the review author watched the film
        """
        if self.specifiedDate:
            viewingDateStr = '-'.join(self.soups['viewing_page'].find('p', class_='view-date').find_all('a')[1].get('href').split('/')[-4:-1])
        else:
            string = self.soups['viewing_page'].find('p', class_='date-links').text.strip()
            p_format = "DD MMM YYYY"
            viewingDateStr = pendulum.from_format(string, p_format).to_date_string()
        return viewingDateStr

    @property
    def review(self) -> str:
        """ Returns the content of the review """
        review = self.soups['viewing_page'].find('div', class_='review').find_all('div')[-1]
        review = util.multi_replace(
            str(review),
            {'</p>': '', '<p>': '\n\n', '</br>': '\n', '<div>': '', '</div>': ''}
        )
        return review.lstrip('\n\n')

    def review_short(self, max_chars = 250) -> str:
        """ Return a shorter version of the review if the review length exceeds :max_chars: """
        return util.truncate_string(self.review, max_chars)

    @property
    def rating(self) -> int:
        """ 
        Returns the rating score the review author gave the film 
        If they didn't give it a rating, returns 0
        """
        if (rating_span := self.soups['viewing_page'].find('span', class_='rating-large')):
            return int(rating_span.get('class')[-1].split('-')[-1])
        # If no rating given, Letterboxd uses the value 0
        return 0

    @property
    def liked(self) -> bool:
        """ 
        Returns True if the review author 'liked' the film, else False 
        """
        activity_summaries = [re.sub(' +', ' ', i.text) for i in self.soups['liked_src'].find_all('p', class_='activity-summary')]
        pattern = rf"liked(?: and rated)? {self.film_name}"
        return any((re.findall(pattern, i) for i in activity_summaries))
        
    @property
    def containsSpoilers(self) -> bool:
        """
        Returns True if the review has been labelled as containing spoilers, else False 
        """
        return True if (self.review and self.soups['viewing_page'].find('div', class_='review').find('em', text=re.compile(r"may contain spoilers"))) else False           

    @property
    def rewatch(self) -> bool:
        """
        Returns True if the review has been labelled a rewatch, else False
        """
        view_date = self.soups['viewing_page'].find('p', class_='view-date').text
        return 'Rewatched' in view_date

    @property
    def tag(self) -> list:
        """
        Returns a list of tags the review has
        """
        if not (tags_ul := self.soups['viewing_page'].find('ul', class_='tags')): 
            return list()
        return [a.text for a in tags_ul.find_all('a')]
        # return [a.get('href').split('/')[-3] for a in tags_ul.find_all('a')]



class MyViewing(Viewing):
    
    # suburl used to save / update viewing
    suburl_update = "s/save-diary-entry"

    @classmethod
    def create(
        cls,
        filmId: int,
        specifiedDate: bool,
        viewingDateStr: str | None,
        review: str = '',
        containsSpoilers: bool = False,
        rewatch: bool = False,
        rating: int = 0,
        liked: bool = False,
        tag: list = list()
        ) -> Self:

        # Remove from local scope
        if not specifiedDate: del viewingDateStr

        with LunaboxdSession.load() as session:
            
            # Make request to update (also used for creation) URL 
            # The parameters passed to this method are converted into a data dictionary
                # which is then passed when making the request
            session.request('POST', cls.suburl_update, data={k:v for k,v in locals().items() if k != 'cls'})   

    def __init__(self, film_suburl: str, num: int | None = None) -> None:
        
        self.session = LunaboxdSession.load()

        self.username = self.session.username
        self.film_suburl = film_suburl
        self.num = num
        
        logging.debug(f"Generated viewing suburl: {self.suburl}")

        self.update_soups()
        
    @classmethod
    def from_link(cls, suburl: str):

        split_suburl = suburl.strip('/').split('film/')[-1].split('/')

        if (num_slashes := len(split_suburl)) > 2:
            raise ValueError(f"Invalid suburl: {suburl} with unexpected number of slashes: {num_slashes}")

        return cls(*split_suburl)

    """ 
    ** Updating
    """

    @Viewing.specifiedDate.setter
    def specifiedDate(self, value: bool):
        """ Change the specifiedDate (i.e. if True: 'you watched on this day') to True or False """
        self.update(specifiedDate = value)

    @Viewing.viewingDateStr.setter
    def viewingDateStr(self, value: str):
        """ 
        Change the viewingDateStr (i.e. date listed on the Viewing) to a new date
            format: yyyy-mm-dd
        """
        self.update(viewingDateStr = value)

    @Viewing.review.setter
    def review(self, value: str):
        """ Change the review text """
        self.update(review = value)

    @Viewing.containsSpoilers.setter
    def containsSpoilers(self, value: bool):
        """ 
        Change the containsSpoilers variable
        If True, the review will be hidden by default 
        """
        self.update(containsSpoilers = value)

    @Viewing.rewatch.setter
    def rewatch(self, value: bool):
        """ Change whether the Viewing is listed as a rewatch """
        self.update(rewatch = value)

    @Viewing.rating.setter
    def rating(self, value: int):
        """ 
        Change the rating connected to the Viewing 
        2.5 -> 2.5/5 rating | 0 -> no rating
        """
        self.update(rating = value)

    @Viewing.liked.setter
    def liked(self, value: bool):
        """ Change whether or not you have liked the film """
        self.update(liked = value)

    @Viewing.tag.setter
    def tag(self, value: list):
        """ Change the tags list associated with the Viewing """
        self.update(tag = value)

    def _get_valid_update_arguments(self, **attributes_to_change):
        data_keys = set([k for k in self.data.keys() if k not in ('viewingId', 'filmId')])
        arg_keys = set(attributes_to_change.keys())
        if (invalid_kwargs := arg_keys.difference(data_keys)):
            raise ValueError(f"Invalid kwargs: {invalid_kwargs}")

    def update(self, **attributes_to_change): 
        """ 
        Update (edit) the viewing

        > KeyWord Parameters <
        ----------------------
        :specifiedDate: (bool)
            Whether or not there is a specified date for the Viewing
        
        :viewingDateStr: (str)
            Date of the Viewing
                format: yyyy-mm-dd
        
        :review: (str)
            The review text of with the Viewing
        
        :containsSpoilers: (bool)
            Whether or not the review contains spoilers
        
        :rewatch: (bool)
            Whether or not the Viewing is marked as a rewatch
            
        :rating: (int)
            The rating you gave the film on that Viewing
            0 = No rating | 1-10 = Letterboxd rating

        :liked: (bool)
            Whether or not you liked the film 
            NOTE: this is NOT tied to the viewing - 
                If you like a film later, it will appear as liked in all your Viewings for it, 
                regardless of whether you liked them when creating or editing that Viewing

        :tag: (list)
            Any tags you want to give the Viewing
        """

        # Check for invalid arguments
        self._get_valid_update_arguments(**attributes_to_change)

        if attributes_to_change.get('specifiedDate') and self.is_diary_entry:
            raise LetterboxdError("Diary entries must have specified date!")

        # Update any changed attributes
        data = {k:v if k not in attributes_to_change or k in ('viewingId', 'filmId') else attributes_to_change[k] for k,v in self.data.items()}

        # Make the update request
        self.session.request('POST', self.suburl_update, data=data)

        # Keep attributes up to date
        self.update_soups()

    def replace_tags(self, tags_find: list, tags_replace: list | None = None) -> None:
        """
        Find these tags (list) and replace with a given tag (str)
        """

        # Remove any tags that are to be replaced
        tags = [i for i in self.tag if i not in tags_find]
        if len(tags) == len(self.tag):
            logging.info("Could not find any tags to replace")

        # Replace the removed tags with tag_replace, if passed
        if tags_replace: tags.extend(tags_replace)
        
        # Perform the changes with a request
        self.update(tag=tags)

    def update_soups(self) -> None:
        """
        ** Overloading ** 
        Update the soups so that data reflects the up to date viewing 
        """

        # Quick lambda function to create soup from a request
        make_soup = lambda suburl: BeautifulSoup(self.session.request('GET', suburl).text, 'lxml')

        self.soups = dict()

        # Page for viewing the Viewing
        self.soups['viewing_page'] = make_soup(self.suburl_and_num)

        # Activity page for the film the Viewing is about
        # Will say for example if you liked and rated the film
        self.soups['liked_src'] = make_soup(f"{self.suburl}activity/")

        # The source of the review text
        self.soups['review_src'] = make_soup(f"csi/viewing/{self.viewingId}/sidebar-user-actions/?esiAllowUser=true")

        logging.debug(f"Updated soups for viewing:{self.viewingId}")

    """
    ** Attributes
    """

    @property
    def review(self) -> str:
        """ Returns the content of the review """
        edit_review_button = self.soups['review_src'].find('a', class_='edit-review-button')
        if not edit_review_button:
            return ''
        # Convert any XML character references in the review text, and return it
        return util.from_xml_char_reference(edit_review_button.get('data-review-text'))


if __name__ == '__main__':
    pass

    # Test code


    # v = Viewing.from_link('LostInStyle/film/the-revenge-of-robert/1//')
    
    # v2 = Viewing.from_link('darthslug/film/birdemic-3-sea-eagle/')

    # print(v)

    # v.update(

    # )

    # v2 = Viewing(
    #     username = 'lostinstyle',
    #     film_suburl = 'the-horse-dancer'
    # )

    # v.action_comment('')

