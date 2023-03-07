"""
    Custom exceptions for the application
"""

class LunaboxdError(Exception):
    """ Errors pertaining to the limitations / restrictions of the app """
    def __init__(self, message: str):
        super().__init__(message)

class LetterboxdError(Exception):
    """ Errors raised directly by Letterboxd 
    / or the limitations / restrictions of the website """
    def __init__(self, message: str):
        super().__init__(message)

class PageNotFound(LetterboxdError):
    """ This page does not exist! """
    def __init__(self, url: str):
        super().__init__(f"URL: {url}")

class PageForbiddenError(LetterboxdError):
    """ The session user doesn't have permission to access this page """
    def __init__(self, url: str):
        super().__init__(f"URL: {url}")
        


