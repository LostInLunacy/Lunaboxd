"""
    For working with Letterboxd tags - scraping them and (provided they're yours) editing them
"""

# Local
import letterboxd
from session import LunaboxdSession, Credentials
import util
from viewing import Viewing, MyViewing

# Web scraping
from bs4 import BeautifulSoup, Tag

# Data
import re

# Debugging
import logging

# --- Rich --- START

from rich.console import Console
import rich.progress

console = Console()

# --- Rich --- END

@util.custom_repr
class Tags:

    def __init__(self, username: str):
        self.session = LunaboxdSession.load()
        self.username = username

    def _get_valid_category(self, category: str) -> str:
        """
        For example if 'review' is passed, return 'reviews', to avoid PageNotFoundError
        Letterboxd like to mix their singular and plural nouns to make life a struggle for us
        """

        d = self.viewing_getter_html_classes

        if category in d:
            return category
        elif (noun_switched_category := letterboxd.noun_switch(category)) in d:
            return noun_switched_category
        raise ValueError(f"Invalid category: {category}")

    def get_tags(self, category: str) -> dict:
        """
        Return the tag name and number of times it has been used for a given catgeory

        > Parameters <
        --------------
        :category:
            the category of listing (diary / reviews / lists)
        """
        category = self._get_valid_category(category)

        def get_soup(page_num: int) -> BeautifulSoup:
            """ Given a page number, get the soup of the tags page """
            response = self.session.request('GET', f'{self.username}/tags/{category}/page/{page_num}')
            return BeautifulSoup(response.text, 'lxml')  

        def get_tag_name(li: Tag) -> str:
            """ Given an li_tag containing tag information, get the name of the Tag """
            return li.find('a').get('title')

        def get_tag_times_used(li: Tag) -> int:
            """ 
            Given an li_tag containing tag information, 
            get the number of times the user has tagged a film with this tag 
            """
            span_tag = li.find('span')
            return 1 if not span_tag else int(span_tag.text)

        # Get the first page of the soup 
        # in order to check if there are tags and if so how many pages of tags
        soup = get_soup(1)
        
        # Case where there are no results (i.e. no tags)
        no_results_header = soup.find("h2", text=re.compile(r"^No [a-zA-Z]+ tags yet$"))
        if no_results_header:
            return list()

        # Find the last page of tags
        last_page = letterboxd.get_last_page(soup)

        # Get tag results
        soups = [soup] + [get_soup(i) for i in range(2, last_page)]
        li_tags = [tag for soup in soups for tag in soup.find('ul', class_='tags').find_all('li')]
        # Filter out unwanted li tags
        li_tags = [i for i in li_tags if i.find('a', attrs={'title': True})]

        results = {get_tag_name(li): get_tag_times_used(li) for li in li_tags}

        return results

    @property
    def tags_reviews(self) -> dict:
        """ Returns a dictionary of the user's review tags and the times they occur """
        return self.get_tags('reviews')

    @property
    def tags_diary(self) -> dict:
        """ Returns a dictionary of the user's diary tags and the times they occur """
        return self.get_tags('diary')

    @property
    def tags_lists(self) -> dict:
        """ Returns a dictionary of the user's list tags and the times they occur """
        return self.get_tags('lists')

    """
    ** Viewings getters
    """

    viewing_getter_html_classes = {
        'reviews': 'film-detail-content',
        'diary': 'headline-3 prettify',
        'lists': 'title-2 prettify'
    }

    def _get_viewing_links(self, category: str | list, tag: str | list) -> list[str]:
        """
        Returns a list of links to Viewings 

        :category: and :tag: can be list or str, but must be the same type as one another
        """

        if type(category) != type(tag) or not isinstance(category, (list, str)):
            raise TypeError(f"Invalid types for category ({type(category)}) and tag ({type(tag)})")
        
        def get_links(category, tag):
            page_num = 1
            results = list()
            
            # Get the class name of the HTML tag to scrape the information from
            # This class varies depending on category
            html_class = self.viewing_getter_html_classes[category]

            while True:
                suburl = f'{self.username}/tag/{tag}/{category}/page/{page_num}'
                response = self.session.request('GET', suburl)
                soup = BeautifulSoup(response.text, 'lxml')

                hrefs = [i.find('a').get('href') for i in soup.find_all(class_=html_class)]
                results.extend(hrefs)

                if not soup.find('a', class_='next'):
                    break
                page_num += 1

            return results

        if isinstance(category, str) and isinstance(tag, str):
            return get_links(tag = tag, category = category)
        
        elif isinstance(category, list) and isinstance(tag, list):
            results = set()
            [results.update(get_links(tag = t, category = c)) for c in category for t in tag] 
            return list(results)


    def get_viewings(self, category: str | list, tag: str | list) -> list[Viewing]:
        """
        Returns a list of Viewings 

        :category: and :tag: can be list or str, but must be the same type as one another
        """

        links = self._get_viewing_links(tag = tag, category = category)

        results = list()
        for link in rich.progress.track(links, description = f"Getting views for tag: {tag}, category: {category}"):
            results.append(Viewing.from_link(link))

        return results


