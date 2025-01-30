"""
------------------------------------------------------------------------------
Libraries
------------------------------------------------------------------------------
"""

import streamlit as st
import os
from datetime import datetime, timedelta
import requests
import pandas as pd
import numpy as np
import time

from pandas import json_normalize


"""
------------------------------------------------------------------------------
Functions
------------------------------------------------------------------------------
"""

# Fetch api data
@st.cache_data(show_spinner=True)
def fetch_data(url):
    """
    Fetches data from the base URL and returns it as JSON.
    If an error occurs, returns None.
    """
    try:
        response = requests.get(url)
        response.raise_for_status() 
        data = response.json() 
        return data
    except requests.exceptions.RequestException as e:
        print(f"An error occurred: {e}")
        return None


# Fetch paginated api data
@st.cache_data(show_spinner=True)
def fetch_pag_data(url, retries=3, delay=5):
    """
    Fetch paginated data from the base URL and returns
    a list containing all the data from the paginated responses.
    
    - url (str): The URL to fetch data from.
    - retries (int): The number of times to retry in case of an error.
    - delay (int): Delay (in seconds) between retries.
    """
    all_data = []

    while url:
        for attempt in range(retries):
            try:
                response = requests.get(url)
                response.raise_for_status()  
                data = response.json()  

                if "data" in data:
                    all_data.extend(data["data"])  # Add data of the current page
                    url = data.get("links", {}).get("next")  # Get the next page URL
                else:
                    url = None  # No more data
                break  

            except requests.HTTPError as e:
                print(f"Attempt {attempt + 1} failed for URL {url}: {e}")
                if attempt < retries - 1:
                    time.sleep(delay)
                else:
                    print(f"Failed after {retries} attempts. Skipping URL: {url}")
                    url = None  # No more data
                    break
            except Exception as e:
                print(f"Unexpected error: {e}")
                url = None
                break

    return all_data


# Fetch organization api data
@st.cache_data(show_spinner=True)
def fetch_orga_data(persons_with_membership: pd.DataFrame):
    """
    Fetches and processes organization data based on unique URLs in the organization column
    and returs a data frame with the orga data.

    Args: DataFrame with an organization column containing the URLs.
    """
    # Extract unique URLs
    unique_orga_urls = persons_with_membership["organization"].dropna().unique()
    
    data_list = []

    for orga_url in unique_orga_urls:
        try:
            orga_data = fetch_data(orga_url)

            if orga_data: 
                data = {
                    "organization": orga_data.get("id"),
                    "orgaName": orga_data.get("name"),
                    "shortName": orga_data.get("shortName"),
                    "orgaType": orga_data.get("organizationType"),
                    "classification": orga_data.get("classification"),
                    "orga_startDate": orga_data.get("startDate"),
                    "orga_endDate": orga_data.get("endDate"),
                }

                data_list.append(data)

        except Exception as e:
            print(f"Error fetching data from {orga_url}: {e}")

    orgaData = pd.DataFrame(data_list)
    return orgaData


# Fetch agenda api data
@st.cache_data(show_spinner=True)
def fetch_agenda_data(meeting_data):
    """
    Processes meeting data and extracts agenda items and returns
    a list of dictionaries with processed meeting details, including agenda items.

    Args: meeting_data (dict): Dictionary containing meeting data with a 'data' key holding a list of meetings.
    """
    try:
        # Validate the input data
        if not isinstance(meeting_data, dict) or "data" not in meeting_data:
            raise ValueError("Invalid meeting data format. Expected a dictionary with a 'data' key.")

        meetings_with_agenda = []

        for meeting in meeting_data.get("data", []):
            meeting_info = {
                "id": meeting.get("id"),
                "name": meeting.get("name"),
                "start": meeting.get("start"),
                "end": meeting.get("end"),
                "agendaItems": []
            }

            for agenda_item in meeting.get("agendaItem", []):
                agenda = {
                    "number": agenda_item.get("number"),
                    "name": agenda_item.get("name"),
                    "public": agenda_item.get("public", False)
                }
                meeting_info["agendaItems"].append(agenda) 

            meetings_with_agenda.append(meeting_info) 

        return meetings_with_agenda

    except Exception as e:
        st.error(f"An error occurred while processing the agenda data: {e}")
        return [] # Return empty list in case of error
