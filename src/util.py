"""
    General utility code
"""

# Data
import datetime
import os
import re
import unicodedata

# Type validation
from typing import Any, Callable

# Quality of life
from rich.theme import Theme # styling


# Colours
LIGHT_BLUE = "#AED6F1"

# Create custom style options
style_theme = Theme({
    'danger': 'red on white bold',
    'success': 'green on white bold',
    'info': f"{LIGHT_BLUE} dim"   
})


def guess_number(check_guess: Callable, max_num: int, min_num:int = 1) -> int:
    if max_num <= min_num:
        raise ValueError(f"Invalid max_num: {max_num} and min_num: {min_num} combination")
    low = min_num
    high = max_num

    while low <= high:
        mid = (low + high) // 2
        guess_result = check_guess(mid)

        match guess_result:
            case 'correct': return mid
            case 'low': low = mid + 1
            case 'high': high = mid - 1


def percentage(part, total, round_to:int):
    return round((part / total) * 100, round_to)

"""
** Decorators
"""

def custom_repr(cls):
    """ Decorates a class, giving it a custom __repr__ method """
    def __repr__(self):
        """ Returns the obj.__str__ enclosed in the name of its class """
        return f"{cls.__name__}({self.__str__()})"

    # Set the class's __repr__
    cls.__repr__ = __repr__
    return cls


def empty_str_if_none(*attr_names):
    """
    :attr_name:
        the name of the instance attribute I want to check is None
    """
    def decorator(func: Callable):
        """
        :func:
            the function to decorate
        """
        def wrapper(self):
            """
            :self:
                the instance
            """
            # Return empty string if the attribute is None
            if all([getattr(self, attr_name) is None for attr_name in attr_names]):
                return ''
            # Otherwise return the result of the function
            return func(self)
        return wrapper
    return decorator

"""
** Regex
"""

def find_one(pattern: str, string: str) -> str | None:
    """ Find only one result using regex """
    if not (result := re.findall(pattern, string)):
        return None
    return result[0]

"""
** Collections
"""

def multi_replace(text: str, find_replace: dict) -> str:
    """
    > Parameters <
    --------------
    :find_replace:
        Example ({'hello': 'welcome', 'world': 'back'})
            "hello world~" -> "welcome back~"
    """
    for k, v in find_replace.items():
        text = text.replace(k,v)
    return text


def key_max(d: dict, max_num: int = 1, multiple_maxes: bool = False) -> Any:
    """
    :d:
        the dictionary object to get the max key from
    :max_num:
        e.g. d={'1':10, '2':20, '3': 30, '4': 40}, max_num=1 -> '4'
        e.g. d={'1':10, '2':20, '3': 30, '4': 40}, max_num=3 -> '2'
    :multiple_maxes:
        e.g. d={'1':10, '2':20, '3': 40, '4': 40}, max_num=1 -> ('3', '4')        
    """
    d = d.copy()
    assert len(d) >= max_num
    if max_num == 1: 
        m = max(zip(d.values(), d.keys()))[1]
    else:
        n = 1
        max_keys = []
        while n <= max_num:
            m = max(zip(d.values(), d.keys()))[1]
            max_keys.append(m)
            d.pop(m)
            n += 1
    if multiple_maxes:
        return tuple(max_keys)
    else:
        return m

def trim_array(array:list, n:int):
    """
    > Parameters <
    --------------
    array (list / tuple)
        the object you want to trim
    n (int)
        the number you want to trim it down to

    > Returns <
    -----------
    trimmed_array (list / tuple) - same as array type
    """
    if not array or len(array) <= n:
        return array
    return array[:n]


def preview_array(array:list, n=10) -> str:
    """ 
    Returns the first n items in an array
    So that long arrays can be printed prettily 
    """
    if not array: 
        return None
    trimmed_array = trim_array(array, n)
    preview = ', '.join([str(x) for x in trimmed_array])
    return f"{preview}..." if len(array) > n else preview

"""
** Strings & Characters
"""

# Converts a float to an int if it equates to a whole number
whole_num_to_int = lambda x: int(x) if int(x) == x else x


def _lowerfy_func(item):
    if type(item) not in (tuple, list, set, str, dict):
        return item
    elif isinstance(item, str):
        return item.lower()
    elif isinstance(item, list):
        return [i.lower() if isinstance(i, str) else i for i in item]
    elif isinstance(item, tuple):
        return (i.lower() if isinstance(i, str) else i for i in item)
    elif isinstance(item, set):
        return {i.lower() if isinstance(i, str) else i for i in item}
    elif isinstance(item, dict):
        return {k:v if isinstance(v, str) else v for k,v in item.items()}


def lowerify(func: Callable):
    def wrapper(self, *args, **kwargs):
        args = (_lowerfy_func(i) for i in args)
        kwargs = {k:_lowerfy_func(v) for k,v in kwargs}
        return func(self, *args, **kwargs)
    return wrapper


def thousand_separator(number: int | float):
    """ Adds thousand separator to number """
    return '{:,}'.format(number)


