import asyncio
import datetime
import enum
import itertools
import json
import pathlib
import typing

import httpx
import pydantic
import tenacity
from tqdm import tqdm
import pandas as pd

YAD2_FOR_SALE_API_URL = 'https://gw.yad2.co.il/feed-search-legacy/realestate/forsale'
YAD2_RENT_API_URL = 'https://gw.yad2.co.il/feed-search-legacy/realestate/rent'
DEFAULT_PARAMS = dict(propertyGroup='apartments,houses',
                      property='1,25,3,32,39,4,5,51,55,6,7',
                      forceLdLoad='true')
CENTRAL_BUREAU_OF_STATISTICS_EXCEL_URL = 'https://www.cbs.gov.il/he/publications/LochutTlushim/2020/%D7%90%D7%95%D7%9B%D7%9C%D7%95%D7%A1%D7%99%D7%99%D7%942020.xlsx'
MIN_AMOUNT_OF_LISTINGS_IN_CITY = 9
TYPOS = {
    'תל אביב -יפו': 'תל אביב יפו',
    'הרצלייה': 'הרצליה',
    'קדימה-צורן': 'קדימה צורן',
    'מודיעין-מכבים-רעות*': 'מודיעין מכבים רעות',
    'קריית אונו': 'קרית אונו',
    'יהוד-מונוסון': 'יהוד מונוסון',
    'קריית גת': 'קרית גת',
    'קריית מלאכי': 'קרית מלאכי',
    'קריית עקרון': 'קרית עקרון',
    'גבע בנימין': 'אדם - גבע בנימין',
    'בית אריה-עופרים': 'בית אריה / עופרים',
    'נהרייה': 'נהריה',
    'קריית מוצקין': 'קרית מוצקין',
    'קריית אתא': 'קרית אתא',
    'קריית ביאליק': 'קרית ביאליק',
    'קריית ים': 'קרית ים',
    'פרדס חנה-כרכור': 'פרדס חנה כרכור',
    'נוף הגליל': 'נצרת עילית / נוף הגליל',
    'קריית שמונה': 'קרית שמונה',
    'מעלות-תרשיחא': 'מעלות תרשיחא',
    'קריית טבעון': 'קרית טבעון',
    'בנימינה-גבעת עדה*': 'בנימינה גבעת עדה',
    'מיתר': 'מיתר / כרמית',
    'כוכב יאיר': 'כוכב יאיר / צור יגאל',
    'סביון*': 'סביון',
    'פרדסייה': 'פרדסיה',
    'שער שומרון': 'שערי תקווה',
    'קריית ארבע': 'קרית ארבע',
    'בית יצחק-שער חפר': 'בית יצחק שער חפר',
}


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


async def get_all_listings_df():
    for_sale_params = DEFAULT_PARAMS | dict(price='600000-20000000')
    rent_params = DEFAULT_PARAMS | dict(price='1500-30000')
    rent_listings = await _get_all_listings(YAD2_RENT_API_URL, rent_params, False)
    for_sale_listings = await _get_all_listings(YAD2_FOR_SALE_API_URL, for_sale_params, True)
    all_listings = (listing.dict() for listing in itertools.chain(for_sale_listings, rent_listings))
    get_initial_df(all_listings).to_csv('./all_listings.csv', index=False)


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


def get_initial_df(all_listings):
    df = pd.DataFrame(all_listings)
    df.date_listed = pd.to_datetime(df.date_listed)

    city_names_and_populations = pd.read_excel(CENTRAL_BUREAU_OF_STATISTICS_EXCEL_URL,
                                               usecols='C,L,M',
                                               keep_default_na=False,
                                               skipfooter=7,
                                               header=7)
    city_names_and_populations = city_names_and_populations.set_axis(
        ['hebrew_city', 'city_population', 'english_city'], axis=1)

    # fix specific cities to match
    city_names_and_populations = city_names_and_populations.replace(TYPOS)

    df = df.merge(city_names_and_populations, left_on='city', right_on='hebrew_city', how='left')
    df = df.drop('city', axis=1)
    # About 1% of listings are in cities with a population of less than 2000,
    # for simplicity we'll ignore them
    df = df.dropna()
    df.city_population = df.city_population.astype(int)

    # drop erroneous extreme rows to clean data set
    df = df[df.date_listed > (pd.Timestamp.today() - pd.Timedelta(16, unit='W')).to_pydatetime()]
    df = df[(df.area < df.area.mean() * 5) & (df.area > df.area.mean() / 10)]
    listing_count_by_city = df.hebrew_city.value_counts()
    cities_to_ignore = set(
        listing_count_by_city.
        loc[lambda listing_count: listing_count < MIN_AMOUNT_OF_LISTINGS_IN_CITY].index)
    df = df[~df.hebrew_city.isin(cities_to_ignore)]
    df = df.reset_index(drop=True)
    return df


if __name__ == '__main__':
    asyncio.run(get_all_listings_df())
