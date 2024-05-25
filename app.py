from dash import Dash, html

print("Initializing app...")
app = Dash(__name__)
server = app.server

print("Setting layout...")
app.layout = html.Div("Hello, world!")

if __name__ == '__main__':
    print("Running server...")
    app.run_server(debug=True, host='0.0.0.0', port=8050)

# This is a test comment to trigger a change