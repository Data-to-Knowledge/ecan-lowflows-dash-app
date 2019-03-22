# -*- coding: utf-8 -*-
import dash
import dash_core_components as dcc
import dash_html_components as html
from dash.dependencies import Input, Output, State
import dash_table
import plotly
import plotly.graph_objs as go
import pandas as pd
import numpy as np
from pdsql import mssql
from pyproj import Proj, transform
import urllib

pd.options.display.max_columns = 10


app = dash.Dash(__name__)
server = app.server

#######################################
### Functions


def rd_ts_summ(server, db, ts_summ_table, dataset_table, mtype_table, sites_table, sites_cols):
    ## Load ts summary data
    ts_summ1 = mssql.rd_sql(server, db, ts_summ_table)
    ts_summ1['FromDate'] = pd.to_datetime(ts_summ1['FromDate'])
    ts_summ1['ToDate'] = pd.to_datetime(ts_summ1['ToDate'])

    ## Load other data
    datasets1 = mssql.rd_sql(server, db, dataset_table)
    mtypes = mssql.rd_sql(server, db, mtype_table)
    datasets = pd.merge(datasets1, mtypes, on='MeasurementType')
    datasets['Dataset Name'] = datasets.Feature + ' - ' + datasets.MeasurementType + ' - ' + datasets.CollectionType + ' - ' + datasets.DataCode + ' - ' + datasets.DataProvider + ' (' + datasets.Units + ')'

    ## Merge the two
    ts_summ2 = pd.merge(datasets, ts_summ1, on='DatasetTypeID')

    ## Get site info
    sites = mssql.rd_sql(server, db, sites_table, sites_cols)
    sites['NZTMX'] = sites['NZTMX'].astype(int)
    sites['NZTMY'] = sites['NZTMY'].astype(int)

    # Hover text
    sites.loc[sites.ExtSiteName.isnull(), 'ExtSiteName'] = ''

    sites['hover'] = sites.ExtSiteID + '<br>' + sites.ExtSiteName.str.strip()

    # Convert projections
    xy1 = list(zip(sites['NZTMX'], sites['NZTMY']))
    x, y = list(zip(*[transform(from_crs, to_crs, x, y) for x, y in xy1]))

    sites['lon'] = x
    sites['lat'] = y

    ## Combine with everything
    ts_summ = pd.merge(sites, ts_summ2, on='ExtSiteID')

    return ts_summ


def rd_site_summ(server, db, lf_site_table, sites_table, from_date, to_date):
    site_summ = mssql.rd_sql(server, db, lf_site_table, ['site', 'date', 'site_type', 'flow_method', 'days_since_flow_est', 'flow', 'crc_count', 'min_trig', 'max_trig', 'restr_category'], from_date=from_date, to_date=to_date, date_col='date', rename_cols=['ExtSiteID', 'Date', 'Site type', 'Data source', 'Days since last estimate', 'Flow or water level', 'Crc count', 'Min trigger', 'Max trigger', 'Restriction category'])
    sites1 = site_summ.ExtSiteID.unique().tolist()

    ## Get site info
    sites = mssql.rd_sql(server, db, sites_table, ['ExtSiteID', 'ExtSiteName', 'NZTMX', 'NZTMY'], where_in={'ExtSiteID': sites1})
    sites['NZTMX'] = sites['NZTMX'].astype(int)
    sites['NZTMY'] = sites['NZTMY'].astype(int)

    sites.loc[sites.ExtSiteName.isnull(), 'ExtSiteName'] = ''

    # Convert projections
    xy1 = list(zip(sites['NZTMX'], sites['NZTMY']))
    x, y = list(zip(*[transform(from_crs, to_crs, x, y) for x, y in xy1]))

    sites['lon'] = x
    sites['lat'] = y

    combo = pd.merge(sites, site_summ, on='ExtSiteID')

    # Hover text
    combo['hover'] = combo.ExtSiteID + '<br>' + combo.ExtSiteName.str.strip() + '<br>' + combo['Data source'] + ' ' + combo['Days since last estimate'].astype(str) + ' day(s) ago'

    return combo


##########################################
### Parameters

