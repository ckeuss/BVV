###--------------------------------------------------------------------------###
### Libraries / Functions                                                    ###
###--------------------------------------------------------------------------###

from src.functions import fetch_data
from src.functions import fetch_pag_data
from src.functions import fetch_orga_data
from src.functions import fetch_agenda_data

import streamlit as st
from pandas import json_normalize
import pandas as pd
import geopandas as gpd
import numpy as np
import plotly.express as px
import matplotlib.pyplot as plt
from wordcloud import WordCloud
from PIL import Image
import requests
import pydeck as pdk
from shapely.geometry import mapping


###--------------------------------------------------------------------------###
### Intro and page set up                                                    ###
###--------------------------------------------------------------------------###

st.set_page_config(layout= "wide")


col1, col2 = st.columns(2)

# Text
col1.markdown("# BVV Berlin")
col1.markdown("Die ALLRIS-Schnittstelle (Allgemeines Ratsinformationssystem) wird von vielen Kommunen in Deutschland für das Rats- und Sitzungsmanagement genutzt, um Informationen zu politischen Gremien, Ausschüssen, Sitzungen und Beschlüssen zu verwalten und öffentlich zugänglich zu machen. Die offenen Daten können über die API im [OPARL-Standard](https://oparl.org/spezifikation/online-ansicht/) abgerufen und weiterverarbeitet werden. Diese BVV-App nutzt die Daten der 12 Berliner Bezirke zu den Bezirksverordnetenversammlungen (BVV) und ermöglicht einen Überblick über die Ausschüsse und Fraktionen sowie die aktuellen Bezirksverordneten und deren Rollen. Zudem visualisiert sie die Entwicklung der Geschlechterverteilung innerhalb der BVV im Laufe der Zeit. Eine integrierte Stichwortsuche erleichtert das Auffinden von Sitzungen mit bestimmten Tagesordnungspunkten – vorausgesetzt, die Bezirke stellen diese Informationen zur Verfügung. Weitere Informationen zu den API-Schnittstellen der Bezirke finden sich im Berlin Open Data Portal, beispielsweise [hier](https://daten.berlin.de/datensaetze/schnittstelle-zum-informationssystem-der-bvv-berlin-mitte) für den Bezirk Mitte.")

# Image
col2.image("https://upload.wikimedia.org/wikipedia/commons/b/b1/Berlin_Bezirk_Mitte_949-831-%28118%29.jpg", caption = "Skyline von Berlin-Mitte, Lotse, CC BY-SA 3.0, via Wikimedia Commons")

# Filter data based on selected district
district = ["Mitte", "Charlottenburg-Wilmersdorf", "Friedrichshain-Kreuzberg","Lichtenberg", "Marzahn-Hellersdorf", "Neukoelln", "Pankow", "Reinickendorf", "Steglitz-Zehlendorf", "Tempelhof-Schoeneberg", "Treptow-Koepenick"]

selected_district = col1.selectbox(
    "Wähle ein Bezirk:", district                 
)

###--------------------------------------------------------------------------###
### Map based on selection                                                   ###
###--------------------------------------------------------------------------###

# Load district geometry dataset
# pre-processed geojson-file based on open data from geoportal Berlin (https://gdi.berlin.de/viewer/main/) 
# 'ALKIS Berlin Bezirke', data accessible via WFS-Service
bezirke = pd.read_csv("./csv/berlin_bezirke.csv")

# Geometry format gpd.GeoSeries
# print(bezirke["geometry"].dtype) -> geometry
bezirke["geometry"] = gpd.GeoSeries.from_wkt(bezirke["geometry"])

# Convert to GeoDataFrame
bezirke = gpd.GeoDataFrame(bezirke, geometry="geometry")

# Filter the data based on the selected district
district_geom = bezirke[bezirke["namgem"] == selected_district]

