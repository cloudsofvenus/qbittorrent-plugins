import re
from html.parser import HTMLParser

from helpers import download_file, retrieve_url
from novaprinter import prettyPrinter

# Precompile the magnet regex pattern
MAGNET_REGEX = re.compile(r'href="(magnet:[^"]+)"')

class Plugin1337x(object):
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
        # These variables mirror the original definitions.
        A, TD, TR, HREF, TBODY, TABLE = ('a', 'td', 'tr', 'href', 'tbody', 'table')

        def __init__(self, url):
            super().__init__()
            self.url = url
            self.row = {}
            self.column = None
            self.insideRow = False
            self.foundTable = False
            self.foundResults = False
            self.parser_class = {
                'name': 'name',
                'seeds': 'seeds',
                'leech': 'leeches',
                'size': 'size'
            }

        def handle_starttag(self, tag, attrs):
            # Optimize attribute handling by iterating once
            params = {}
            for key, value in attrs:
                params[key] = value

            if not self.foundResults and 'class' in params and 'search-page' in params['class']:
                self.foundResults = True
                return

            if self.foundResults and tag == self.TBODY:
                self.foundTable = True
                return

            if self.foundTable and tag == self.TR:
                self.insideRow = True
                self.row = {}
                return

            if self.insideRow and tag == self.TD:
                classList = params.get('class', '')
                for columnName, classValue in self.parser_class.items():
                    if classValue in classList:
                        self.column = columnName
                        self.row[self.column] = -1
                return

            if self.insideRow and tag == self.A:
                if self.column != 'name' or self.HREF not in params:
                    return
                link = params[self.HREF]
                if link.startswith('/torrent/'):
                    link = f'{self.url}{link}'
                    torrent_page = retrieve_url(link)
                    # Use the precompiled regex
                    match = MAGNET_REGEX.search(torrent_page)
                    if match:
                        self.row['link'] = match.group(1)
                        self.row['engine_url'] = self.url
                        self.row['desc_link'] = link

        def handle_data(self, data):
            if self.insideRow and self.column:
                if self.column == 'size':
                    data = data.replace(',', '')
                self.row[self.column] = data
                self.column = None

        def handle_endtag(self, tag):
            if tag == self.TABLE:
                self.foundTable = False
            if self.insideRow and tag == self.TR:
                self.insideRow = False
                self.column = None
                if not self.row:
                    return
                prettyPrinter(self.row)
                self.row = {}

    def download_torrent(self, info):
        print(download_file(info))

    def search(self, what, cat='all'):
        parser = self.MyHtmlParser(self.url)
        what = what.replace('%20', '+')
        category = self.supported_categories.get(cat)
        page = 1
        while True:
            if category:
                page_url = f'{self.url}/category-search/{what}/{category}/{page}/'
            else:
                page_url = f'{self.url}/search/{what}/{page}/'
            html = retrieve_url(page_url)
            parser.feed(html)
            if '<li class="last">' not in html:
                # exists on every page but the last
                break
            page += 1
        parser.close()