server = 'edwprod01'
db = 'hydro'
sites_table = 'ExternalSite'
lf_site_table = 'LowFlowRestrSite'
lf_site_band_table = 'LowFlowRestrSiteBand'
lf_crc_table = 'LowFlowRestrSiteBandCrc'
#ts_summ_table = 'TSDataNumericDailySumm'
#ts_table = 'TSDataNumericDaily'
#dataset_table = 'vDatasetTypeNamesActive'
#mtype_table = 'MeasurementType'
sites_cols = ['ExtSiteID', 'ExtSiteName', 'NZTMX', 'NZTMY']
#datasettypes = [4, 5, 15]
#datasettype_names = {4: 'Water Level (m)', 5: 'Flow (m3/s)', 15: 'Precip (mm)'}

site_types = ['LowFlow', 'Residual']
data_source = ['Telemetered', 'Correlated from Telem', 'Gauged', 'Manually Calculated', 'GW manual']
restr_type = ['No', 'Partial', 'Full', 'Deactivated']

ts_plot_height = 600
map_height = 700

#default_band_options = [{'value:': 'All Bands', 'label': 'All Bands'}]

default_colors = plotly.colors.DEFAULT_PLOTLY_COLORS

### Convert projections
from_crs = Proj('+proj=tmerc +ellps=GRS80 +lon_0=173 +x_0=1600000 +y_0=10000000 +k_0=0.9996 +lat_0=0 +units=m +no_defs', preserve_units=True)
to_crs = Proj('+proj=longlat +datum=WGS84')

restr_color_dict = {'No': 'rgb(44, 160, 44)', 'Partial': 'rgb(255, 127, 14)', 'Full': 'rgb(214, 39, 40)', 'Deactivated': 'rgb(31, 119, 180)'}

table_cols = ['ExtSiteID', 'ExtSiteName', 'NZTMX', 'NZTMY', 'Date', 'Site type', 'Data source', 'Days since last estimate', 'Flow or water level', 'Crc count', 'Min trigger', 'Max trigger', 'Restriction category']

lat1 = -43.45
lon1 = 171.9
zoom1 = 7

mapbox_access_token = "pk.eyJ1IjoibXVsbGVua2FtcDEiLCJhIjoiY2pwbHloa2ZwMDA2cTQybzRnZm01dGczMCJ9.e_yydJz08VyqKWqUlzdgQg"

###############################################
### App layout

map_layout = dict(mapbox = dict(layers = [], accesstoken = mapbox_access_token, style = 'outdoors', center=dict(lat=lat1, lon=lon1), zoom=zoom1), margin = dict(r=0, l=0, t=0, b=0), autosize=True, hovermode='closest', height=map_height, showlegend=True, legend=dict(x=0, y=1, traceorder='normal', font=dict(family='sans-serif', size=12, color='#000'), bgcolor='#E2E2E2', bordercolor='#FFFFFF', borderwidth=2))

