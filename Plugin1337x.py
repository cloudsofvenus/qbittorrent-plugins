import re
from html.parser import HTMLParser

from helpers import download_file, retrieve_url
from novaprinter import prettyPrinter

# Precompile the magnet regex pattern
MAGNET_REGEX = re.compile(r'href="(magnet:[^"]+)"')

class Plugin1337x:
    url = 'https://1337x.to'
    name = '1337x'
    supported_categories = {
        'all': None,
        'anime': 'Anime',
        'software': 'Apps',
        'games': 'Games',
        'movies': 'Movies',
        'music': 'Music',
        'tv': 'TV',
    }

    class MyHtmlParser(HTMLParser):
        # Mapping our desired columns to expected class name parts
        parser_class = {
            'name': 'name',
            'seeds': 'seeds',
            'leech': 'leeches',
            'size': 'size'
        }
        TAG_A = 'a'
        TAG_TD = 'td'
        TAG_TR = 'tr'
        TAG_TBODY = 'tbody'
        TAG_TABLE = 'table'

        def __init__(self, base_url):
            super().__init__()
            self.base_url = base_url
            self._reset_state()

        def _reset_state(self):
            self.row = {}
            self.current_column = None
            self.inside_row = False
            self.found_table = False
            self.found_results = False

        def handle_starttag(self, tag, attrs):
            # Instead of converting attrs to a dict, iterate once to extract needed values.
            class_val = None
            href_val = None
            for key, value in attrs:
                if key == 'class':
                    class_val = value
                elif key == 'href':
                    href_val = value

            # Mark the start of results if the "search-page" class is found.
            if not self.found_results and class_val and 'search-page' in class_val:
                self.found_results = True
                # Continue processing in case this tag is also important.
            
            # If we haven't found the results block yet, skip further processing.
            if not self.found_results:
                return

            if tag == self.TAG_TBODY:
                self.found_table = True
                return

            if self.found_table and tag == self.TAG_TR:
                self.inside_row = True
                self.row = {}
                return

            if self.inside_row and tag == self.TAG_TD:
                if class_val:
                    # Check against each expected column type.
                    for col_name, expected_class in self.parser_class.items():
                        if expected_class in class_val:
                            self.current_column = col_name
                            self.row[col_name] = None
                            break
                return

            if self.inside_row and tag == self.TAG_A:
                # Process only if we're in the "name" column and an href exists.
                if self.current_column == 'name' and href_val and href_val.startswith('/torrent/'):
                    torrent_page_url = f'{self.base_url}{href_val}'
                    torrent_page = retrieve_url(torrent_page_url)
                    match = MAGNET_REGEX.search(torrent_page)
                    if match:
                        self.row['link'] = match.group(1)
                        self.row['engine_url'] = self.base_url
                        self.row['desc_link'] = torrent_page_url

        def handle_data(self, data):
            if self.inside_row and self.current_column:
                # For size values, remove commas and trim whitespace.
                if self.current_column == 'size':
                    data = data.replace(',', '')
                self.row[self.current_column] = data.strip()
                self.current_column = None

        def handle_endtag(self, tag):
            if tag == self.TAG_TABLE:
                self.found_table = False
            if self.inside_row and tag == self.TAG_TR:
                self.inside_row = False
                if self.row:
                    prettyPrinter(self.row)
                self.row = {}

    def download_torrent(self, info):
        print(download_file(info))

    def search(self, what, cat='all'):
        # Replace '%20' with '+' if present.
        search_term = what.replace('%20', '+')
        category = self.supported_categories.get(cat)
        page = 1

        while True:
            if category:
                page_url = f'{self.url}/category-search/{search_term}/{category}/{page}/'
            else:
                page_url = f'{self.url}/search/{search_term}/{page}/'
            
            html = retrieve_url(page_url)
            # Create a fresh parser per page to avoid state bleed.
            parser = self.MyHtmlParser(self.url)
            parser.feed(html)
            parser.close()

            # If no "last" page indicator exists, break out.
            if '<li class="last">' not in html:
                break
            page += 1