class MyTags(Tags):

    def __init__(self):
        self.session = LunaboxdSession.load()
        self.username = self.session.username

    """
    ** Tag editing
    """

    def edit_tags(self, tags_find: list, tags_replace: list | None = None, categories: list | None = None) -> None:
        """
        > Parameters <
        --------------
        :tags_find:
            the tags you wish to replace
        :tags_replace:
            for every viewing that contains one or more elements in :tags_find:, 
            every tag in :tags_replace: will be added

        For example, given
        v1 = Viewing that has the tags: ['one', 'two', 'three']
        v2 = Viewing that has the tags: ['six', 'seven', 'eight']
        v3 = Viewing that has the tags: ['zero', 'two', 'nine']

        And I pass
        :tags_find: = 'two', 'three',
        :tags_replace: = 'hello', 'world'

        Then after the method has run, the update tags will be:
        v1 -> ['one', 'hello', 'world'] # Contained 'two' & 'three', so they were replaced and the replacement tags were added
        v2 -> ['six', 'seven', 'eight'] # Unchanged because it did not contain any elements in :tags_find:
        v3 -> ['zero', 'six', 'seven', 'nine'] # Contained 'two', so that was replaced and the replacement tags were added
        """

        # Attempt to ensure valid tags passed
        tags_find_suburls = [letterboxd.string_to_suburl(i) for i in tags_find]
        
        # If categories not passed, set variable to all categories
        categories = [self._get_valid_category(i) for i in categories] if categories else self.viewing_getter_html_classes.keys()

        # Get the viewings for the list of tags and list of categories
        results = self.get_viewings(tag = tags_find_suburls, category = categories)

        # Remove any unwanted results
        if 'diary' not in categories and 'reviews' in categories:
            results = [i for i in results if not i.is_diary_entry]
        elif 'reviews' not in categories and 'diary' in categories:
            results = [i for i in results if not i.is_review]

        logging.debug(f"\nReplacing tags:\nViewings: {len(results)}\nFind: {tags_find}\nReplace: {tags_replace}\n")

        # Execute tag replacements for each result
        # Using for loop (instead of list compreh. as rich.progress.track seesm to require)   
        for viewing in rich.progress.track(results, description = "\nReplacing tags"):
            viewing.replace_tags(tags_find, tags_replace)
        
    """
    ** Viewing getters
    """

    def get_viewings(self, category: str | list, tag: str | list) -> list:

        links = self._get_viewing_links(tag = tag, category = category) 

        results = list()
        for link in rich.progress.track(links, description = f"Getting views for tag: {tag}, category: {category}"):
            results.append(MyViewing.from_link(link))

        return results


# Testing code
if __name__ == '__main__':
    pass

    # t = MyTags()
    # t.edit_tags(
    #     ['replace me', 'and me'], ['with', 'these', 'new', 'tags'], categories = ['diary', 'review']
    # )