# Pydeck requires a GeoJSON dictionary, not a Shapely Polygon
# Convert geometry
district_geojson = mapping(district_geom["geometry"].values[0])

# Set map view state ->Berlin
view_state = pdk.ViewState(latitude=52.52, longitude=13.4050, zoom=10)

# Pydeck map
deck = pdk.Deck(
    initial_view_state=view_state,
    layers=[
        pdk.Layer(
            "GeoJsonLayer",
            data=district_geojson,
            get_fill_color="[78, 141, 111, 255]", # RGBA
            get_line_color="[0, 0, 0]",  # Black 
            line_width=2,
            pickable=True,
            opacity=0.5
            ),
    ],
    map_style="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json" # carto positron
)

st.pydeck_chart(deck)

###--------------------------------------------------------------------------###
### Load distric data via API                                                ###
###--------------------------------------------------------------------------###


# System data
selected_district = selected_district.lower()

if selected_district:
    systemUrl = f"https://www.sitzungsdienst-{selected_district}.de/oi/oparl/1.0/system.asp"

    # Fetch data
    systemData = fetch_data(systemUrl)

    
# Bodies data
bodyUrl = systemData["body"]
bodiesData = fetch_data(bodyUrl)

# Person data
personUrl = bodiesData["data"][0]["person"]
personData = fetch_pag_data(personUrl)

# Filter persons with membership data
persons_with_membership = [person for person in personData if "membership" in person]

# normalize the data
persons_with_membership = json_normalize(
    persons_with_membership,
    "membership",  
    ["name", "familyName", "givenName", "formOfAddress"],  # Keys to extract
    errors="ignore",  # Ignore missing meta keys
)


###--------------------------------------------------------------------------###
### Orga data                                                                ###
###--------------------------------------------------------------------------###

orgaData = fetch_orga_data(persons_with_membership)

st.subheader("Ausschüsse und Fraktionen")

# Distribute organizations on three columns and add caption
cols = st.columns(3)
for idx, row in orgaData.iterrows():
    with cols[idx % 3]:
        st.markdown(f"**{row['orgaName']}**")
        st.caption(f"{row['shortName']} | {row['orgaType']} | {row['classification']}")


###--------------------------------------------------------------------------###
### Current number of persons by Orga                                        ###
###--------------------------------------------------------------------------###

st.subheader("Aktuelle Mitgliederanzahl je Ausschuss bzw. Fraktion")

members = pd.merge(persons_with_membership, orgaData, on= "organization", how="left")

currentMembers = members[members["endDate"].isna()]

noMembers_perOrga = currentMembers["orgaName"].value_counts().reset_index()
noMembers_perOrga.columns = ["organization", "noMembers"]

# Sort organizations by number of members in descending order
noMembers_perOrga = noMembers_perOrga.sort_values("noMembers")

fig = px.bar(noMembers_perOrga, x = "noMembers", y = "organization",
             text=noMembers_perOrga["noMembers"],
             labels = {"noMembers": "Mitgliederanzahl", "organization": "Ausschuss/Fraktion"})


fig.update_layout(height=600)

# Different bar color for fraktionen
fraktionen = {"Grünen", "Grüne", "SPD", "Linke","CDU", "FDP", "AFD", "BSW", "Fraktion "}

colors = noMembers_perOrga["organization"].str.lower().apply(
    lambda x: "#4E8D6F" if any(f.lower() in x for f in fraktionen) else "#8bbf9f")

fig.update_traces(marker_color= colors, textfont_size=16) # Edit marker colors/ font size
fig.update_layout(yaxis={"categoryorder":"total ascending"})  # Sort

st.plotly_chart(fig, use_container_width = True)



###--------------------------------------------------------------------------###
### Current representatives                                                  ###
###--------------------------------------------------------------------------###

