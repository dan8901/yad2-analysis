import json
import pathlib

import pandas as pd
import streamlit as st

CENTRAL_BUREAU_OF_STATISTICS_EXCEL_URL = 'https://www.cbs.gov.il/he/publications/LochutTlushim/2020/%D7%90%D7%95%D7%9B%D7%9C%D7%95%D7%A1%D7%99%D7%99%D7%942020.xlsx'
MIN_AMOUNT_OF_LISTINGS_IN_CITY = 9
DATA_FILE_PATH = pathlib.Path(__file__).parents[1].resolve().joinpath('all_listings.json')
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


@st.experimental_memo
def get_initial_df():
    all_listings = json.loads(DATA_FILE_PATH.read_text())
    df = pd.DataFrame(all_listings)
    df.date_listed = pd.to_datetime(df.date_listed)

    city_names_and_populations = pd.read_excel(CENTRAL_BUREAU_OF_STATISTICS_EXCEL_URL,
                                               usecols='B,G,H',
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
    return df, city_names_and_populations
