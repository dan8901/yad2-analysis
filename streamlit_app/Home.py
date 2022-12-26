import pathlib
import sys

import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

from streamlit_app.get_initial_df import get_initial_df

sys.path.append(str(pathlib.Path(__file__).resolve().parents[1]))

from streamlit_app.cities import CITIES

MILLION = 1000000


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
    # create purchase_price/rent per city graph

    st.title('Real Estate Analysis Tool')
    st.markdown(
        'Share [yad2analysis.com](http://yad2analysis.com) with your friends!<br/>'
        'This app was made by [Dan Nissim](https://www.linkedin.com/in/dan-nissim) with data'
        ' from [yad2.co.il](https://yad2.co.il). Feel free to <a href="mailto:nissim.dan@gmail.com">contact me</a>.',
        unsafe_allow_html=True)

    df, city_names_and_populations = get_initial_df()

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

    df = df[df.date_listed > start_time]
    df = df[(df.price > price_range[0]) & (df.price < price_range[1])]

    selected_cities = select_cities(set(df.english_city.unique()))
    if not selected_cities:
        return

    df = df[df.english_city.isin(selected_cities)]
    st.header('Results')
    graph8(df, city_names_and_populations)


def graph8(df, city_names_and_populations):
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