def serve_layout():

    ### prepare summaries and initial states
    to_date = pd.Timestamp.now()
    from_date = to_date - pd.DateOffset(weeks=2)

    ### Read in site summary data
    init_summ = rd_site_summ(server, db, lf_site_table, sites_table, str(from_date.date()), str(to_date.date()))

    new_sites = init_summ.drop_duplicates('ExtSiteID')

    layout = html.Div(children=[
    html.Div([
        html.P(children='Filter sites by:'),
		html.Label('Site Type'),
		dcc.Dropdown(options=[{'label': d, 'value': d} for d in site_types], multi=True, value='LowFlow', id='site-type'),
        html.Label('Data Source'),
		dcc.Dropdown(options=[{'label': d, 'value': d} for d in data_source], multi=True, value=data_source, id='data-source'),
        html.Label('Restriction Category'),
		dcc.Dropdown(options=[{'label': d, 'value': d} for d in restr_type], multi=True, value=restr_type, id='restr-type'),
        html.Label('Date Range'),
		dcc.DatePickerRange(
            end_date=str(to_date.date()),
            display_format='DD/MM/YYYY',
            start_date=str(from_date.date()),
            id='date_sel'
#               start_date_placeholder_text='DD/MM/YYYY'
            ),
        html.Label('Site IDs'),
		dcc.Dropdown(options=[{'label': d, 'value': d} for d in new_sites.ExtSiteID.sort_values()], multi=True, id='sites-dropdown')
		], className='two columns', style={'margin': 20}),

	html.Div([
        html.P('Click on a site:', style={'display': 'inline-block'}),
		dcc.Graph(
                id = 'site-map',
                style={'height': map_height},
                figure=dict(
                        data = [dict(lat = new_sites['lat'],
                                     lon = new_sites['lon'],
                                     text = new_sites['hover'],
                                     type = 'scattermapbox',
                                     hoverinfo = 'text',
                                     marker = dict(
                                             size=8,
                                             color='black',
                                             opacity=1
                                             )
                                     )
                                ],
                        layout=map_layout),
                config={"displaylogo": False}),

        html.A(
            'Download Site Summary Data',
            id='download-summ',
            download="site_summary.csv",
            href="",
            target="_blank",
            style={'margin': 50}),

        dash_table.DataTable(
            id='summ_table',
            columns=[{"name": i, "id": i, 'deletable': True} for i in init_summ.columns],
            data=init_summ.astype(str).to_dict('rows'),
            sorting=True,
            sorting_type="multi",
            style_cell={
                'minWidth': '80px', 'maxWidth': '200px',
                'whiteSpace': 'normal'
            },
#            column_widths=[20, 20, 20, 20, 20, 20, 20, 20, 20, 20, 20, 20, 20, 20]
            )

	], className='four columns', style={'margin': 20}),

    html.Div([

		html.P('Select band for time series plot:', style={'display': 'inline-block'}),
		dcc.Dropdown(options=[], multi=True, id='band-dropdown'),
		dcc.Graph(
			id = 'selected-data',
			figure = dict(
				data = [dict(x=0, y=0)],
                layout = dict(
                        paper_bgcolor = '#F4F4F8',
                        plot_bgcolor = '#F4F4F8',
                        height = ts_plot_height
                        )
                ),
			config={"displaylogo": False}
            ),
        html.A(
            'Download Time Series Data',
            id='download-tsdata',
            download="tsdata.csv",
            href="",
            target="_blank",
            style={'margin': 50})
	], className='six columns', style={'margin': 10, 'height': 900}),
    html.Div(id='summ_data', style={'display': 'none'}, children=init_summ.to_json(date_format='iso', orient='split')),
    dcc.Graph(id='map-layout', style={'display': 'none'}, figure=dict(data=[], layout=map_layout))
], style={'margin':0})

    return layout


app.layout = serve_layout

app.css.append_css({'external_url': 'https://codepen.io/plotly/pen/EQZeaW.css'})

########################################
### Callbacks


@app.callback(
    Output('summ_data', 'children'), [Input('date_sel', 'start_date'), Input('date_sel', 'end_date')])
def store_summ(start_date, end_date):
#    ts_summ['FromDate'] = pd.to_datetime(ts_summ['FromDate'])
#    ts_summ['ToDate'] = pd.to_datetime(ts_summ['ToDate'])
    new_summ = rd_site_summ(server, db, lf_site_table, sites_table, start_date, end_date)
    print('store_summ', start_date, end_date)
    return new_summ.to_json(date_format='iso', orient='split')


@app.callback(
		Output('map-layout', 'figure'),
		[Input('site-map', 'relayoutData')],
		[State('map-layout', 'figure')])
def update_map_layout(relay, figure):
    if relay is not None:
#        print(figure['layout'])
        if 'mapbox.center' in relay:
#            print(relay)
            lat = float(relay['mapbox.center']['lat'])
            lon = float(relay['mapbox.center']['lon'])
            zoom = float(relay['mapbox.zoom'])
            new_layout = figure['layout'].copy()
            new_layout['mapbox']['zoom'] = zoom
            new_layout['mapbox']['center']['lat'] = lat
            new_layout['mapbox']['center']['lon'] = lon
        else:
            new_layout = figure['layout'].copy()
    else:
        new_layout = figure['layout'].copy()

    return dict(data=[], layout=new_layout)


@app.callback(
		Output('site-map', 'figure'),
		[Input('summ_data', 'children'), Input('site-type', 'value'), Input('data-source', 'value'), Input('restr-type', 'value')],
		[State('map-layout', 'figure'), State('date_sel', 'end_date')])
