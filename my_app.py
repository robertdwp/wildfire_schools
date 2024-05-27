import os
import pandas as pd
import plotly.graph_objs as go
from plotly.subplots import make_subplots
from dash import Dash, dcc, html
from dash.dependencies import Input, Output
import dash_bootstrap_components as dbc

# Load the datasets
incidents_df = pd.read_csv('wf_incidents.csv')
county_incidents_df = pd.read_csv('ics209-plus-wf_incidents_by_county_1999to2020.csv')
disaster_days_df = pd.read_csv('disasterDays_final.csv')
enrollment_df = pd.read_excel('county enrollment.xlsx')

# Transform the enrollment dataframe
enrollment_df = enrollment_df.melt(id_vars=['County'], var_name='year', value_name='enrollment')
enrollment_df['year'] = enrollment_df['year'].apply(lambda x: int(x.split('-')[0]))

# Rename columns for consistency
enrollment_df.rename(columns={'County': 'county'}, inplace=True)

# Ensure 'year' and 'county' columns are treated as lowercase in disaster days dataframe
disaster_days_df['county'] = disaster_days_df['county'].str.lower()
enrollment_df['county'] = enrollment_df['county'].str.lower()

# Ensure 'year' column is treated as integer in disaster days dataframe
disaster_days_df['year'] = disaster_days_df['year'].astype(int)

# Merge disaster days dataframe with enrollment dataframe
disaster_enrollment_df = pd.merge(disaster_days_df, enrollment_df, on=['year', 'county'], how='inner')

# Rename columns for clarity
disaster_enrollment_df.rename(columns={'enrollment_y': 'county_enrollment'}, inplace=True)

# Ensure the correct columns are numeric
disaster_enrollment_df['days'] = pd.to_numeric(disaster_enrollment_df['days'], errors='coerce')
disaster_enrollment_df['county_enrollment'] = pd.to_numeric(disaster_enrollment_df['county_enrollment'], errors='coerce')

# Calculate the total instructional days lost per school
disaster_enrollment_df['total_days_lost_school'] = disaster_enrollment_df['days'] * disaster_enrollment_df['county_enrollment']

# Aggregate the total days lost and enrollment at the county level
county_agg_df = disaster_enrollment_df.groupby(['year', 'county']).agg(
    total_days_lost=pd.NamedAgg(column='total_days_lost_school', aggfunc='sum'),
    total_enrollment=pd.NamedAgg(column='county_enrollment', aggfunc='sum')
).reset_index()

# Ensure the aggregated columns are numeric
county_agg_df['total_days_lost'] = pd.to_numeric(county_agg_df['total_days_lost'], errors='coerce')
county_agg_df['total_enrollment'] = pd.to_numeric(county_agg_df['total_enrollment'], errors='coerce')

# Calculate average instructional days lost per student at the county level
county_agg_df['days_per_student'] = county_agg_df['total_days_lost'] / county_agg_df['total_enrollment']

# Define the list of California counties
california_counties = [
    'Alameda', 'Alpine', 'Amador', 'Butte', 'Calaveras', 'Colusa', 'Contra Costa', 'Del Norte', 'El Dorado', 'Fresno', 
    'Glenn', 'Humboldt', 'Imperial', 'Inyo', 'Kern', 'Kings', 'Lake', 'Lassen', 'Los Angeles', 'Madera', 'Marin', 
    'Mariposa', 'Mendocino', 'Merced', 'Modoc', 'Mono', 'Monterey', 'Napa', 'Nevada', 'Orange', 'Placer', 'Plumas', 
    'Riverside', 'Sacramento', 'San Benito', 'San Bernardino', 'San Diego', 'San Francisco', 'San Joaquin', 
    'San Luis Obispo', 'San Mateo', 'Santa Barbara', 'Santa Clara', 'Santa Cruz', 'Shasta', 'Sierra', 'Siskiyou', 
    'Solano', 'Sonoma', 'Stanislaus', 'Sutter', 'Tehama', 'Trinity', 'Tulare', 'Tuolumne', 'Ventura', 'Yolo', 'Yuba'
]

# Convert to lowercase for matching
county_incidents_df['COUNTY_NAME'] = county_incidents_df['COUNTY_NAME'].str.lower().str.replace(' county', '')

