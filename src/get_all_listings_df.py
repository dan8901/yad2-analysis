import asyncio
import datetime
import enum
import itertools
import typing

import httpx
import pandas as pd
import pydantic
import tenacity
from tqdm import tqdm

from src.distance_from_beach import DistanceFromBeach

YAD2_FOR_SALE_API_URL = 'https://gw.yad2.co.il/feed-search-legacy/realestate/forsale'
YAD2_RENT_API_URL = 'https://gw.yad2.co.il/feed-search-legacy/realestate/rent'
DEFAULT_PARAMS = dict(propertyGroup='apartments,houses',
                      property='1,25,3,39,4,5,51,6,7',
                      forceLdLoad='true')
CENTRAL_BUREAU_OF_STATISTICS_EXCEL_URL = 'https://www.cbs.gov.il/he/publications/LochutTlushim/2020/%D7%90%D7%95%D7%9B%D7%9C%D7%95%D7%A1%D7%99%D7%99%D7%942020.xlsx'
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


class Listing(pydantic.BaseModel):
    date_listed: datetime.datetime
    city: str
    neighborhood: typing.Optional[str]
    street: typing.Optional[str]
    coordinates: typing.Optional[typing.Tuple[float, float]]
    floor: int
    rooms: int
    area: int
    price: int
    for_sale: bool
    distance_from_beach: int
    property_type: str
    link: str


async def get_all_listings_df():
    await save_preprocessed_listings()
    get_initial_df().to_csv('../all_listings.csv', index=False)


async def save_preprocessed_listings():
    for_sale_params = DEFAULT_PARAMS | dict(price='600000-20000000')
    rent_params = DEFAULT_PARAMS | dict(price='1500-30000')
    rent_listings = await _get_all_listings(YAD2_RENT_API_URL, rent_params, False)
    for_sale_listings = await _get_all_listings(YAD2_FOR_SALE_API_URL, for_sale_params, True)
    all_listings = (listing.model_dump()
                    for listing in itertools.chain(for_sale_listings, rent_listings))
    pd.DataFrame(all_listings).to_csv('../preprocessed_listings.csv', index=False)


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
    distance_calculator = DistanceFromBeach()
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
                            coordinates = (raw_listing['coordinates']['latitude'],
                                           raw_listing['coordinates']['longitude'])\
                                if raw_listing['coordinates'] else None
                            listing = Listing(
                                floor=get_floor(raw_listing),
                                rooms=raw_listing['Rooms_text'],
                                area=raw_listing['square_meters'],
                                city=raw_listing['city'],
                                street=raw_listing.get('street'),
                                coordinates=coordinates,
                                date_listed=datetime.datetime.fromisoformat(
                                    raw_listing['date_added']),
                                price=int(raw_listing['price'].split(' ')[0].replace(',', '')),
                                neighborhood=raw_listing.get('neighborhood'),
                                for_sale=for_sale,
                                distance_from_beach=distance_calculator.calculate(coordinates)
                                if coordinates else None,
                                property_type=raw_listing['HomeTypeID_text'],
                                link=f'https://www.yad2.co.il/item/{raw_listing["link_token"]}')
                            listings.append(listing)
                        except (KeyError, pydantic.ValidationError) as _:
                            pass
                    await asyncio.sleep(0.1)
                    progress_bar.update()
    return listings


def get_initial_df():
    df = pd.read_csv('../preprocessed_listings.csv')
    df.date_listed = pd.to_datetime(df['date_listed'])

    city_names_and_populations = pd.read_excel(CENTRAL_BUREAU_OF_STATISTICS_EXCEL_URL,
                                               usecols='C,H,M',
                                               keep_default_na=False,
                                               skipfooter=7,
                                               header=7)
    city_names_and_populations = city_names_and_populations.set_axis(
        ['hebrew_city', 'city_population', 'english_city'], axis=1)

    # fix specific cities to match
    city_names_and_populations = city_names_and_populations.replace(TYPOS)

    df = df.merge(city_names_and_populations, left_on='city', right_on='hebrew_city', how='left')
    df = df.drop('hebrew_city', axis=1)
    # drop erroneous extreme rows to clean data set
    df = df[df.date_listed > (pd.Timestamp.today() - pd.Timedelta(16, unit='W')).to_pydatetime()]
    df = df[(df.area < df.area.mean() * 5) & (df.area > df.area.mean() / 10)]
    df.city_population = df.city_population.astype(float).round().astype('Int64')
    df.drop_duplicates(subset='link', keep='first', inplace=True)
    df = df.reset_index(drop=True)
    # TODO: instead of ignoring them here, ignore them only in the graphs that assume this.
    # TODO: add information about title 2 : property type - cottage, apartment, etc...
    return df


if __name__ == '__main__':
    asyncio.run(get_all_listings_df())
    # get_initial_df(pd.read_csv('../preprocessed_listings.csv',
    #                            parse_dates=['date_listed'])).to_csv('../all_listings.csv',
    #                                                                 index=False)
