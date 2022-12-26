import calendar

import matplotlib
import pandas as pd
import streamlit as st
from streamlit_app.Home import setup

WEEKDAYS = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']


def main():
    four_months_ago = (pd.Timestamp.today() - pd.Timedelta(16, unit='W')).to_pydatetime()
    whole_price_range = (1000000, 9000000)
    df, _ = setup(four_months_ago, whole_price_range)
    graphs = [graph1, graph2, graph3, graph4, graph5, graph6, graph7]
    for graph in graphs:
        graph(df)


def graph1(df):
    plot = df[df.area < 200].area.hist(bins=30, figsize=(5, 3), grid=False)
    plot.get_yaxis().set_visible(False)
    plot.set_xlabel('Area $m^2$')
    plot.set_title('Distribution of the Area of Listings')
    st.pyplot(plot.get_figure(), True)


def graph2(df):
    plot = df.price.hist(bins=30, figsize=(8, 5), grid=False)
    plot.get_yaxis().set_visible(False)
    plot.set_xlabel('Price')
    plot.set_title('Distribution of Prices')
    st.pyplot(plot.get_figure(), True)


def graph3(df):
    plot = df.date_listed.hist(bins=16, figsize=(8, 5), grid=False)
    plot.get_yaxis().set_visible(False)
    plot.set_xlabel('Date')
    plot.get_xaxis().set_major_formatter(matplotlib.dates.DateFormatter('%d-%m'))
    plot.set_title('Distribution of Dates Listed')
    st.pyplot(plot.get_figure(), True)


def graph4(df):
    plot = pd.Series([calendar.day_name[date.weekday()] for date in df.date_listed]).value_counts(). \
        sort_index(
        key=lambda day_names: [WEEKDAYS.index(day_name) for day_name in day_names]).plot.bar(
        figsize=(5, 3))
    plot.set_ylabel('Amount of Listings')
    plot.set_title('Day of the Week Listed')
    st.pyplot(plot.get_figure(), True)


def graph5(df):
    plot = df.rooms.value_counts().sort_index().plot.bar(figsize=(5, 3))
    plot.set_xlabel('Number of Rooms')
    plot.set_ylabel('Amount of Listings')
    plot.set_title('Distribution of Number of Rooms')
    st.pyplot(plot.get_figure(), True)


def graph6(df):
    plot = pd.Series([date_listed.time().hour + date_listed.time().minute / 60 for date_listed in
                      df.date_listed]) \
        .hist(bins=48, figsize=(8, 3), grid=False)
    plot.get_yaxis().set_visible(False)
    plot.get_xaxis().set_ticks([i for i in range(0, 24, 1)])
    plot.set_xlabel('Hour')
    plot.set_title('Time of Day Listings Were Posted')
    st.pyplot(plot.get_figure(), True)


def graph7(df):
    plot = df.floor.value_counts().sort_index().plot.bar()
    plot.set_xlabel('Floor number')
    plot.set_ylabel('Amount of Listings')
    plot.set_title('Distribution of Floor Number')
    st.pyplot(plot.get_figure(), True)


if __name__ == '__main__':
    main()