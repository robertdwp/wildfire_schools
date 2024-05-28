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

# Convert relevant columns to numeric, coercing errors to NaN
disaster_days_df['days'] = pd.to_numeric(disaster_days_df['days'], errors='coerce')
enrollment_df['enrollment'] = pd.to_numeric(enrollment_df['enrollment'], errors='coerce')

# Filter the disaster days dataframe to only include wildfires
wildfire_keywords = ['wildfire', 'fire']  # Add any other relevant keywords
disaster_days_df = disaster_days_df[disaster_days_df['reason'].str.contains('|'.join(wildfire_keywords), case=False, na=False)]

# Merge disaster days dataframe with enrollment dataframe
disaster_enrollment_df = pd.merge(disaster_days_df, enrollment_df, on=['year', 'county'], how='inner')

# Rename columns for clarity
disaster_enrollment_df.rename(columns={'enrollment_x': 'school_enrollment', 'enrollment_y': 'county_enrollment'}, inplace=True)

# Ensure the correct columns are numeric
disaster_enrollment_df['days'] = pd.to_numeric(disaster_enrollment_df['days'], errors='coerce')
disaster_enrollment_df['school_enrollment'] = pd.to_numeric(disaster_enrollment_df['school_enrollment'], errors='coerce')
disaster_enrollment_df['county_enrollment'] = pd.to_numeric(disaster_enrollment_df['county_enrollment'], errors='coerce')

# Calculate the total instructional days lost per school
disaster_enrollment_df['total_days_lost_school'] = disaster_enrollment_df['days'] * disaster_enrollment_df['school_enrollment']

# Aggregate the total days lost and enrollment for affected schools at the county level
county_agg_df = disaster_enrollment_df.groupby(['year', 'county']).agg(
    total_days_lost=pd.NamedAgg(column='total_days_lost_school', aggfunc='sum'),
    affected_enrollment=pd.NamedAgg(column='school_enrollment', aggfunc='sum')
).reset_index()

# Calculate average instructional days lost per student for affected schools at the county level
county_agg_df['days_per_student_affected'] = county_agg_df['total_days_lost'] / county_agg_df['affected_enrollment']

# Ensure we have data for all years 2002-2018 for each county
years = list(range(2002, 2018 + 1))
full_years_df = pd.DataFrame({'year': years})
county_agg_full_df = pd.DataFrame()

for county in county_agg_df['county'].unique():
    county_data = county_agg_df[county_agg_df['county'] == county]
    county_full_data = full_years_df.merge(county_data, on='year', how='left').fillna({'total_days_lost': 0, 'affected_enrollment': 0, 'days_per_student_affected': 0})
    county_full_data['county'] = county
    county_agg_full_df = pd.concat([county_agg_full_df, county_full_data])

# Extract 2018 enrollment data for each county
enrollment_2018_df = enrollment_df[enrollment_df['year'] == 2018][['county', 'enrollment']].set_index('county')

# Debug: Print columns of county_incidents_df to check for correct column names
print("County Incidents DataFrame columns:", county_incidents_df.columns)

# Define the list of California counties
california_counties = [
    'alameda', 'alpine', 'amador', 'butte', 'calaveras', 'colusa', 'contra costa', 'del norte', 'el dorado', 'fresno', 
    'glenn', 'humboldt', 'imperial', 'inyo', 'kern', 'kings', 'lake', 'lassen', 'los angeles', 'madera', 'marin', 
    'mariposa', 'mendocino', 'merced', 'modoc', 'mono', 'monterey', 'napa', 'nevada', 'orange', 'placer', 'plumas', 
    'riverside', 'sacramento', 'san benito', 'san bernardino', 'san diego', 'san francisco', 'san joaquin', 
    'san luis obispo', 'san mateo', 'santa barbara', 'santa clara', 'santa cruz', 'shasta', 'sierra', 'siskiyou', 
    'solano', 'sonoma', 'stanislaus', 'sutter', 'tehama', 'trinity', 'tulare', 'tuolumne', 'ventura', 'yolo', 'yuba'
]

# Calculate global min and max for standardizing y-axis scales
# Filter the instructional days lost dataframe for years 2002 to 2018
instructional_days_lost = disaster_days_df.groupby(['year', 'county'])['days'].sum().reset_index()
instructional_days_lost = instructional_days_lost[(instructional_days_lost['year'] >= 2002) & (instructional_days_lost['year'] <= 2018)]
global_days_max = instructional_days_lost['days'].max()

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
    selected_county = selected_county.lower()
    # Filter the data for the selected county
    disaster_data = county_agg_full_df[county_agg_full_df['county'].str.contains(selected_county, na=False)]

    # Get the enrollment for the county in 2018
    max_students_affected = enrollment_2018_df.loc[selected_county, 'enrollment'] if selected_county in enrollment_2018_df.index else 0

    # Create the plot
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Bar(x=disaster_data['year'], y=disaster_data['affected_enrollment'], name='Students Affected', marker_color='orange'),
        secondary_y=False
    )
    fig.add_trace(
        go.Scatter(x=disaster_data['year'], y=disaster_data['days_per_student_affected'], name='Instructional Days Lost per Student (Affected Schools)', marker=dict(color='blue')),
        secondary_y=True
    )

    # Add figure title and labels
    fig.update_layout(
        xaxis_title='Year',
        xaxis=dict(tickmode='array', tickvals=years),
        yaxis=dict(title='Students Affected', range=[0, max_students_affected]),
        yaxis2=dict(title='Instructional Days Lost per Student (Affected Schools)', range=[0, 21]),
        legend=dict(x=0.01, y=0.99),
        margin=dict(l=40, r=40, t=40, b=40)
    )

    return fig

# Entry point for Gunicorn
application = app.server

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8050))
    app.run_server(debug=True, port=port, host='0.0.0.0')