def display_map(summ_data, site_type, data_source, restr_type, figure, end_date):
    if isinstance(site_type, str):
        site_type = [site_type]
    if isinstance(data_source, str):
        data_source = [data_source]
    if isinstance(restr_type, str):
        restr_type = [restr_type]

    new_summ = pd.read_json(summ_data, orient='split')
    new_sites = new_summ[(new_summ['Date'] == end_date) & (new_summ['Site type'].isin(site_type)) & (new_summ['Data source'].isin(data_source)) & (new_summ['Restriction category'].isin(restr_type))].drop_duplicates('ExtSiteID')
#    print(new_sites)
#    print(new_summ.ExtSiteID.unique())

    data = []
    for r in restr_type:
        sub_sites = new_sites[new_sites['Restriction category'] == r]
        subset = dict(
    		lat = sub_sites['lat'],
    		lon = sub_sites['lon'],
    		text = sub_sites['hover'],
    		type = 'scattermapbox',
    		hoverinfo = 'text',
    		marker = dict(size=10, color=restr_color_dict[r], opacity=1),
            name = r
            )
        data.append(subset)

    fig = dict(data=data, layout=figure['layout'])
    return fig


@app.callback(
    Output('band-dropdown', 'options'),
    [Input('sites-dropdown', 'value'), Input('site-map', 'clickData')],
    [State('date_sel', 'end_date')])
def update_band_options(sites, clickdata, end_date):
    if not sites:
        options1 = []
    else:
        sites1 = [str(s) for s in sites]
        site_bands = mssql.rd_sql(server, db, lf_site_band_table, ['band_num', 'band_name', 'site_type'], where_in={'site': sites1}, from_date=end_date, to_date=end_date, date_col='date').drop_duplicates(['band_name'])
        site_bands['label'] = site_bands['band_name'] + ' - ' + site_bands['site_type']
        site_bands1 = site_bands.rename(columns={'band_num': 'value'}).drop(['band_name', 'site_type'], axis=1)
        options1 = site_bands1.to_dict('records')

#    print(options1)
    return options1


@app.callback(
        Output('sites-dropdown', 'options'),
        [Input('summ_data', 'children')])
def update_sites_options(summ_data):
    new_summ = pd.read_json(summ_data, orient='split')
    sites = np.sort(new_summ.ExtSiteID.unique())
    options1 = [{'label': i, 'value': i} for i in sites]
    return options1


@app.callback(
        Output('sites-dropdown', 'value'),
        [Input('site-map', 'selectedData'), Input('site-map', 'clickData')])
def update_sites_values(selectedData, clickData):
    if selectedData is not None:
        sites1 = [s['text'].split('<br>')[0] for s in selectedData['points']]
        print(sites1)
    elif clickData is not None:
        sites1 = [clickData['points'][0]['text'].split('<br>')[0]]
        print(sites1)
    else:
        sites1 = []
    return sites1[:1]


@app.callback(
	Output('selected-data', 'figure'),
	[Input('sites-dropdown', 'value'), Input('band-dropdown', 'value'), Input('date_sel', 'start_date'), Input('date_sel', 'end_date')])
def display_data(sites, bands, start_date, end_date):

    print(sites, bands, start_date, end_date)
    if not sites or bands is None:
        return dict(
			data = [dict(x=0, y=0)],
			layout = dict(
				title='Click on the map to select sites',
				paper_bgcolor = '#F4F4F8',
				plot_bgcolor = '#F4F4F8'
			)
		)
#    print(bands)
    sites1 = [str(s) for s in sites]

    layout = dict(
            title = 'Site ' + sites1[0],
            paper_bgcolor = '#F4F4F8',
            plot_bgcolor = '#F4F4F8',
            xaxis = dict(range = [start_date, end_date]),
            showlegend=True,
            height=ts_plot_height,
            legend=dict(x=0,
                        y=1,
                        traceorder='grouped',
                        font=dict(family='sans-serif',
                                  size=12,
                                  color='#000'),
                        bgcolor='rgba(0, 0, 0, 0)'
                        ),
            yaxis=dict(title='Flow (m3/s) or water level (m)',
                       showgrid=True)
            )

