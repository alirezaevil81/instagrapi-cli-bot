from colorama import Fore, Style
from prettytable import PrettyTable

# all text alert

def text_success(message):
    return f"{Fore.GREEN}{Style.BRIGHT}[Successful]:{Style.RESET_ALL}{message}"

def text_error(message,exception = ''):
    return f"{Fore.RED}{Style.BRIGHT}[Error]:{Style.RESET_ALL}{message}{exception}"

def text_warning(message):
    return f"{Fore.YELLOW}{Style.BRIGHT}[Warning]:{Style.RESET_ALL}{message}"

# all color text

def text_blue(text):
    return f"{Fore.BLUE}{Style.BRIGHT}{text}{Style.RESET_ALL}"

def text_yellow(text):
    return f"{Fore.YELLOW}{Style.BRIGHT}{text}{Style.RESET_ALL}"

def text_red(text):
    return f"{Fore.RED}{Style.BRIGHT}{text}{Style.RESET_ALL}"

def text_cyan(text):
    return f"{Fore.CYAN}{Style.BRIGHT}{text}{Style.RESET_ALL}"

def text_magenta(text):
    return f"{Fore.MAGENTA}{Style.BRIGHT}{text}{Style.RESET_ALL}"

def text_green(text):
    return f"{Fore.GREEN}{Style.BRIGHT}{text}{Style.RESET_ALL}"


# table create

def table_creator(headers, rows):
    table = PrettyTable()
    table.field_names = headers
    for row in rows:
        table.add_row(row)
    return table