# Filter current members in BVV
BVV = currentMembers[(currentMembers["classification"] == "BVV") | (currentMembers["classification"] == "Bezirksparlament") | (currentMembers["classification"] == "Bezirk") | (currentMembers["classification"] == "Bezirksverordnetenversammlung") | (currentMembers["classification"] == "Bezirksverordnete") | (currentMembers["classification"] == "Parlament") | (currentMembers["classification"] == "Stadtbezirk")]

st.write(" ")

st.subheader(f"Aktuelle Mitglieder der BVV {selected_district.title()}")

# Distribute names on three columns
cols = st.columns(3) 
names = sorted(BVV["name"].tolist())

for i, name in enumerate(names):
    col = cols[i % 3]
    col.write(f"{i + 1}. {name}") #Add numbers

st.write(" ")


###--------------------------------------------------------------------------###
### Current members and their roles                                          ###
###--------------------------------------------------------------------------###

st.subheader(f"Aktuelle Mitglieder der BVV {selected_district.title()} und ihre Rollen")
st.dataframe(currentMembers[["name", "formOfAddress", "role", "votingRight", "orgaName"]].reset_index(drop=True), use_container_width=True)

st.write(" ")



###--------------------------------------------------------------------------###
### gender proportion of active members over time                            ###
###--------------------------------------------------------------------------###

# Filter all past and current members by BVV
BVV_all_years = members[(members["classification"] == "BVV") | (members["classification"] == "Bezirksparlament") | (members["classification"] == "Bezirk") | (members["classification"] == "Bezirksverordnetenversammlung") | (members["classification"] == "Bezirksverordnete") | (members["classification"] == "Parlament") | (members["classification"] == "Stadtbezirk")]

# Check if "formOfAddress" column exists
if "formOfAddress" not in BVV_all_years.columns or BVV_all_years["formOfAddress"].isnull().all():
    st.error("Error: 'formOfAddress' column is missing or contains only invalid values.")
else:
    # Datetime
    BVV_all_years["startDate"] = pd.to_datetime(BVV_all_years["startDate"], errors="coerce")
    BVV_all_years["endDate"] = pd.to_datetime(BVV_all_years["endDate"], errors="coerce")
 
    # Year range
    min_year = BVV_all_years["startDate"].dt.year.min()
    max_year = pd.to_datetime("today").year

    min_year = int(min_year)
    max_year = int(max_year)

    st.subheader(f"Entwicklung der Geschlechterverteilung in der BVV von {min_year} bis {max_year}")

    # List
    all_years_data = []

    # Loop through the range of years
    for year in range(min_year, max_year + 1):
        # Filter rows where the person was active during the specific year
        df_year = BVV_all_years[
            (BVV_all_years["startDate"].dt.year <= year) & 
            ((BVV_all_years["endDate"].dt.year >= year) | BVV_all_years["endDate"].isna())
        ]

        # Strip whitespace
        df_year["formOfAddress"] = df_year["formOfAddress"].str.strip()

        # Map gender
        gender_mapping = {"Frau": "w", "Herr": "m"}
        df_year["gender"] = df_year["formOfAddress"].map(gender_mapping)

        # Absolute counts
        # .shape[0] counts number of matching rows
        male_count = df_year[df_year["gender"] == "m"].shape[0]
        female_count = df_year[df_year["gender"] == "w"].shape[0]

        # Members by gender, percent
        noMembers_byGender = df_year["gender"].value_counts(normalize=True).round(3) * 100 

        # Percent by gender
        perc_fem = noMembers_byGender.get("w", 0)
        perc_mal = noMembers_byGender.get("m", 0)

        # Append year and calculated percentages to list
        all_years_data.append({
            "Jahr": year,
            "Anteil Frauen %": perc_fem,
            "Anteil Männer %": perc_mal,
            "Anzahl Frauen": female_count,
            "Anzahl Männer": male_count
        })

    # DataFrame
    all_years_gender = pd.DataFrame(all_years_data)

    color_map = {
        "Anteil Frauen %": "#c1a5fe",  
        "Anteil Männer %": "#4E8D6F"
        }

    fig = px.line(
        all_years_gender,
        x= "Jahr",
        y=["Anteil Frauen %", "Anteil Männer %"],
        labels={"value": "Prozent", "Jahr": "Jahr"},
        markers=True,
        color_discrete_map=color_map
    )

    fig.update_traces(
        hovertemplate=(
            "Jahr: %{x}<br>"
            "Anteil Frauen %: %{customdata[0]:.2f}<br>"  
            "Anteil Männer %: %{customdata[1]:.2f}<br>"  
            "Anzahl Frauen: %{customdata[2]}<br>" 
            "Anzahl Männer: %{customdata[3]}" 
        ),
        customdata=all_years_gender[["Anteil Frauen %", "Anteil Männer %", "Anzahl Frauen", "Anzahl Männer"]].values,  # custom data as array
    )
    
    fig.update_layout(
        yaxis=dict(ticksuffix="%"),
        legend_title_text="Legende"
    )

    st.plotly_chart(fig)

