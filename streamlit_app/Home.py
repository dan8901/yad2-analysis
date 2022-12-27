import pathlib
import sys

import matplotlib
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np

import streamlit as st

from streamlit_app.get_initial_df import get_initial_df
from streamlit_app.other_graphs import other_graphs

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from streamlit_app.cities import CITIES

MILLION = 1000000
MIN_IN_EACH_BIN = 3
MAX_AMOUNT_OF_BINS = 10


def on_region_checkbox_change(region_key, relevant_cities):
    all_other_selected_cities = set(st.session_state.city_multiselect) - CITIES[region_key]
    if not getattr(st.session_state, region_key):
        st.session_state.city_multiselect = list(all_other_selected_cities) or []
    else:
        st.session_state.city_multiselect = list(all_other_selected_cities
                                                 | (CITIES[region_key]
                                                    & relevant_cities)) or []


def on_city_multiselect_change():
    for region in CITIES:
        setattr(st.session_state, region,
                bool(set(st.session_state.city_multiselect) & CITIES[region]))


def select_cities(relevant_cities):
    st.write('Select regions you would like to analyze.')
    for region in CITIES:
        st.checkbox(region,
                    key=region,
                    on_change=on_region_checkbox_change,
                    args=(region, relevant_cities))
    return st.multiselect(
        'Or, select the cities you would like to analyze.',
        list(relevant_cities),
        default=list(set(st.session_state.get('city_multiselect', {})) & relevant_cities),
        key='city_multiselect',
        on_change=on_city_multiselect_change)


def main():
    # TODO:

    st.title('Real Estate Analysis Tool')
    st.markdown(
        'Share [yad2analysis.com](http://yad2analysis.com) with your friends!<br/>'
        'This app was made by [Dan Nissim](https://www.linkedin.com/in/dan-nissim) with data'
        ' from [yad2.co.il](https://yad2.co.il). Feel free to <a href="mailto:nissim.dan@gmail.com">contact me</a>.',
        unsafe_allow_html=True)

    initial_df, city_names_and_populations = get_initial_df()

    unformatted_price_range = st.slider('Select the range of prices to analyze  (in million ₪).',
                                        0.3,
                                        12.0, (1.0, 3.0),
                                        step=0.1,
                                        key='price_range',
                                        format='%f')
    price_range = unformatted_price_range[0] * MILLION, unformatted_price_range[1] * MILLION
    start_time = st.slider(
        "Select the earliest listing date to analyze.",
        min_value=(pd.Timestamp.today() - pd.Timedelta(16, unit='W')).to_pydatetime(),
        max_value=(pd.Timestamp.today() - pd.Timedelta(2, unit='W')).to_pydatetime(),
        step=pd.Timedelta(1, unit='W').to_pytimedelta(),
        format="DD/MM/YY",
        key='start_time_select')

    df = initial_df[initial_df.date_listed > start_time]
    df = df[(df.price > price_range[0]) & (df.price < price_range[1]) | ~df.for_sale]

    selected_cities = select_cities(set(df.english_city.unique()))
    if selected_cities:
        df = df[df.english_city.isin(selected_cities)]
        st.subheader('Results')
        tabs = st.tabs(['Rent Yield', 'Amount of Listings', 'Price per m²'])
        graphs = [graph8, graph9, graph10]
        for i, tab in enumerate(tabs):
            with tab:
                st.pyplot(graphs[i](df, city_names_and_populations), True)

    st.subheader('Other Graphs')
    other_graphs(initial_df)


def graph8(df, *args):
    dfs = list()
    for city in df.english_city.unique():
        x = df[df.english_city == city]
        number_of_bins = min(MAX_AMOUNT_OF_BINS, int(x.shape[0] / MIN_IN_EACH_BIN))
        dfs.append(x.assign(area_bin=pd.qcut(x.area, number_of_bins, duplicates='drop')))

    y = pd.concat(dfs).groupby(['english_city', 'area_bin', 'for_sale']) \
        .agg({'price': ['mean', 'count']}).unstack().dropna().reset_index()
    res = y.groupby('english_city').apply(
        lambda z: np.average(z['price']['mean'][False] * 12 / z['price']['mean'][True],
                             weights=z['price']['count'][False] + z['price']['count'][True]))
    plot = res.plot.bar()
    plot.axhline(y=res.median(), linestyle='--')
    plot.yaxis.set_major_formatter(matplotlib.ticker.PercentFormatter(1))
    plot.set_xlabel(None)
    plot.set_title('Annual Yield From Rent')
    plot.get_figure().set_size_inches(max(8, int(res.shape[0] / 2)), 5)
    return plot.get_figure()


def graph9(df, city_names_and_populations, *args):
    # create df
    df = df[df.for_sale]
    cities_df = df.english_city.value_counts()
    cities_df.name = 'amount_of_listings'
    cities_df = cities_df.to_frame().merge(city_names_and_populations,
                                           left_index=True,
                                           right_on='english_city')
    cities_df = cities_df.set_index('english_city')
    cities_df['amount_of_listings_per_100k_residents'] = (
        (cities_df.amount_of_listings / cities_df.city_population) * 100000).astype(int)
    median_amount_of_listings_per_100k_residents = \
        cities_df.amount_of_listings_per_100k_residents.median()

    cities_df = cities_df.sort_index()
    plot = cities_df.amount_of_listings.plot.bar(width=0.3, position=0)
    cities_df.amount_of_listings_per_100k_residents.plot.bar(width=0.3, color='orange', position=1)
    plot.legend(loc='upper right')
    plot.set_xlabel(None)
    plot.axhline(y=median_amount_of_listings_per_100k_residents, color='orange', linestyle='--')
    plot.get_figure().set_size_inches(max(8, int(cities_df.shape[0] / 2)), 5)
    plot.set_title('Amount of Listings')
    return plot.get_figure()


def graph10(df, *args):
    df = df[df.for_sale]
    amount_of_listings = df.english_city.value_counts()
    amount_of_listings.name = 'amount_of_listings'
    df['price_per_sqm'] = df.price / df.area
    prices_per_sqm = df.groupby('english_city').mean(numeric_only=True)['price_per_sqm'].astype(int)
    plot = prices_per_sqm.plot.bar()
    plot.axhline(y=prices_per_sqm.median(), linestyle='--')
    plot.set_xlabel(None)
    plot.set_title('Price per Square Meter')
    plot.get_figure().set_size_inches(max(8, int(prices_per_sqm.shape[0] / 2)), 5)
    return plot.get_figure()


if __name__ == '__main__':
    main()
