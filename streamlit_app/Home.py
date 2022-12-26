import json
import pathlib
import sys

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

sys.path.append(str(pathlib.Path(__file__).resolve().parent))

from streamlit_app.cities import CITIES

CENTRAL_BUREAU_OF_STATISTICS_EXCEL_URL = 'https://www.cbs.gov.il/he/publications/LochutTlushim/2020/%D7%90%D7%95%D7%9B%D7%9C%D7%95%D7%A1%D7%99%D7%99%D7%942020.xlsx'
MIN_AMOUNT_OF_LISTINGS_IN_CITY = 9
DEFAULT_CITIES_SELECTION = [
    'Tel Aviv - Yafo',
    'Petah Tiqwa',
    'Qiryat Ono',
    'Ramat Gan',
    'Modi\'in-Makkabbim-Re\'ut',
    'Rishon LeZiyyon',
    'Holon',
]
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
    'מיתר': 'מיתר / כרמית'
}
DATA_FILE_PATH = pathlib.Path(__file__).parents[1].resolve().joinpath('all_listings.json')


def setup(start_time, price_range):
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
    df = df[(df.price > price_range[0]) & (df.price < price_range[1])]
    df = df[(df.area < df.area.mean() * 5) & (df.area > df.area.mean() / 10)]
    df = df[df.date_listed > start_time]
    listing_count_by_city = df.hebrew_city.value_counts()
    cities_to_ignore = set(
        listing_count_by_city.
        loc[lambda listing_count: listing_count < MIN_AMOUNT_OF_LISTINGS_IN_CITY].index)
    df = df[~df.hebrew_city.isin(cities_to_ignore)]
    df = df.reset_index(drop=True)
    return df, city_names_and_populations


def on_region_checkbox_change(region_key, relevant_cities):
    all_other_selected_cities = set(st.session_state.city_multiselect) - CITIES[region_key]
    if not getattr(st.session_state, region_key):
        st.session_state.city_multiselect = all_other_selected_cities or []
    else:
        st.session_state.city_multiselect = all_other_selected_cities | (CITIES[region_key]
                                                                         & relevant_cities)


def on_city_multiselect_change():
    for region in CITIES:
        setattr(st.session_state, region,
                bool(set(st.session_state.city_multiselect) & CITIES[region]))


def select_cities(relevant_cities):
    st.write('Select regions you would like to analyze.')
    for region in CITIES:
        should_be_selected_by_default = bool(set(DEFAULT_CITIES_SELECTION) & CITIES[region])
        st.checkbox(region,
                    key=region,
                    on_change=on_region_checkbox_change,
                    args=(region, relevant_cities),
                    value=should_be_selected_by_default)
    return st.multiselect('Or, select the cities you would like to analyze.',
                          relevant_cities,
                          default=(set(DEFAULT_CITIES_SELECTION) & relevant_cities),
                          key='city_multiselect',
                          on_change=on_city_multiselect_change)


def main():
    # TODO:
    # add price range slider, and download all data for all apartment prices
    # add general graphs (day of week, time of day, etc.)
    # download rent data and create purchase_price/rent per city graph

    st.title('Real Estate Analysis Tool')
    st.markdown(
        'This app was made by [Dan Nissim](https://www.linkedin.com/in/dan-nissim) with data'
        ' from [yad2.co.il](https://yad2.co.il). Feel free to <a href="mailto:nissim.dan@gmail.com">contact me</a>.',
        unsafe_allow_html=True)
    price_range = st.slider('Select the range of prices to analyze.',
                            1000000,
                            12000000, (1000000, 3000000),
                            step=100000,
                            key='price_range')
    start_time = st.slider(
        "Select the earliest listing date to analyze.",
        min_value=(pd.Timestamp.today() - pd.Timedelta(16, unit='W')).to_pydatetime(),
        max_value=(pd.Timestamp.today() - pd.Timedelta(2, unit='W')).to_pydatetime(),
        step=pd.Timedelta(1, unit='W').to_pytimedelta(),
        format="DD/MM/YY",
        key='start_time_select')

    df, city_names_and_populations = setup(start_time, price_range)

    selected_cities = select_cities(set(df.english_city.unique()))
    if not selected_cities:
        return

    df = df[df.english_city.isin(selected_cities)]
    # st.write(df.describe())
    # st.write(df.english_city.unique())
    st.header('Results')
    # all_graphs = [graph1, graph2, graph3, graph4, graph5, graph6, graph7, graph8]
    # for graph in all_graphs:
    #     graph(df, city_names_and_populations)
    graph8(df, city_names_and_populations)


def graph8(df, city_names_and_populations, *args):
    # create df
    amount_of_listings = df.english_city.value_counts()
    amount_of_listings.name = 'amount_of_listings'
    df['price_per_sqm'] = df.price / df.area
    prices_per_sqm = df.groupby('english_city').mean(
        numeric_only=True)['price_per_sqm'].sort_values(ascending=False).astype(int)
    cities_df = pd.merge(prices_per_sqm, amount_of_listings, left_index=True, right_index=True)
    cities_df = cities_df.merge(city_names_and_populations,
                                left_index=True,
                                right_on='english_city')
    cities_df = cities_df.set_index('english_city')
    cities_df['amount_of_listings_per_100k_residents'] = (
        (cities_df.amount_of_listings / cities_df.city_population) * 100000).astype(int)
    median_amount_of_listings_per_100k_residents = \
        cities_df.amount_of_listings_per_100k_residents.median()
    median_price_per_sqm = cities_df.price_per_sqm.median()

    # plotting
    fig, ax = plt.subplots()
    ax2 = ax.twinx()
    cities_df.price_per_sqm.plot.bar(ax=ax, width=0.2, position=0)
    cities_df.amount_of_listings.plot.bar(ax=ax2, width=0.2, color='orange', position=1)
    cities_df.amount_of_listings_per_100k_residents.plot.bar(ax=ax2,
                                                             width=0.2,
                                                             color='purple',
                                                             position=2)
    ax.set_ylabel('Price per Square Meter')
    ax2.set_ylabel('Amount of Listings')
    ax.set_xlim(right=(ax.get_xlim()[1] + 0.25))
    ax2.set_xlim(right=(ax2.get_xlim()[1] + 0.25))
    ax.set_xlabel(None)
    lines, labels = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax.axhline(y=median_price_per_sqm, linestyle='--')
    ax2.axhline(y=median_amount_of_listings_per_100k_residents, color='purple', linestyle='--')
    ax.legend(lines + lines2, labels + labels2, loc='upper right')
    fig.set_size_inches(max(8, int(cities_df.shape[0] / 2)), 5)
    ax.set_title('Amount of Listings, and the Price per Square Meter, for each City')
    st.pyplot(ax.get_figure())


if __name__ == '__main__':
    main()
