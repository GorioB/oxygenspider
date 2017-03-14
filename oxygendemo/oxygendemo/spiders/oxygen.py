# -*- coding: utf-8 -*-
import re
import scrapy

from oxygendemo.items import Product
from pyquery import PyQuery as pq
from scrapy.http import Request, FormRequest
from scrapy.linkextractors import LinkExtractor
from scrapy.signals import spider_idle
from scrapy.spiders import CrawlSpider, Rule
from scrapy.xlib.pydispatch import dispatcher
from urlparse import urlsplit


class OxygenSpider(CrawlSpider):
    name = 'oxygenboutique.com'
    allowed_domains = ['oxygenboutique.com']
    base_url = 'https://www.oxygenboutique.com'
    currency_change_url = 'https://www.oxygenboutique.com/frontendhandler.ashx'
    start_urls = [base_url]

    # Oxygen Boutique's search page returns all items if you pass an empty query
    # So I could just start at that page and have near perfect efficiency
    # However, it doesn't seem like good practice
    # And I wouldn't have to write many rules

    # start_urls = ['https://www.oxygenboutique.com/search-results?q=&ViewAll=1&s=5']

    rules = (
        Rule(
            LinkExtractor(
                restrict_css='.MobileEnable > li > a',
                deny=(
                    'designer',
                    'features',
                )
            ),
            follow=True
        ),
        Rule(LinkExtractor(allow=(r'ViewAll',)), follow=True),
        Rule(LinkExtractor(restrict_css='.homeProducts > a'), callback='parse_item'),
    )

    def __init__(self, *args, **kwargs):
        self.prices = {'eur': {}, 'gbp': {}}
        self.cookie_jars_set = False
        super(OxygenSpider, self).__init__(*args, **kwargs)
        dispatcher.connect(self.do_when_idle, spider_idle)

    def start_requests(self):
        ''' acquire cookies for each currency we want'''
        return [
            FormRequest(
                self.currency_change_url,
                formdata={
                    'Action': 'UpdateCurrency',
                    'NewCurrency': '72105097-911D-4366-A591-DA74A2DAA544',
                    'NewCountry': 'Republic of Ireland'
                },
                meta={
                    'cookiejar': 'eur'
                },
                dont_filter=True,
                callback=self.get_prices
            ),
            FormRequest(
                self.currency_change_url,
                formdata={
                    'Action': 'UpdateCurrency',
                    'NewCurrency': 'b2dd6e5d-5336-4195-b966-2c81d2b34899',
                    'NewCountry': 'United Kingdom'
                },
                meta={
                    'cookiejar': 'gbp'
                },
                dont_filter=True,
                callback=self.get_prices
            ),
        ]

    def get_prices(self, response):
        return Request(
            '{}/search-results?ViewAll=1'.format(self.base_url),
            dont_filter=True,
            meta=response.meta,
            callback=self.populate_price_table
        )

    def populate_price_table(self, response):
        body = pq(response.body)
        specialchar = {'gbp': u'\u00a3', 'eur': u'\u20ac'}[response.meta['cookiejar']]
        self.prices[response.meta['cookiejar']] = {
            item('a').attr('href').strip('/'): item('.price').text().replace(specialchar, '').split()[0]
            for item in body('.homeProducts').items()
        }

    def do_when_idle(self, spider):
        ''' Make sure that converted currencies are filled out before starting crawl'''
        if spider != self:
            return

        if not self.cookie_jars_set:
            self.cookie_jars_set = True
            self.crawler.engine.crawl(
                FormRequest(
                    self.currency_change_url,
                    formdata={
                        'Action': 'UpdateCurrency',
                        'NewCurrency': '519EFDE3-30C5-49EF-8F8D-AD1ACF82DB0A',
                        'NewCountry': 'United States'
                    },
                    dont_filter=True,
                    callback=self.start_crawl
                ),
                spider
            )

    def start_crawl(self, response):
        for url in self.start_urls:
            yield Request(url)

    def parse_item(self, response):
        self.body = pq(response.body)
        item = Product()

        item['gender'] = 'F'  # Female-only store, no way to tell otherwise
        item['designer'] = self.body('.details h2 a').text()
        item['code'] = urlsplit(response.url)[2].strip("/")
        item['name'] = self.body('.details h2').text()
        item['type'] = self.get_type(item['name'])
        item['description'] = self.get_description()
        item['raw_color'] = self.get_color(item['description'])
        item['image_urls'] = [self.base_url + i.attr('id')
                              for i in self.body('#thumbnailsMobile img').items()]
        item['usd_price'], item['sale_discount'] = self.get_usd_price()
        item['stock_status'] = self.get_stock_status()
        item['link'] = response.url

        item['eur_price'] = self.prices['eur'].pop(item['code'], None)
        item['gbp_price'] = self.prices['gbp'].pop(item['code'], None)
        yield item

    def get_type(self, name):
        ''' Guess type based on certain keywords in item name.
            Oxygen Boutique doesn't indicate type on the product page.
            As of writing, there are very few items under shoes and accessories,
            which is why few words would be tagged as such.'''
        identifiers = {
            'A': [],
            'S': ['sneakers', 'boots'],
            'B': ['bag'],
            'J': [],
            'R': ['hat', 'tattoo'],
        }

        for key in identifiers:
            for word in identifiers[key]:
                if word in name.lower():
                    return key
        return 'A'  # vast majority of items in Oxygen Boutique are apparel

    def get_usd_price(self):
        price = self.body('.details .price').text()
        price = price.replace('$', '').replace(',', '').strip().split()

        discounted_price = float(price[-1].replace(',', '') or '0')
        full_price = price[0] or '0'

        discount = ((float(full_price.replace(',', '')) - discounted_price) /
                    float(full_price.replace(',', ''))) * 100
        return full_price, discount

    def get_description(self):
        accordion = self.body('#accordion div div')
        text_desc = accordion.eq(0).text()
        size_fit_desc = '. '.join(
            [line.text() for line in accordion.eq(1)('div div').items() if line.text() != '']
        )
        return ' '.join([text_desc, size_fit_desc])

    def get_color(self, description):
        ''' Oxygen Boutique doesn't specify color, apart from item name/desc.
            Not ideal but best guess without turning to external libraries. '''
        colors = (
            'black', 'blue', 'multicolor',
            'white', 'gray', 'grey',
            'pink', 'red', 'beige',
            'green', 'gold', 'brown',
            'purple', 'silver', 'animal',
            'yellow', 'floral', 'orange',
            'khaki', 'transparent', 'teal',
            'ivory',
        )

        rgx = r'\b({})\b'.format('|'.join(colors))
        match = re.search(rgx, description.lower())
        return match.group(1) if match else None

    def get_stock_status(self):
        return {i.text(): 1 if i.attr('style') == 'display:none;' else 3
                for i in self.body('#SizePanel a').items()}
