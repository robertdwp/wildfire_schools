import os
import pandas as pd
import plotly.graph_objs as go
from plotly.subplots import make_subplots
from dash import Dash, dcc, html
from dash.dependencies import Input, Output
import dash_bootstrap_components as dbc
import dash_table

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

# Debug: Print the columns of disaster_enrollment_df after merge
print("Debug: Columns of disaster_enrollment_df after merge")
print(disaster_enrollment_df.columns)

# Ensure the correct columns are numeric
disaster_enrollment_df['days'] = pd.to_numeric(disaster_enrollment_df['days'], errors='coerce')
disaster_enrollment_df['enrollment_y'] = pd.to_numeric(disaster_enrollment_df['enrollment_y'], errors='coerce')

# Calculate the total instructional days lost per school
disaster_enrollment_df['total_days_lost_school'] = disaster_enrollment_df['days'] * disaster_enrollment_df['enrollment_y']

# Aggregate the total days lost and enrollment at the county level
county_agg_df = disaster_enrollment_df.groupby(['year', 'county']).agg(
    total_days_lost=pd.NamedAgg(column='total_days_lost_school', aggfunc='sum'),
    total_enrollment=pd.NamedAgg(column='enrollment_y', aggfunc='sum')
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

# Filter the merged dataframe for California counties and years 2002 to 2018
california_counties_lower = [county.lower() for county in california_counties]
merged_df_california = county_incidents_df[
    (county_incidents_df['COUNTY_NAME'].isin(california_counties_lower)) & 
    (county_incidents_df['YEAR'] >= 2002) & 
    (county_incidents_df['YEAR'] <= 2018)
]

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
    html.Label('Select County:'),
    dcc.Dropdown(
        id='county-dropdown',
        options=[{'label': county.title(), 'value': county.title()} for county in california_counties],
        value='Alameda'  # Default value
    ),
    dcc.Graph(id='wildfire-chart'),
    html.H2('Data Table'),
    dash_table.DataTable(
        id='data-table',
        columns=[
            {'name': 'Year', 'id': 'year'},
            {'name': 'Total Students Affected', 'id': 'students_affected'},
            {'name': 'Total Days Lost', 'id': 'total_days_lost'},
            {'name': 'Total Enrollment', 'id': 'total_enrollment'},
            {'name': 'Instructional Days Lost per Student', 'id': 'days_per_student'}
        ],
        data=[]
    )
], fluid=True)

# Callback to update the chart and table based on selected county
@app.callback(
    [Output('wildfire-chart', 'figure'),
     Output('data-table', 'data')],
    [Input('county-dropdown', 'value')]
)
def update_chart(selected_county):
    # Filter the data for the selected county
    county_data = merged_df_california[merged_df_california['COUNTY_NAME'] == selected_county.lower()]
    disaster_data = county_agg_df[county_agg_df['county'] == selected_county.lower()]
    enrollment_data = enrollment_df[(enrollment_df['county'] == selected_county.lower()) & (enrollment_df['year'] == 2018)]

    # Aggregate the students affected data by year
    agg_df = county_data.groupby('YEAR')['INCIDENT_ID'].count().reset_index()
    agg_df.rename(columns={'YEAR': 'Year', 'INCIDENT_ID': 'Students_Affected'}, inplace=True)

    print("Debug: agg_df")
    print(agg_df.head())

    # Merge with disaster days data
    plot_df = pd.merge(agg_df, disaster_data, left_on='Year', right_on='year', how='left').fillna(0)

    print("Debug: plot_df")
    print(plot_df.head())

    # Ensure the "Students Affected" y-axis max is set to the total number of students enrolled in the county in 2018
    enrollment_2018 = enrollment_data['enrollment'].values[0] if not enrollment_data.empty else global_students_max

    # Create the plot
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.add_trace(
        go.Bar(x=plot_df['Year'], y=plot_df['Students_Affected'], name='Students Affected by Wildfire-related Closure Days', marker_color='orange'),
        secondary_y=False
    )
    fig.add_trace(
        go.Scatter(x=plot_df['Year'], y=plot_df['days_per_student'], name='Instructional Days Lost per Student due to Wildfires', marker=dict(color='blue')),
        secondary_y=True
    )

    # Add figure title and labels
    fig.update_layout(
        title='Impact of Wildfires on Instructional Days and Students Affected (2002-2018)',
        xaxis_title='Year',
        xaxis=dict(range=[2002, 2018]),
        yaxis=dict(title='Students Affected by Wildfire-related Closure Days', range=[global_students_min, enrollment_2018]),
        yaxis2=dict(title='Instructional Days Lost per Student due to Wildfires', range=[global_days_min, global_days_max]),
        legend=dict(x=0.01, y=0.99),
        margin=dict(l=40, r=40, t=40, b=40)
    )

    # Prepare the data for the table
    table_data = plot_df[['Year', 'Students_Affected', 'total_days_lost', 'total_enrollment', 'days_per_student']].to_dict('records')

    return fig, table_data

# Entry point for Gunicorn
application = app.server

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8050))
    app.run_server(debug=True, port=port, host='0.0.0.0')
