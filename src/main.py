import asyncio
import datetime
import enum
import itertools
import json
import pathlib
import smtplib
import ssl
import typing
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import httpx
import jinja2
import pydantic
import tenacity
from tqdm import tqdm

# API_KEY_PARAM = {'apikey': os.environ['API_KEY']}
# GMAIL_PASSWORD = os.environ['GMAIL_PASSWORD']
CONFIG_PATH = pathlib.Path('./src/config.json')
SMTP_PORT = 465
GMAIL_SMPT_SERVER_ADDRESS = 'smtp.gmail.com'
APP_EMAIL_ADDRESS = 'thestockalertapp@gmail.com'
LOGO_PATH = pathlib.Path('./static/logo.png')
EMAIL_SUBJECT = 'New apartment alert'
HTML_PATH = pathlib.Path('./static/email_template.html')
READABLE_DATETIME_FORMAT = '%B %d, %Y, %H:%M'
NUMBER_OF_DIGITS_TO_ROUND = 2

YAD2_FOR_SALE_API_URL = 'https://gw.yad2.co.il/feed-search-legacy/realestate/forsale'
YAD2_RENT_API_URL = 'https://gw.yad2.co.il/feed-search-legacy/realestate/rent'
DEFAULT_PARAMS = dict(propertyGroup='apartments,houses',
                      property='1,25,3,32,39,4,5,51,55,6,7',
                      forceLdLoad='true')
ALL_LISTINGS_RESULTS_PATH = pathlib.Path('./all_listings.json')


class RegionCodes(enum.IntEnum):
    SHARON = 19
    HAMERKAZ = 2
    SHFELA_AND_MISHOR_HAHOF_HADROMI = 41
    YEHUDA_AND_SHOMRON = 75
    SOUTH = 43
    JERUSALEM = 100
    HADERA_AND_VALLEYS = 101
    NORTH = 25


class Coordinates(pydantic.BaseModel):
    latitude: float
    longitude: float


class Listing(pydantic.BaseModel):
    date_listed: datetime.datetime
    city: str
    neighborhood: typing.Optional[str]
    street: typing.Optional[str]
    coordinates: typing.Optional[Coordinates]
    floor: int
    rooms: int
    area: int
    price: int
    for_sale: bool


class ContactInfo(pydantic.BaseModel):
    name: str
    email: str


class Config(pydantic.BaseModel):
    symbols: typing.List[str]
    contact_info: ContactInfo
    price_drop_percentage_threshold: float


async def main():
    config = Config.parse_obj(json.loads(CONFIG_PATH.read_text()))
    for_sale_params = DEFAULT_PARAMS | dict(price='1000000-12000000')
    rent_params = DEFAULT_PARAMS | dict(price='1000-20000')
    rent_listings = await _get_all_listings(YAD2_RENT_API_URL, rent_params, False)
    for_sale_listings = await _get_all_listings(YAD2_FOR_SALE_API_URL, for_sale_params, True)
    listings = itertools.chain(for_sale_listings, rent_listings)
    ALL_LISTINGS_RESULTS_PATH.write_text(
        json.dumps([listing.dict() for listing in listings], default=str))
    # for quote in quotes:
    #     if _should_notify(quote, config.price_drop_percentage_threshold):
    #         _notify(quote, config.contact_info)


def get_floor(raw_listing):
    for attribute in raw_listing['row_4']:
        if attribute['key'] == 'floor':
            if attribute['value'] == 'קרקע':
                return 0
            return attribute['value']
    raise ValueError('this listing doesn\'t have a floor number')


async def _get_total_amount_of_pages(yad2_client: httpx.AsyncClient) -> int:
    total_amount_of_pages = 0
    for region_code in RegionCodes:
        raw_response = await yad2_client.get('/', params=dict(topArea=region_code))
        raw_response.raise_for_status()
        response = raw_response.json()
        total_amount_of_pages += response['data']['pagination']['last_page']
    return total_amount_of_pages


