"""
    For creating a requests.Session object that is used to make requests to Letterboxd
"""

# Local
from exceptions import PageNotFound, PageForbiddenError, LetterboxdError
import util

# Data
import datetime
import json
import os
import pickle
import re
from typing import Any, Callable, Self

# Web scraping
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse

# Quality of life
from rich import traceback
from rich import pretty
from rich import print
from rich.console import Console
from rich.logging import RichHandler

# Password masking
import stdiomask

# ============ Logging ============ #

from rich.logging import RichHandler
import logging

logging.basicConfig(
    level = logging.DEBUG,
    format = "%(message)s",
    datefmt = "[%X]",
    handlers = [RichHandler()]
)

# ============ QOL ============ #

# Pretty traceback errors
traceback.install()

# Pretty output in console
pretty.install()

# Rich console
console = Console(theme = util.style_theme)

# ============ Credentials ============ #

class Credentials:
    """ Get credentials from the user of the application """

    def __init__(self) -> None:
        return self._get_credentials()

    def __repr__(self):
        return f"{self.__class__.__name__} ({self})"

    def __str__(self):
        if not hasattr(self, 'password'):
            raise Exception("Credentials not yet set")

        return f'''
        Username: {self.username}
        Password: {len(self.password) * '*'}
        '''

    def _get_credentials(self) -> None:
        """
        > Modifies <
        ------------
        Sets :username: and :password: based on user input
        """
        self._get_username()
        self._get_password()

    def _get_username(self) -> None:
        """ Get the username from the user """
        while True:
            value = input('Letterboxd username: ').strip()
            if value: 
                self.username = value
                return
            print("You didn't enter a username!")

    def _get_password(self) -> None:
        """ Get the password from the user """
        while True:
            value = stdiomask.getpass(prompt='Letterboxd Password: ' ).strip()
            if value:
                self.password = value
                return
            print("You didn't enter a password!")


# ============ Response Errors ============ #

class LetterboxdResponseDict(dict):
    """
        In the response text of some requests to Letterboxd, there is dictionary
        This dictionary tells you the result of the request (i.e. successs / failure)
            and sometimes there is an accompanying message giving more detail
        This class gathers information from that dictionary if it exists
        
        If that dictionary doesn't exist, it returns a dictionary where the result is unknown, 
            signifying that the success of the request is unknown
    """

    successful_result = (True, 'success')

    def __init__(self, response:requests.Response) -> None:

        self.response = response
        
        # Call the parent method to instantiate the dictionary
        letterboxd_response_dict = self.get_letterboxd_response_dict()
        super().__init__(**letterboxd_response_dict)

        # Raise any errors
        self.raise_errors()

    def __str__(self):
        return f"""
        URL: {self.response.url}
        Result: {self.result}
        Message(s): {self.messages}
        Error: {self.error}
        """
    
    def __repr__(self):
        return f"{self.__class__.__name__}: ({self})"  
    
    @property
    def has_response_dict(self) -> bool:
        """ Information from Letterboxd about the response found in the HTML """
        return any(self.values())
    
    @property
    def result(self) -> str | None:
        """ The result of the request according to Letterboxd """
        return self.get('result')
    
    @property
    def messages(self) -> str | None:
        """ Feedback about the request from Letterboxd """
        return self.get('messages', [])
    
    @property
    def error(self) -> str | None:
        """ Error(s) that resulted from the request according to Letterboxd """
        return self.get('error')
    
    @property
    def ok(self) -> bool:
        """ Returns True if the request was successful, else False """
        if not self.response.ok:
            return False
        if self.result is not None and self.result not in self.successful_result:
            return False
        return not self.error
    
    def raise_errors(self) -> None:
        
        if self.ok:
            # No errors to raise
            return
        
        if self.has_response_dict:
            string = str(self)
            match self.error:
                case 'not_found':
                    raise PageNotFound(string)
                case 'forbidden':
                    raise PageForbiddenError(string)
                case _:
                    # Default case
                    raise LetterboxdError(string)
        
        # No response dict found - fallback on regular Response error
        self.response.raise_for_status()

    def get_letterboxd_response_dict(self) -> dict:
        letterboxd_response_dict = {}
        try:
            letterboxd_response_dict.update(json.loads(self.response.text))
            assert 'result' in letterboxd_response_dict
        except:
            pass

        soup = BeautifulSoup(self.response.text, 'lxml')
        letterboxd_response_dict['error'] = self._get_letterboxd_errors(soup)
        return letterboxd_response_dict    

    def _get_letterboxd_errors(self, soup: BeautifulSoup) -> str | None:
        """
        Separately to the response dict, 
            sometimes there are errors flagged by Letterboxd in the script tags of the HTML response
        This method returns a concatenated string of those errors
        """
        # Look for errors flagged by Letterboxd in the script tags of the response
        if not soup.find('body', class_='error'):
            # No errors found
            return None
        
        # For whatever reason, you cannot search the soup.text
        # You have to first find the script tags and get their text attribute
        error_pattern = r"'/errors/([\w]+)'"
        concatenated_text = ''.join(s.text for s in self.soup.find_all('script'))
        error_string = util.find_one(error_pattern, concatenated_text)
        return error_string
 

