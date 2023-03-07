"""
    Mimics use of the search bar on Letterboxd
    Given a query and search category (e.g. members), returns the results of that search
"""

# Local
from exceptions import PageNotFound
from session import LunaboxdSession
import letterboxd
import util

# Data
import math
import re

# Web scraping
from bs4 import BeautifulSoup, SoupStrainer

# Type validation
import requests

# Debugging
import logging


@util.custom_repr
class Find:
    """
    Searches Letterboxd using the search bar

    NOTE:
        Do not confuse with search.py
            which pertains to filtering a page based on criteria 
                (e.g. horror films from 2007 on a user's profile)
    """

    # Suburl for the find page
    suburl_search_prefix = 'search'

    # Number of results per page - static variable
    RESULTS_PER_PAGE = 20

    def __init__(self) -> None:
        self.session = LunaboxdSession.load()

    def _get_soup(self, query: str, search_category: str) -> requests.Response:
        full_url = self.make_substring(query, search_category)
        try:
            response = self.session.request('GET', full_url)
        except PageNotFound:
            # No results
            return None
        else:
            return response

    def _get_results(self, query: str, search_category: str, limit: int | None) -> list[dict]:
        """
        Executes requests and scrapes the results
        
        > Called by <
        -------------
        self.__call__()
        """
        if not (response := self._get_soup(query, search_category)):
            # No results
            return []

        # Identify the page to stop at
        soup = BeautifulSoup(response.text, 'lxml')
        page_stop = min (
            letterboxd.get_last_page(soup), # Last page
            math.ceil(limit / self.RESULTS_PER_PAGE) # Page based on limit set
        ) if limit else letterboxd.get_last_page(soup) # If no limit just get last available page

        results = list()
        page_current = 1

        # Get the appropriate scraper method depending on search category - this will be executed for each page
        get_page_func = self.get_page_methods[search_category]

        while True:
            ul = BeautifulSoup(response.text, 'lxml', parse_only=SoupStrainer('ul', class_='results'))
            results_on_page = get_page_func(ul)

            # Add the results_on_page to results
            results.extend(results_on_page)

            if page_current == page_stop:
                break
            
            else:
                # Otherwise get response for next page
                page_current += 1
                full_url = self.make_substring(query, search_category, page_num = page_current)
                response = self.session.request('GET', full_url)

        # Strip results so that they do not exceed the limit
        # E.g. if the limit was 105, and there are 20 results per page, the 6th page would still be scraped
        #   In that case this would strip the last 15 results, taking the number from 120 to 105
        return results[:limit] if limit else results

    def __call__(self, query: str, search_category: str, limit: int = 20) -> list[dict]:
        """
        > Parameters <
        --------------
        :query: 
            the query (i.e. string you want to find results for)
        :search_category:
            e.g. 'members' will return a list of Letterboxd users who match the query
        :limit:
            the maximum number of results that will be returned
                NOTE: this can also saves resources by not requesting all pages if not necessary

        > Returns <
        -----------
        list of dictionaries containing search results
            e.g. a query of 'Avenger Dogs' to the 'films' category might return:
            [
                {'name': 'Avenger Dogs', 'link': 'avenger-dogs'}, 
                {'name': 'Avenger Dogs 2: Wonder Dogs', 'link': 'avenger-dogs-2-wonder-dogs'}, ...
            ]
        """
        logging.debug(f"Finding item: '{query}' with the search category '{search_category}' and a limit of {limit}")

        if search_category not in (valid_search_categories := self.get_page_methods.keys()):
            raise ValueError(f"Invalid search_category: {search_category}\nUse one of the following: {valid_search_categories} ")
        
        # Scrape results
        return self._get_results(query, search_category, limit)

    """
    ** Methods for scraping data given a ul tag containing a result
    """

    @staticmethod
    def _get_page_members(ul) -> list[dict]:
        """
        Get a page of Letterboxd search results for members
        """
        get_display_name = lambda i:i.text.strip()
        get_usernmae = lambda i:i.get('href').strip('/')
        return [
            {
                'username': get_usernmae(i),
                'display_name': get_display_name(i)
            } for i in ul.find_all('a', class_='name')
        ]

    @staticmethod
    def _get_page_films(ul) -> list[dict]:
        """
        Get a page of Letterboxd search results for films
        """

        pattern = r"(?:/film/)([\w\d-]+)/"
        get_name = lambda i:i.find('a').text.rstrip(i.find('a', attrs={'href': re.compile(r"/films/year/\d{4}/")}).text).strip()
        get_link = lambda i:re.findall(pattern, i.find('a').get('href'))[0]
        return [
            {
                'name': get_name(i),
                'link': get_link(i)
            } for i in ul.find_all('span', class_='film-title-wrapper')
            ]

    @staticmethod
    def _get_page_lists(ul) -> list[dict]:
        """
        Get a page of Letterboxd search results for lists
        """
        get_name = lambda i:i.find('h2', class_='title-2 prettify').text.strip()
        get_link = lambda i:i.find('a').get('href')
        get_owner_username = lambda i:i.get('data-person')
        return [
            {
                'name': get_name(i),
                'link': get_link(i),
                'owner-username': get_owner_username(i)
            } for i in ul.find_all('section', class_='list')
        ]

    @property
    def get_page_methods(self) -> dict:
        """
        Dictionary containing methods pertaining to extracting data
        from a ul tag in Letterboxd search results
        """
        return {
            i.split('_')[-1]: getattr(self, i) for i in dir(self) 
            if i != 'get_page_methods' and callable(getattr(self, i)) and '_get_page_' in i
            }

    def make_substring(self, query: str, search_category: str, page_num: int = 1) -> str:
        """ 
        Given a search query, the category of search and the page number of search,
            returns a suburl for making a request based on that data
        """
        return '/'.join((self.suburl_search_prefix, search_category, query, 'page', str(page_num)))

    

# Testing code
if __name__ == '__main__':
    pass

    # f = Find()

    # result_member = f(
    #     'lucindaj', 'members', limit = 30
    # )

    # result_film = f(
    #     'avenger dogs', 'films', limit = 30
    # )

    # result_list = f(
    #     'furry', 'lists', limit = 2
    # )