async def _get_all_listings(api_url, params, for_sale) -> typing.List[Listing]:
    listings = list()
    async with httpx.AsyncClient(base_url=api_url, params=params) as yad2_client:
        total_amount_of_pages = await _get_total_amount_of_pages(yad2_client)
        with tqdm(total=total_amount_of_pages) as progress_bar:
            for region_code in RegionCodes:
                for attempt in tenacity.Retrying(stop=tenacity.stop_after_attempt(3),
                                                 wait=tenacity.wait_fixed(1)):
                    with attempt:
                        raw_response = await yad2_client.get('/', params=dict(topArea=region_code))
                        raw_response.raise_for_status()
                response = raw_response.json()
                amount_pages = response['data']['pagination']['last_page']
                for page in range(amount_pages + 1):
                    for attempt in tenacity.Retrying(stop=tenacity.stop_after_attempt(3),
                                                     wait=tenacity.wait_fixed(1)):
                        with attempt:
                            raw_response = await yad2_client.get('/',
                                                                 params=dict(topArea=region_code,
                                                                             page=page))
                            raw_response.raise_for_status()
                    response = raw_response.json()
                    for raw_listing in response['data']['feed']['feed_items']:
                        try:
                            listing = Listing(floor=get_floor(raw_listing),
                                              rooms=raw_listing['Rooms_text'],
                                              area=raw_listing['square_meters'],
                                              city=raw_listing['city'],
                                              street=raw_listing.get('street'),
                                              coordinates=raw_listing['coordinates'] or None,
                                              date_listed=datetime.datetime.fromisoformat(
                                                  raw_listing['date_added']),
                                              price=int(raw_listing['price'].split(' ')[0].replace(
                                                  ',', '')),
                                              neighborhood=raw_listing.get('neighborhood'),
                                              for_sale=for_sale)
                            listings.append(listing)
                        except (KeyError, pydantic.ValidationError) as _:
                            pass
                    await asyncio.sleep(0.1)
                    progress_bar.update()
    return listings


def _should_notify(quote: Listing, price_drop_percentage_threshold: float) -> bool:
    return quote.price <= (1 - price_drop_percentage_threshold) * quote.priceAvg200


def _notify(quote: Listing, contact_info: ContactInfo):
    html = _generate_html(contact_info.name, quote)
    _send_email(contact_info.email, html)


def _generate_html(name: str, quote: Listing) -> str:
    unformatted_html = HTML_PATH.read_text()
    html_data = dict(name=name,
                     symbol=quote.symbol,
                     stock_name=quote.name,
                     datetime=datetime.datetime.fromtimestamp(
                         quote.timestamp).strftime(READABLE_DATETIME_FORMAT),
                     price=round(quote.price, NUMBER_OF_DIGITS_TO_ROUND),
                     price_200_day_avg=round(quote.priceAvg200, NUMBER_OF_DIGITS_TO_ROUND),
                     percentage_price_is_lower_than_average=int(
                         (1 - quote.price / quote.priceAvg200) * 100))
    return jinja2.Template(unformatted_html).render(html_data)


def _send_email(email_address: str, html: str):
    message = MIMEMultipart()
    message['Subject'] = EMAIL_SUBJECT
    message['From'] = APP_EMAIL_ADDRESS
    message['To'] = email_address
    image_part = MIMEImage(LOGO_PATH.read_bytes())
    image_part.add_header('Content-ID', '<0>')
    message.attach(image_part)
    html_part = MIMEText(html, 'html')
    message.attach(html_part)
    context = ssl.create_default_context()
    with smtplib.SMTP_SSL(GMAIL_SMPT_SERVER_ADDRESS, SMTP_PORT, context=context) as smtp_connection:
        smtp_connection.login(APP_EMAIL_ADDRESS, GMAIL_PASSWORD)
        smtp_connection.sendmail(APP_EMAIL_ADDRESS, email_address, message.as_string())
