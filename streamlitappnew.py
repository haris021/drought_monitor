import streamlit as st
import geopandas as gpd 
import pandas as pd 
from datetime import datetime, timedelta
import plotly.graph_objects as go
import ee
import geemap.foliumap as geemap
import json as js

json_object = st.secrets["json_data"]
service_account = st.secrets["service_account"]


# Authorising the app
credentials = ee.ServiceAccountCredentials(service_account, key_data=json_object)
ee.Initialize(credentials)



@st.cache_data
def get_start_and_end_date(data):
    dataset = ee.ImageCollection(data) 
    info = dataset.aggregate_array('system:time_start').getInfo()
    time_start  = datetime(1970, 1, 1) + timedelta(seconds=(info[0] /1000))
    time_end = datetime(1970, 1, 1) + timedelta(seconds=(info[-1] /1000))

    return time_start, time_end

def convert_df_to_csv(df):
    # IMPORTANT: Cache the conversion to prevent computation on every rerun
    return df.to_csv().encode('utf-8')




selection_dict = {  'spei03': 'SPEI_03_month',
                    'spei06': 'SPEI_06_month',
                    'spei09': 'SPEI_09_month',
                    'spei12': 'SPEI_12_month'  }


st.title("Pakistan Drought Monitor")

divisions_master_df = pd.read_csv("DivisionFileNames.csv")
drough_index = st.sidebar.selectbox("Select Drought Index", tuple(['spei03','spei06','spei09','spei12']))
division = st.sidebar.selectbox("Select Division", tuple(divisions_master_df["Division"].values.tolist()))
st.sidebar.divider()
st.sidebar.subheader("Map Options")


dataset = ee.ImageCollection("CSIC/SPEI/2_8") 
start_date, end_date = get_start_and_end_date("CSIC/SPEI/2_8")

map_year = st.sidebar.select_slider("Select Year", options = tuple(range(start_date.year, end_date.year+1)))

if map_year == start_date.year:
  map_month = st.sidebar.select_slider("Select Month", options= tuple(range(start_date.month,13)))
elif map_year == end_date.year:
  map_month = st.sidebar.select_slider("Select Month", options= tuple(range(1,end_date.month+1)))
else:
   map_month = st.sidebar.select_slider("Select Month", options= tuple(range(1,13)))


st.sidebar.divider()
st.sidebar.subheader("Timeseries Options")



division_file_name = divisions_master_df.loc[divisions_master_df["Division"] == division]["File Name"].values.tolist()[0]

division_df = pd.read_csv(f"csv files/{division_file_name}")
division_df["time"] = pd.to_datetime(division_df["time"])
division_df = division_df.sort_values(by = "time")

time_start = division_df.head(1)["time"].dt.year.values.tolist()[0]
time_end = division_df.tail(1)["time"].dt.year.values.tolist()[0]

time_start = 1950

time_begin, time_stop = st.sidebar.slider("Select Time Range"
                                                , time_start, time_end,(time_start, time_end ))

division_df = division_df.loc[(division_df['time'].dt.year>=time_begin) & (division_df['time'].dt.year<=time_stop)]





dataset = dataset.filterDate(f'{map_year}-{map_month}-01', f'{map_year + 1}-{map_month}-01').select(selection_dict[drough_index]).first()
style = {"color": "black"}
Map = geemap.Map()
Map.add_shapefile("shapefile/PAK_adm2.shp", "Division Bounds", style_function = lambda x: style)

visParams = {
  "min": -2.33,
  "max":  2.33,
  "palette": [
    '8b1a1a', 'de2929', 'f3641d',
    'fdc404', '9afa94', '03f2fd',
    '12adf3', '1771de', '00008b',
  ]
}

Map.setCenter(69.3451, 30.3753, 5.3)





pakistan_boundary = gpd.read_file("Pakistan_with_Kashmir.shp")
pakistan_boundary_js = js.loads(pakistan_boundary.to_json())['features'][0]['geometry']['coordinates']
pakistan_geometry = ee.Geometry.MultiPolygon(pakistan_boundary_js)

Map.addLayer(dataset.clip(pakistan_geometry), visParams, f'{selection_dict[drough_index]}')

Map.add_colorbar(vis_params=visParams)
Map.addLayerControl()
Map.to_streamlit()








fig = go.Figure()
fig.add_trace(go.Bar(
    x=division_df['time'].loc[division_df[drough_index]>0],
    y=division_df[drough_index].loc[division_df[drough_index]>0],
    name='flood',
    marker_color='blue'
))
fig.add_trace(go.Bar(
    x=division_df['time'].loc[division_df[drough_index]<0],
    y=division_df[drough_index].loc[division_df[drough_index]<0],
    name='drought',
    marker_color='red'
))



# Set x and y labels
fig.update_layout(
    xaxis_title='Time',
    yaxis_title='SPEI', 
    title=go.layout.Title(
        text=f"{drough_index.upper()}-{division}<br><sup>{time_begin} - {time_stop}</sup>",
        xref="paper",
        x=0
    ),

)
st.plotly_chart(fig)
st.download_button(
  label="Download data as CSV",
  data=convert_df_to_csv(division_df[['time', drough_index]]),
  file_name=f'{division.upper().replace(" ","_")}_{drough_index.upper()}_{time_begin}_{time_end}.csv',
  mime='text/csv',
)
