# VERSION: 2.3
# AUTHORS: sa3dany, Alyetama, BurningMop, scadams

# LICENSING INFORMATION
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import re
from html.parser import HTMLParser
import concurrent.futures

from helpers import download_file, retrieve_url
from novaprinter import prettyPrinter

# Precompile the magnet regex pattern once for efficiency.
MAGNET_REGEX = re.compile(r'href="(magnet:[^"]+)"', re.MULTILINE)

class one337x(object):
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
        def error(self, message):
            pass

        A, TD, TR, HREF, TBODY, TABLE = ('a', 'td', 'tr', 'href', 'tbody', 'table')

        def __init__(self, url):
            HTMLParser.__init__(self)
            self.url = url
            self.row = {}
            self.column = None
            self.insideRow = False
            self.foundTable = False
            self.foundResults = False
            self.rows = []  # Accumulate rows from this page.
            self.parser_class = {
                'name': 'name',
                'seeds': 'seeds',
                'leech': 'leeches',
                'size': 'size'
            }

        def handle_starttag(self, tag, attrs):
            params = dict(attrs)
            if not self.foundResults and 'search-page' in params.get('class', ''):
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
                        break
                return

            if self.insideRow and tag == self.A:
                if self.column != 'name' or self.HREF not in params:
                    return
                link = params[self.HREF]
                if link.startswith('/torrent/'):
                    # Instead of fetching the torrent detail page here (which is slow),
                    # simply store its full URL in the row.
                    link = f'{self.url}{link}'
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
                if self.row:
                    self.rows.append(self.row)
                self.row = {}

    def download_torrent(self, info):
        print(download_file(info))

    def fetch_magnet(self, detail_link):
        # Retrieve the torrent detail page and extract the magnet link.
        torrent_page = retrieve_url(detail_link)
        match = MAGNET_REGEX.search(torrent_page)
        if match:
            return match.group(1)
        return None

    def search(self, what, cat='all'):
        what = what.replace('%20', '+')
        category = self.supported_categories[cat]
        page = 1
        while True:
            if category:
                page_url = f'{self.url}/category-search/{what}/{category}/{page}/'
            else:
                page_url = f'{self.url}/search/{what}/{page}/'
            html = retrieve_url(page_url)
            # Create a new parser for each page.
            parser = self.MyHtmlParser(self.url)
            parser.feed(html)
            parser.close()

            # Process all torrent detail pages concurrently.
            with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
                futures = {}
                for row in parser.rows:
                    if 'desc_link' in row:
                        # Submit a concurrent task to fetch the magnet link.
                        future = executor.submit(self.fetch_magnet, row['desc_link'])
                        futures[future] = row
                    else:
                        # If there's no detail link, just output the row.
                        prettyPrinter(row)
                for future in concurrent.futures.as_completed(futures):
                    magnet = future.result()
                    row = futures[future]
                    if magnet:
                        row['link'] = magnet
                        row['engine_url'] = self.url
                    prettyPrinter(row)

            # Check for pagination: break if this is the last page.
            if '<li class="last">' not in html:
                break
            page += 1