#    if bands is None:
#        ts1 = mssql.rd_sql(server, db, lf_site_band_table, ['date', 'flow'], where_in={'site': sites1}, from_date=start_date, to_date=end_date, date_col='date')
#        flow_data = ts1[['date', 'flow']].drop_duplicates('date')
#        data = [go.Scattergl(
#                    x=flow_data.date,
#                    y=flow_data.flow,
#                    legendgroup='flow',
#                    name='Flow',
#                    line={'color': 'black'},
#                    opacity=1)]
#    else:

    if isinstance(bands, int):
        bands = [bands]

    ts1 = mssql.rd_sql(server, db, lf_site_band_table, ['date', 'band_name', 'flow', 'min_trig', 'max_trig', 'band_allo'], where_in={'site': sites1, 'band_num': bands}, from_date=start_date, to_date=end_date, date_col='date')

    color_dict = dict(zip(ts1.band_name.unique().tolist(), default_colors))

    flow_data = ts1[['date', 'flow']].drop_duplicates('date')
    data = [go.Scattergl(
                x=flow_data.date,
                y=flow_data.flow,
                legendgroup='flow',
                name='Flow',
                line={'color': 'black'},
                opacity=1)]
    for name, group in ts1.groupby('band_name'):
        min_trig = go.Scattergl(
                x=group.date,
                y=group.min_trig,
                legendgroup=name,
                name='Min Trigger, ' + name,
                mode='lines',
                line=dict(dash='dot', color=color_dict[name]),
                opacity=0.7,
                yaxis='y1')
        max_trig = go.Scattergl(
                x=group.date,
                y=group.max_trig,
                legendgroup=name,
                name='Max Trigger, ' + name,
                mode='lines',
                line=dict(dash='dash', color=color_dict[name]),
                opacity=0.7,
                yaxis='y1')
        allo = go.Scattergl(
                x=group.date,
                y=group.band_allo,
                legendgroup=name,
                name='Allowed Allocation %, ' + name,
                line=dict(color=color_dict[name]),
                opacity=0.7,
                yaxis='y2',
                xaxis='x1')
        data.extend([min_trig, max_trig, allo])

        layout['yaxis2'] = dict(title='Allowed Allocation %',
                                overlaying='y',
                                anchor= 'x',
                                side='right',
                                showgrid= False)

    fig = dict(data=data, layout=layout)
    return fig


@app.callback(
    Output('summ_table', 'data'),
    [Input('summ_data', 'children'), Input('sites-dropdown', 'value'), Input('site-map', 'selectedData'), Input('site-map', 'clickData')])
def plot_table(summ_data, sites, selectedData, clickData):
    new_summ = pd.read_json(summ_data, orient='split')[table_cols]

    if sites:
        new_summ = new_summ.loc[new_summ.ExtSiteID.isin(sites)]
    return new_summ.to_dict("rows")


@app.callback(
    Output('download-tsdata', 'href'),
    [Input('sites-dropdown', 'value'), Input('band-dropdown', 'value'), Input('date_sel', 'start_date'), Input('date_sel', 'end_date')])
def download_tsdata(sites, bands, start_date, end_date):

    if not sites or bands is None:
        return ''

    sites1 = [str(s) for s in sites]

    if isinstance(bands, int):
        bands = [bands]

    ts1 = mssql.rd_sql(server, db, lf_site_band_table, where_in={'site': sites1, 'band_num': bands}, from_date=start_date, to_date=end_date, date_col='date')

    csv_string = ts1.to_csv(index=False, encoding='utf-8')
    csv_string = "data:text/csv;charset=utf-8," + urllib.parse.quote(csv_string)
    return csv_string


@app.callback(
    Output('download-summ', 'href'),
    [Input('summ_data', 'children')])
def download_summ(summ_data):
    new_summ = pd.read_json(summ_data, orient='split')

    csv_string = new_summ.to_csv(index=False, encoding='utf-8')
    csv_string = "data:text/csv;charset=utf-8," + urllib.parse.quote(csv_string)
    return csv_string


if __name__ == '__main__':
	app.run_server(debug=True, host='0.0.0.0', port=8051)