def truncate_string(string: str, max_length: int) -> str:
    """
    > Parameters <
    --------------
    string (str)
        the string whose max length will be checked
    max_length (int; > 0)
        truncate the string if it exceeds this length

    > Returns <
    -----------
    if does not exceed max_allowed_len:
        string
    else:
        truncated string to its last full world, with trailing ellipsis
    """
    if not isinstance(max_length, int) or max_length <= 0:
        raise ValueError(f"Max allowed length must be positive int")
    
    # String length is less than s
    if len(string) <= max_length:
        return string
    
    # String sliced to max_length
    truncated_string = string[:max_length]

    # Gets the index of the last space in the string
    last_space = truncated_string.rfind(" ")
    
    # If the last space in the string is not at the end of the string
    if last_space != -1:
        
        # Truncate string further according to where 
        # the last space appears in the truncated string 
        # e.g. 'hello this is my world' -> 'hello this is m -> 'hello this is'
        truncated_string = truncated_string[:last_space]
    
    return f"{truncated_string}..."


remove_special_chars = lambda string, allowed=[]: unicodedata.normalize('NFKD', ''.join(c for c in string if c.isalpha() or c.isdigit() or c.isspace() or c in allowed))

# Given a dictionary (d) create a new object with the keys and values switched
swap_key_with_value = lambda d:{v:k for k,v in d.items()}

# Some Letterboxd ajax pages make use of XML character references that 
# need to be converted before sending the data in a post request
XML_CHAR_REFERENCES = {'&amp;': '&', '&lt;': '<', '&gt;': '>', '&quot;': '"', '&apos;': "'"}


def from_xml_char_reference(string:str) -> str:
    """ Remove all XML character references from a string """
    return multi_replace(string, XML_CHAR_REFERENCES)


def to_xml_char_reference(string:str) -> str:
    """ Replace characters with their XML character reference counterparts """
    return multi_replace(string, swap_key_with_value(XML_CHAR_REFERENCES))


"""
** Misc
"""

def yn(prompt) -> bool:
    """ 
    Get a Yes/No response from the user
    
    > Returns <
    -----------
    True if the first character of user's response == 'y' else False
    """
    while True:
        user_response = input(f"{prompt}\n: Y/N: ").lower().strip()
        if user_response:
            break
    return bool(user_response[0] == 'y')

def day_of_year() -> int:
    """ Returns the current day of the year """
    return datetime.datetime.now().timetuple().tm_yday


def symbol_list(nums: list, n: int, symbol:str = '|') -> list:
    max_num = max(nums)
    proportional_lengths = [round(num / max_num * n) for num in nums]
    return [symbol * length for length in proportional_lengths]


def symbol_string(nums: list, n: int, symbol: str = '|') -> None:
    return '\n'.join(symbol_list(nums, n, symbol))


"""
** Files
"""

def assess_file_age(file_path: str) -> datetime.datetime:
    """ Returns the datetime the file was last modified """
    timestamp = os.path.getmtime(file_path)
    last_modified_datetime = datetime.datetime.fromtimestamp(timestamp)
    return last_modified_datetime
    
def file_updated_after(file_path: str, datetime: datetime.datetime) -> bool:
    """ Returns True if the file_path was updated after the datetime passed, else False """
    if not os.path.exists(file_path):
        return False
    return assess_file_age(file_path) > datetime


class TypeCheckError(TypeError):
    """
    Exceptions raised by type_check function
    """
    def __init__(self, message:str):
        super().__init__(message)


def type_check(expected_types: dict):
    def decorator(func: Callable):
        def wrapper(self, *args, **kwargs):
            # Func for getting names of types when raising error
            get_names = lambda et: [i.__name__ for i in et] if isinstance(et, tuple) else et.__name__
            
            expected_types_keys = list(expected_types.keys())
            for i, expected_type in enumerate(expected_types.values()):
                if i < len(args):
                    if not isinstance(args[i], expected_type) and not any(isinstance(args[i], type) for type in expected_type):
                        raise TypeCheckError(f"Positional argument {i+1} ({expected_types_keys[i]}) should be of type {get_names(expected_type)}")
                elif expected_types_keys[i] in kwargs:
                    if not isinstance(kwargs[expected_types_keys[i]], expected_type) and not any(isinstance(kwargs[expected_types_keys[i]], type) for type in expected_type):
                        raise TypeCheckError(f"Keyword argument {expected_types_keys[i]} should be of type {get_names(expected_type)}")
                else:
                    raise TypeCheckError(f"Argument {expected_types_keys[i]} is missing")
            return func(self, *args, **kwargs)
        return wrapper
    return decorator


# Testing code
if __name__ == '__main__':
    pass

    # @type_check(expected_types={'string': str, 'number': int})
    # def print_me(string: str, number: int):
    #     print(string, number)


    # print_me('hello world', 123) 
    # print_me('hello world', number=456) 
    # print_me(string='hello world', number=789) 
    # print_me(string='hello world', number='osaikj')