# Show dataset if checkbox
if st.checkbox("Datensatz anzeigen"):
    st.write(BVV_all_years[["role", "votingRight", "startDate", "endDate", "name", "formOfAddress", "orgaName", "shortName", "orgaType", "classification", "orga_startDate", "orga_endDate"]].reset_index(drop=True))



###--------------------------------------------------------------------------###
### average no. of roles per person f/m                                      ###
###--------------------------------------------------------------------------###


# Check if "formOfAddress" column exists
if "formOfAddress" not in currentMembers.columns or currentMembers["formOfAddress"].isnull().all():
    st.error("Error: 'formOfAddress' column is missing or contains only invalid values.")
else:
    st.subheader("Durchschnittliche Anzahl an Rollen pro Person nach Geschlecht")

    gender_role_counts = currentMembers.groupby(["formOfAddress", "name"]).size().reset_index(name="roles")
    # Map gender
    gender_role_counts["formOfAddress"] = gender_role_counts["formOfAddress"].map({"Herr": "M", "Frau": "W"})
    # Average number in column "roles"
    gender_role_avg = gender_role_counts.groupby("formOfAddress")["roles"].mean().reset_index()
    gender_role_avg["roles"] = gender_role_avg["roles"].round(2)
    # Average number by gender
    male_avg = gender_role_avg[gender_role_avg["formOfAddress"] == "M"]["roles"].item()
    female_avg = gender_role_avg[gender_role_avg["formOfAddress"] == "W"]["roles"].item()

    # Show metric in two columns
    col3, col4 = st.columns(2)

    with col3:
        st.metric("⌀ Anzahl an Rollen", f"{male_avg:.2f}")
        st.metric("⌀ Anzahl an Rollen", f"{female_avg:.2f}")
        
    with col4:
        # Add visual representation
        max_value = max(male_avg, female_avg)
        male_width = (male_avg / max_value) * 100
        female_width = (female_avg / max_value) * 100

        # st.progress() does not support custom hex color values
        # workaround with html
        st.markdown(f"""
        <div style="display: flex; align-items: center; margin-bottom: 10px;">
            <div style="width: 50px; text-align: right; margin-right: 10px;font-size: 14px;">Männer</div>
            <div style="background-color: #4E8D6F; width: {male_width}%; height: 20px;"></div>
        </div>
        <br>
        <div style="display: flex; align-items: center;">
            <div style="width: 50px; text-align: right; margin-right: 10px;font-size: 14px;">Frauen</div>
            <div style="background-color: #c1a5fe; width: {female_width}%; height: 20px;"></div>
        </div>
        """, unsafe_allow_html=True)

st.write(" ")
st.write(" ")



###--------------------------------------------------------------------------###
### Load meetings data and agenda items                                      ###
###--------------------------------------------------------------------------###

meetingUrl = bodiesData["data"][0]["meeting"]

