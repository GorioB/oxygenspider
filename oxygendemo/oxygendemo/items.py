# -*- coding: utf-8 -*-

# Define here the models for your scraped items
#
# See documentation in:
# http://doc.scrapy.org/en/latest/topics/items.html

import scrapy


class Product(scrapy.Item):
    type = scrapy.Field()
    gender = scrapy.Field()
    designer = scrapy.Field()
    code = scrapy.Field()
    name = scrapy.Field()
    description = scrapy.Field()
    raw_color = scrapy.Field()
    image_urls = scrapy.Field()
    usd_price = scrapy.Field()
    sale_discount = scrapy.Field()
    stock_status = scrapy.Field()
    link = scrapy.Field()

    eur_price = scrapy.Field()
    gbp_price = scrapy.Field()