# ============ Session ============ #

def save_session(func:Callable) -> Any:
    """
    ** Decorator **
    1. Executes the funcion
    2. Saves the session (writes the pickle to file)
    3. Returns result of function execution
    """
    def inner(self, *args, **kwargs):
        result = func(self, *args, **kwargs)
        self.save()
        return result
    return inner


class LunaboxdSession(requests.Session):
    """
    Create a session object that can be used to make requests as the user
    Inherits from requests.Session and adds Letterboxd-specific functionality
        - e.g. requests have default url prefix of letterboxd.com (the homepage)
    """

    # User agent identifies the browser/software making the request
    # Tailors response accordingly (e.g. desktop vs. mobile)
    # Passing the user agent makes requests less likely to be perceived as spam
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36 Edg/91.0.864.59"

    # The homepage of the site
    URL_MAIN = "https://letterboxd.com/"

    # Import suburls to main pages
    suburl_login = "user/login.do/"
    suburl_logout = "user/logout.do/"

    # Cookie name for FilmFilter
    # FilmFilter is the filter used to (surprise) filter films on the website
        # e.g. 'show-watched', 'hide-liked'
    # These filters are maintained by a session cookie. 
    # For example if you use the 'show-watched' filter, across the site, 
        # you will only see films you have watched until you turn this filter off
    # This is the name of the cookie that stores this information
    cookie_name_filmFilter = 'filmFilter'

    # The string for the CSRF token cookie name (allows for persistent requests)
    cookie_name_csrf = 'com.xk72.webparts.csrf'

    # Session cache filepath
    # So that when the program is restarted within a certain period of time,
        # the user does not need to re-enter login information
    filename_session = f"../cache_files/{urlparse(URL_MAIN + suburl_login).netloc}_session.bat"

    ## =====================================================================

    # The __attrs__ class attribute
    # is called in the requests.Session class by the __getstate__() method

    # In pickle, the __dict__() method is serialised *unless* the __getstate__() method
    # is called, in which cases the return object of the __get_state() will be pickled
    # as the contents of the instance

    # In requests.Session, the __getstate__() returns a list of 
    # getattr(x) for x in __attrs__, which is not a real dunder method, but 
    # just a list defined within the same requests.Session class.
    # It contains a strings correesponding to the attribute names of the instance

    # When pickleing, this method is called, so that means these items alone are pickled
    # Hence, to pickle additional variables here, we must add them 
    # to the __attrs__ class variable

    __attrs__ = requests.Session.__attrs__

    # We'd like to pickle the following variables for when the session is unpickled
    __attrs__.extend((
        'login_credentials',
        'headers',
        'cookies',
        'Credentials'
    ))

    ## =====================================================================

    def __init__(self) -> None:
        """
        Creates a Session object used to make persistent requests as the user
        
        1. Calls the parent method to get requests.Session functionality
        2. Update session headers to include user agent
        3. Get login credentials from the user through user input
        4. Make a GET request to get the cookies
        5. Log in
        """

        # 1. Initialise parent method
        super().__init__()

        # 2. Update session headers w/ the user agent
        self.headers.update({'user-agent': self.USER_AGENT})

        # 3. Get login credentials from the user
        self.get_credentials()

        # 4. Make GET request to Letterboxd to get cookies (required for login)
        self.get('')

        # 5. Login to Letterboxd
        self.login()

    def __repr__(self):
        return f"{self.__class__.__name__} ({self})"

    def __str__(self):
        return f'''
        Username: {self.username}
        Password: {bool(self.login_credentials.password)}
        Logged In: {self.logged_in_check()}
        '''

    """
    ** Pickleing
    """

    @classmethod
    def load(cls) -> Self:
        """
        ** Alternative Constructor **

        If an instance has been pickled to the expected location,
            1. Attempt to load it
            2. If it hasn't expired, returns it

        > Returns <
        -----------
        Cached instance of the class is available, else new instance
        """

        file_path = cls.filename_session
        try:
            # Open cache file in read bytes mode
            with open(file_path, 'rb') as pf:
                session_unpickled = pickle.load(pf)
        except FileNotFoundError:
            logging.info(f"Could not find saved pickle file at {file_path}. So creating new session...")
            return cls() # Return new instance
        except:
            raise
        
        # Test pickle session - is it logged in?
        one_hour_ago = datetime.datetime.now() - datetime.timedelta(hours=1)
        if not (value := session_unpickled.logged_in_check()) or not util.file_updated_after(cls.filename_session, one_hour_ago):
            logging.debug(f"Session unpickled logged_in_check: {value}")
            # Assume session has expired
            logging.info("Session was not logged in. So creating new session...")
            return cls()

        # The pickled session is valid and still logged in - so return it 
        logging.info("Loaded session...")
        return session_unpickled

    def save(self) -> None:
        """ Save the Session to a bat file """
        with open(self.filename_session, 'wb') as pf:
            pickle.dump(self, pf)

    @classmethod
    def delete_cache_file(cls) -> None:
        """
        > Modifies <
        ------------
        If a pickled session is saved to the expected file path, deletes it
        """
        file_path = cls.filename_session
        if os.path.exists(file_path):
            os.remove(file_path)

    """
    ** Requests
    """

    @property
    def csrf_token(self) -> dict:
        """
        Returns the CSRF tokenof the session, assings to variable
        This variable is then used by the overloaded request method

        NOTE: this token is necessary for post requests
        """
        return {'__csrf': self.cookies.get(self.cookie_name_csrf)}

    def _make_data(self, data:dict):
        if not self.csrf_token:
            return data
        return self.csrf_token | data

    @save_session
    def request(self, method: str, suburl: str = '', **kwargs) -> requests.Response():
        """
        ** Overload **
        
        Customise requests to
            - Use URL_MAIN (Letterboxd) url prefix
            - Include the __CSRF token
        """

        # Add the CSRF token to the data of every request (once it's available)
        kwargs['data'] = self._make_data(kwargs.get('data', {}))

        logging.debug(f"data for request: {kwargs['data']}")

        # If the URL_MAIN (i.e. main website url) is in the suburl, remove it
        suburl = suburl.replace(self.URL_MAIN, '')

        # Make the request
        response = super().request(method, url=f"{self.URL_MAIN}{suburl}", **kwargs)

        # Add Letterboxd's feedback about the request to the Response object 
        # This will also raise any errors flagged by Letterboxd
        response.letterboxd_response = LetterboxdResponseDict(response)

        # Return the Response object
        return response

    """
    ** Credentials | Logging in | Logging out
    """

    def get_credentials(self) -> None:
        """
        Ask the user for their details

        > Modifies <
        ------------
        :self.login_credentials:
            Sets to new credentials input by the user
        """
        # If already logged in as another user, log out
        if self.logged_in_check(): 
            self.logout()
        self.login_credentials = Credentials()

    def login(self) -> None:
        """
        Login to Letterboxd
        """        
        # Get credentials for login data
        credentials = vars(self.login_credentials)
        
        # Make login request
        response = self.request('POST', self.suburl_login, data=credentials)

        # Confirmation message
        console.print(f"\nSuccessfully logged in as {self.username}!", style='success')

    def logout(self) -> None:
        """
        Attempts to logout of Letterboxd
        """
        if not self.logged_in_check():
            logging.info(f"Already logged out")
            return

        # Logout
        response = self.request('GET', self.suburl_logout)
        self._raise_lb_response_dict(response)

    def logged_in_check(self) -> bool:
        """
        Verify the session is logged_in

        > Modifies <
        ------------
        self.logged -> True/False (depending on result of login)

        > Returns <
        -----------
        self.logged_in
        """
        ## Get user's profile soup
        try:
            response = self.request('GET', f"{self.username}/")
            # self.request('POST', suburl = "lucindaj/follow/")
        except AttributeError:
            # Username has not been set
            return False
        except PageNotFound:
            logging.debug(f"Invalid username: {self.username}")
            return False
        # except LBResponseDictError:
        #     raise
        else:
            soup = BeautifulSoup(response.text, 'lxml')

            # Part of the script that says if user is logged_in
            # Finding it == user IS logged_in
            pattern = rf"person.username = \"{self.username.lower()}\"; person.loggedin = true;"
            script_text = ''.join([i.text for i in soup.find_all('script')]).lower()      
            match = re.search(pattern, script_text)
            return bool(match)
        
    """
    ** Attributes
    """

    @property
    def username(self) -> str:
        """ Return the LBSession's username """
        return self.login_credentials.username

    @property
    def filmFilter(self) -> set:
        """
        The filmFilter is the name given the cookie corresponding to 
        the filter option on Letterboxd which allows you to (by default) filter films by criteria 
        (e.g. 'show-watched' -> only shows you films you have watched)

        The filmFilters take the form of a list (you can apply more than one filter at once)
        """
        filmFilters = self.cookies.get(self.cookie_name_filmFilter, None)
        return set() if not filmFilters else set(filmFilters.split('%20'))

    @filmFilter.setter
    def filmFilter(self, filters: set) -> None:
        """ Setter for the filmFilter cookie """
        logging.debug(f"Setting filmFilter to {filters}")
        self.cookies.set(self.cookie_name_filmFilter, '%20'.join(filters))

    def filmFilter_reset(self) -> None:
        """ Resetter for the filmFilter cookie """
        self.filmFilter = ''

    def filmFilter_extend(self, filters: set) -> None:
        """ Combine existing filters w/ new ones """
        new_filters = self.filmFilter | filters
        self.filmFilter = new_filters 

    def filmFilter_remove(self, filters: set) -> None:
        """ Subtract new filters from existing ones """
        new_filters = self.filmFilter - filters
        self.filmFilter = new_filters


# Testing code
if __name__ == '__main__':
    pass
    
    session = LunaboxdSession.load()
    