# Print out the unique values in COUNTY_NAME for inspection
print("Unique COUNTY_NAME values in county_incidents_df:", county_incidents_df['COUNTY_NAME'].unique()[:50])  # Print only first 50 for brevity

# Check if all California counties are correctly formatted in the dataframe
california_counties_lower = [county.lower() for county in california_counties]
print("California counties (lowercase):", california_counties_lower)

# Filter the merged dataframe for California counties and years 2002 to 2018
merged_df_california = county_incidents_df[
    (county_incidents_df['COUNTY_NAME'].isin(california_counties_lower)) & 
    (county_incidents_df['YEAR'] >= 2002) & 
    (county_incidents_df['YEAR'] <= 2018)
]

# Print out debug information
print("Filtered merged_df_california:", merged_df_california.head())
print("Number of rows in county_incidents_df before filtering:", len(county_incidents_df))
print("Number of rows in county_incidents_df after filtering:", len(merged_df_california))

# Filter the instructional days lost dataframe for years 2002 to 2018
county_agg_df = county_agg_df[(county_agg_df['year'] >= 2002) & (county_agg_df['year'] <= 2018)]

# Calculate global min and max for standardizing y-axis scales
global_students_min = 0
global_students_max = enrollment_df[enrollment_df['year'] == 2018]['enrollment'].max()
global_days_min = 0
global_days_max = county_agg_df['days_per_student'].max()

# Initialize the Dash app
app = Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])

# Layout of the app
app.layout = dbc.Container([
    html.H1('Impact of Wildfires on Instructional Days and Students Affected'),
    html.Label('Select County:'),
    dcc.Dropdown(
        id='county-dropdown',
        options=[{'label': county.title(), 'value': county.title()} for county in california_counties],
        value='Alameda'  # Default value
    ),
    dcc.Graph(id='wildfire-chart')
], fluid=True)

# Callback to update the chart based on selected county
@app.callback(
    Output('wildfire-chart', 'figure'),
    [Input('county-dropdown', 'value')]
)
def update_chart(selected_county):
    # Filter the data for the selected county
    county_data = merged_df_california[merged_df_california['COUNTY_NAME'].str.contains(selected_county.lower(), na=False)]
    disaster_data = county_agg_df[county_agg_df['county'].str.contains(selected_county.lower(), na=False)]
    enrollment_data = enrollment_df[(enrollment_df['county'] == selected_county.lower()) & (enrollment_df['year'] == 2018)]

    # Print debug info
    print(f"county_data for {selected_county}:", county_data)
    print(f"disaster_data for {selected_county}:", disaster_data)
    print(f"enrollment_data for {selected_county}:", enrollment_data)

    # Aggregate the students affected data by year
    agg_df = county_data.groupby('YEAR')['INCIDENT_ID'].sum().reset_index()
    agg_df.rename(columns={'YEAR': 'Year'}, inplace=True)

    # Merge with disaster days data
    plot_df = pd.merge(agg_df, disaster_data, left_on='Year', right_on='year', how='left').fillna(0)

    # Print debug info
    print(f"plot_df for {selected_county}:", plot_df)

    # Create the plot
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Bar(x=plot_df['Year'], y=plot_df['INCIDENT_ID'], name='Students Affected', marker_color='orange'),
        secondary_y=False
    )
    fig.add_trace(
        go.Scatter(x=plot_df['Year'], y=plot_df['days_per_student'], name='Instructional Days Lost per Student', marker=dict(color='blue')),
        secondary_y=True
    )

    # Add figure title and labels
    fig.update_layout(
        title='Impact of Wildfires on Instructional Days and Students Affected (2002-2018)',
        xaxis_title='Year',
        xaxis=dict(range=[2002, 2018]),
        yaxis=dict(title='Students Affected', range=[global_students_min, global_students_max]),
        yaxis2=dict(title='Instructional Days Lost per Student', range=[global_days_min, global_days_max]),
        legend=dict(x=0.01, y=0.99),
        margin=dict(l=40, r=40, t=40, b=40)
    )

    return fig

# Entry point for Gunicorn
application = app.server

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8050))
    app.run_server(debug=True, port=port, host='0.0.0.0')
