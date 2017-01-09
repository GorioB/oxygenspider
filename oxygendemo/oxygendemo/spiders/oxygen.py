# -*- coding: utf-8 -*-
import re
import scrapy

from oxygendemo.items import Product
from pyquery import PyQuery as pq
from scrapy.http import Request, FormRequest
from scrapy.linkextractors import LinkExtractor
from scrapy.spiders import CrawlSpider, Rule
from urlparse import urlsplit


class OxygenSpider(CrawlSpider):
    name = 'oxygenboutique.com'
    allowed_domains = ['oxygenboutique.com']
    base_url = 'https://oxygenboutique.com'
    start_urls = [base_url]

    # Oxygen Boutique's search page returns all items if you pass an empty query
    # So I could just start at that page and have near perfect efficiency
    # However, it doesn't seem like good practice
    # And I wouldn't have to write any rules

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

    def start_requests(self):
        return [FormRequest(
            'https://oxygenboutique.com/frontendhandler.ashx',
            formdata={
                'Action': 'UpdateCurrency',
                'NewCurrency': '519EFDE3-30C5-49EF-8F8D-AD1ACF82DB0A',
                'NewCountry': 'United States'
            },
            callback=self._start_crawl
        )]

    def _start_crawl(self, response):
        for url in self.start_urls:
            yield Request(url)

    def parse_item(self, response):
        self.body = pq(response.body)
        item = Product()

        item['gender'] = 'F'
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
        # price = price.replace(u'\xa3', '').replace(',', '').strip().split()
        price = price.replace('$', '').replace(',', '').strip().split()

        discounted_price = float(price[-1].replace(',', '') or '0')
        full_price = price[0] or '0'

        discount = ((float(full_price.replace(',', '')) - discounted_price) /
                    float(full_price.replace(',', ''))) * 100
        return full_price, discount

    def get_description(self):
        accordion = self.body('#accordion div div')
        text_desc = accordion.eq(0).text()
        size_fit_desc = '. '.join([line.text() for line in accordion.eq(1)('div div').items() if line.text() != ''])
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
        if match:
            return match.group(1)
        return None

    def get_stock_status(self):
        return {i.text(): 1 if i.attr('style') == 'display:none;' else 3
                for i in self.body('#SizePanel a').items()}
