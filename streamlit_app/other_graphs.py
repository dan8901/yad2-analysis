import calendar
import pathlib
import sys

import matplotlib
import matplotlib.pyplot as plt
import pandas as pd
import streamlit as st

sys.path.append(str(pathlib.Path(__file__).resolve().parents[2]))

WEEKDAYS = ['Sunday', 'Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']


def other_graphs(df):
    tabs = st.tabs(['Area', 'Price', 'Date', 'Day of Week', 'Rooms', 'Time of Day', 'Floor'])
    graphs = [graph1, graph2, graph3, graph4, graph5, graph6, graph7]
    for i, tab in enumerate(tabs):
        with tab:
            st.pyplot(graphs[i](df), True)


@st.experimental_memo
def graph1(df):
    plt.clf()
    plot = df[df.area < 200].area.hist(bins=30, figsize=(5, 3), grid=False)
    plot.get_yaxis().set_visible(False)
    plot.set_xlabel('Area $m^2$')
    plot.set_title('Distribution of the Area of Listings')
    return plot.get_figure()


@st.experimental_memo
def graph2(df):
    plot = df[(300000 < df.price) & (df.price < 10000000)].price.hist(bins=30,
                                                                      figsize=(8, 5),
                                                                      grid=False)
    plot.get_yaxis().set_visible(False)
    plot.get_xaxis().set_ticks([i for i in range(0, 10000000, 1000000)])
    plot.set_xlabel('Price')
    plot.set_title('Distribution of Prices')
    return plot.get_figure()


@st.experimental_memo
def graph3(df):
    plot = df.date_listed.hist(bins=16, figsize=(8, 5), grid=False)
    plot.get_yaxis().set_visible(False)
    plot.set_xlabel('Date')
    plot.get_xaxis().set_major_formatter(matplotlib.dates.DateFormatter('%d-%m'))
    plot.set_title('Distribution of Dates Listed')
    return plot.get_figure()


@st.experimental_memo
def graph4(df):
    plot = pd.Series([calendar.day_name[date.weekday()] for date in df.date_listed]).value_counts(). \
        sort_index(
        key=lambda day_names: [WEEKDAYS.index(day_name) for day_name in day_names]).plot.bar(
        figsize=(5, 3))
    plot.set_ylabel('Amount of Listings')
    plot.set_title('Day of the Week Listed')
    return plot.get_figure()


@st.experimental_memo
def graph5(df):
    plot = df.rooms.value_counts().sort_index().plot.bar(figsize=(5, 3))
    plot.set_xlabel('Number of Rooms')
    plot.set_ylabel('Amount of Listings')
    plot.set_title('Distribution of Number of Rooms')
    return plot.get_figure()


@st.experimental_memo
def graph6(df):
    plot = pd.Series([date_listed.time().hour + date_listed.time().minute / 60 for date_listed in
                      df.date_listed]) \
        .hist(bins=48, figsize=(8, 3), grid=False)
    plot.get_yaxis().set_visible(False)
    plot.get_xaxis().set_ticks([i for i in range(0, 24)])
    plot.set_xlabel('Hour')
    plot.set_title('Time of Day Listings Were Posted')
    return plot.get_figure()


@st.experimental_memo
def graph7(df):
    plot = df.floor.value_counts().sort_index().plot.bar()
    plot.set_xlabel('Floor number')
    plot.set_ylabel('Amount of Listings')
    plot.set_title('Distribution of Floor Number')
    return plot.get_figure()