meetingData = fetch_data(meetingUrl)


#agendaItems
agendaData = fetch_agenda_data(meetingData)


# Initialize agenda_item_names
agenda_item_names = []

# Check if agenda data is empty
if not agendaData or all(
    len(meeting.get("agendaItems", [])) == 0 for meeting in agendaData
):
    # Show an error message if no agenda items are found
    st.error(f"No agenda items found for {selected_district}.")
else:
    # Extract agenda item names
    agenda_item_names = [
        agendaItem["name"]
        for meeting in agendaData
        for agendaItem in meeting.get("agendaItems", [])
        if "name" in agendaItem
    ]

agendaItems = pd.DataFrame(agenda_item_names, columns=["Agenda Items"])



###--------------------------------------------------------------------------###
### word cloud from the agenda items                                         ###
###--------------------------------------------------------------------------###

col3, col4 = st.columns(2)


if len(agenda_item_names) > 0:
    with col3:
        st.subheader("Sitzungen und Tagesordnungspunkte")
        st.markdown("##### Finde Sitzungsinformationen zu Tagesordnungspunkten, die dich interessieren:")
        stopwords = set([
            "der", "die", "das", "und", "zur", "von", "den", "im", "des", "aus", "einer",
            "zu", "auf", "für", "mit", "nicht", "bei", "über", "als", "es", "dem","eine",
            "werden", "eine", "oder", "an", "ein", "haben", "nach", "mehr", "dass","ist",
            "am", "in", "auch", "zum", "liegen", "keine", "wie", "ohne", "vor", "gegen",
            "vom", "von", "beim", "kein"
        ])

        # Combine all agenda items in one text
        text = " ".join(agenda_item_names)

        # Create word cloud, exclude stopwords
        wordcloud = WordCloud(
            width=800,  
            height=400,  
            background_color="white",  
            colormap="Grays",  
            max_words=100,  
            stopwords=stopwords, 
            contour_color="black",  
            contour_width=1
        ).generate(text)

        # Plot word cloud
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.imshow(wordcloud, interpolation="bilinear")
        ax.axis("off")  

        
        st.pyplot(fig)




###--------------------------------------------------------------------------###
### Search agenda items in meetings                                          ###
###--------------------------------------------------------------------------###

if len(agenda_item_names) > 0:
  
    # User input for the search word
    word_to_search = col3.text_input("Bitte ein Suchwort eingeben (z.B. Verkehr, Kita, Wohnen, Haushalt etc.):", "")

    # Check if a search word is provided
    if word_to_search:
        matching_items = []

        # Iterate through meetings and agenda items to find matches
        for meeting in agendaData:

            # Iterate over the agenda items for each meeting
            for agenda_item in meeting.get("agendaItems", []):
                # Check if the search word is in the agenda item name
                if word_to_search.lower() in agenda_item["name"].lower():
                    meeting_url = meeting["id"]

                    try:
                        response = requests.get(meeting_url)
                        response.raise_for_status() 
                        meeting_data = response.json()

                        # Extract location description 
                        location = meeting_data.get("location", {})
                        location_description = location.get("description", "Unbekannt") 

                    except Exception as e:
                        print(f"Failed to fetch location for meeting {meeting_url}: {e}")

                    matching_items.append({
                        "Meeting Name": meeting["name"],
                        "Start Time": meeting["start"],
                        "End Time": meeting["end"],
                        "Location": location_description,
                        "Agenda Item": agenda_item["name"],
                        "Public": "Yes" if agenda_item["public"] else "No"
                    })

        # Display the matching results
        if matching_items:
            st.write(f"{len(matching_items)} Treffer für '{word_to_search}' gefunden:")
            # Show results in data frame
            st.dataframe(matching_items, use_container_width=True)  
        else:
            st.write(f"Keine Treffer für '{word_to_search}' gefunden.", use_container_width=True)