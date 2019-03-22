# -*- coding: utf-8 -*-
"""
Created on Tue Jan 15 15:59:37 2019

@author: MichaelEK
"""
from pdsql import mssql
import pandas as pd
import numpy as np
from pyproj import Proj, transform
from hilltoppy import web_service as ws
from allotools.allocation_ts import allo_ts

##########################################
### Parameters

## Convert projections
from_crs = Proj('+proj=tmerc +ellps=GRS80 +lon_0=173 +x_0=1600000 +y_0=10000000 +k_0=0.9996 +lat_0=0 +units=m +no_defs', preserve_units=True)
to_crs = Proj('+proj=longlat +datum=WGS84')

sites_table = 'ExternalSite'
ts_summ_table = 'TSDataNumericDailySumm'
ts_table = 'TSDataNumericDaily'
dataset_table = 'vDatasetTypeNamesActive'
mtype_table = 'MeasurementType'
lf_site_table = 'LowFlowRestrSite'
lf_site_band_table = 'LowFlowRestrSiteBand'
lf_crc_table = 'LowFlowRestrSiteBandCrc'
crc_wap_table = 'CrcWapAllo'

sites_cols = ['ExtSiteID', 'ExtSiteName', 'NZTMX', 'NZTMY']

wq_mtypes_table = 'WQMeasurement'
wq_summ_table = 'WQDataSumm'

base_url = 'http://wateruse.ecan.govt.nz'
hts = 'WQAll.hts'

##########################################
### Functions


def ecan_ts_summ(server, database, features, mtypes, ctypes, data_codes, data_providers):
    """

    """
    ### Get the appropriate dataset/mtype keys
    datasets1 = mssql.rd_sql(server, database, dataset_table, where_in={'Feature': features, 'MeasurementType': mtypes, 'CollectionType': ctypes, 'DataCode': data_codes, 'DataProvider': data_providers})
    mtypes1 = mssql.rd_sql(server, database, mtype_table, ['MeasurementType', 'Units'], where_in={'MeasurementType': mtypes})
    datasets2 = pd.merge(datasets1, mtypes1, on='MeasurementType')

    wq_mtypes = mssql.rd_sql(server, database, wq_mtypes_table, ['MeasurementID', 'Measurement'], where_in={'Measurement': mtypes})

    ### Get the summary data
    summ1 = mssql.rd_sql(server, database, ts_summ_table, ['ExtSiteID', 'DatasetTypeID', 'Min', 'Median', 'Mean', 'Max', 'Count', 'FromDate', 'ToDate'], where_in={'DatasetTypeID': datasets1.DatasetTypeID.tolist()})
    summ2 = pd.merge(summ1, datasets2, on='DatasetTypeID')

    if not wq_mtypes.empty:
        wq_mtypes.rename(columns={'Measurement': 'MeasurementType'}, inplace=True)
        wq_summ1 = mssql.rd_sql(server, database, wq_summ_table, ['ExtSiteID', 'MeasurementID', 'Units', 'FromDate', 'ToDate'], where_in={'MeasurementID': wq_mtypes.MeasurementID.tolist(), 'DataType': ['WQData']})
        wq_summ1['CollectionType'] = 'Manual Field'
        wq_summ1['DataCode'] = 'Primary'
        wq_summ1['DataProvider'] = 'ECan'
        wq_summ1['Feature'] = 'Aquifer'
        wq_summ1.loc[wq_summ1.ExtSiteID.str.contains('SQ', case=False), 'Feature'] = 'River'

        wq_summ2 = pd.merge(wq_summ1, wq_mtypes, on='MeasurementID').drop('MeasurementID', axis=1)

        wq_datasets1 = wq_summ2[['Feature', 'MeasurementType', 'CollectionType', 'DataCode', 'DataProvider']].drop_duplicates()
        wq_datasets1['DatasetTypeID'] = np.arange(10000, 10000 + len(wq_datasets1))

        wq_summ3 = pd.merge(wq_summ2, wq_datasets1, on=['Feature', 'MeasurementType', 'CollectionType', 'DataCode', 'DataProvider'])

        summ3 = pd.concat([summ2, wq_summ3], sort=True)
    else:
        summ3 = summ2

    ### Join
    summ3['FromDate'] = pd.to_datetime(summ3['FromDate'])
    summ3['ToDate'] = pd.to_datetime(summ3['ToDate'])

    return summ3


def app_ts_summ(server, database, features, mtypes, ctypes, data_codes, data_providers):
    """

    """
    ## Get TS summary
    ecan_summ = ecan_ts_summ(server, database, features, mtypes, ctypes, data_codes, data_providers)

    ## Dataset name
    ecan_summ['Dataset Name'] = ecan_summ.Feature + ' - ' + ecan_summ.MeasurementType + ' - ' + ecan_summ.CollectionType + ' - ' + ecan_summ.DataCode + ' - ' + ecan_summ.DataProvider + ' (' + ecan_summ.Units + ')'

    ## Get site info
    sites = mssql.rd_sql(server, database, sites_table, sites_cols)
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
    ts_summ = pd.merge(sites, ecan_summ, on='ExtSiteID')

    return ts_summ


def sel_ts_summ(ts_summ, features, mtypes, ctypes, data_codes, data_providers, start_date, end_date):
    if isinstance(features, str):
        features = [features]
    if isinstance(mtypes, str):
        mtypes = [mtypes]
    if isinstance(ctypes, str):
        ctypes = [ctypes]
    if isinstance(data_codes, str):
        data_codes = [data_codes]
    if isinstance(data_providers, str):
        data_providers = [data_providers]

    date_bool = ((ts_summ.FromDate >= start_date) & (ts_summ.FromDate <= end_date)) | ((ts_summ.ToDate >= start_date) & (ts_summ.ToDate <= end_date)) | ((ts_summ.FromDate <= start_date) & (ts_summ.ToDate >= end_date))
    df = ts_summ[date_bool & ts_summ.Feature.isin(features) & ts_summ.MeasurementType.isin(mtypes) & ts_summ.CollectionType.isin(ctypes) & ts_summ.DataCode.isin(data_codes) & ts_summ.DataProvider.isin(data_providers)].copy()

    df['FromDate'] = df['FromDate'].dt.date.astype(str)
    df['ToDate'] = df['ToDate'].dt.date.astype(str)
    df['Min'] = df['Min'].round(3).astype(str)
    df['Mean'] = df['Mean'].round(3).astype(str)
    df['Max'] = df['Max'].round(3).astype(str)

    return df


def ecan_ts_data(server, database, site_ts_summ, from_date, to_date, dtl_method=None):
    """

    """
    dataset1 = site_ts_summ.DatasetTypeID.iloc[0]
    sites1 = site_ts_summ.ExtSiteID.unique().tolist()

    if dataset1 < 10000:
        ts1 = mssql.rd_sql(server, database, ts_table, ['ExtSiteID', 'DateTime', 'Value'], where_in={'DatasetTypeID': [dataset1], 'ExtSiteID': sites1}, from_date=from_date, to_date=to_date, date_col='DateTime')
    else:
        ts_list = []
        mtype = site_ts_summ.MeasurementType.iloc[0]
        for s in sites1:
            ts0 = ws.get_data(base_url, hts, s, mtype, from_date, to_date, dtl_method=dtl_method)
            ts_list.append(ts0)
        ts1 = pd.concat(ts_list).reset_index().drop('Measurement', axis=1)
        ts1.rename(columns={'Site': 'ExtSiteID'}, inplace=True)

    return ts1


def lf_site_summ(server, database, from_date, to_date):
    site_summ = mssql.rd_sql(server, database, lf_site_table, ['site', 'date', 'site_type', 'flow_method', 'days_since_flow_est', 'flow', 'crc_count', 'min_trig', 'max_trig', 'restr_category'], from_date=from_date, to_date=to_date, date_col='date', rename_cols=['ExtSite', 'Date', 'Site type', 'Data source', 'Days since last estimate', 'Flow or water level', 'Crc count', 'Min trigger', 'Max trigger', 'Restriction category'])
    sites1 = site_summ.ExtSiteID.unique().tolist()

    ## Get site info
    sites = mssql.rd_sql(server, database, sites_table, ['ExtSiteID', 'ExtSiteName', 'NZTMX', 'NZTMY'], where_in={'ExtSiteID': sites1})
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


def app_allo_usage_summ(server, database, from_date, to_date, site_summ, usage_ts_summ):
    """

    """
    date_bool = ((usage_ts_summ.FromDate >= from_date) & (usage_ts_summ.FromDate <= to_date)) | ((usage_ts_summ.ToDate >= from_date) & (usage_ts_summ.ToDate <= to_date)) | ((usage_ts_summ.FromDate <= from_date) & (usage_ts_summ.ToDate >= to_date))
    usage_ts_summ1 = usage_ts_summ[date_bool].copy()

    lf_crc = mssql.rd_sql(server, database, lf_crc_table, ['site', 'band_num', 'date', 'crc'], where_in={'site': site_summ.ExtSiteID.unique().tolist()}, from_date=from_date, to_date=to_date, date_col='date')
    lf_crc['date'] = pd.to_datetime(lf_crc['date'])

    crc_wap = mssql.rd_sql(server, database, crc_wap_table, ['crc', 'wap'], where_in={'crc': lf_crc.crc.unique().tolist(), 'wap': usage_ts_summ1.ExtSiteID.unique().tolist()}).drop_duplicates()

    allo1 = allo_ts(server, from_date, to_date, 'D', 'daily volume', crc_filter={'crc': lf_crc.crc.unique().tolist()}).reset_index()
    allo2 = (allo1.groupby(['crc', 'date'])['allo'].sum()/24/60/60).reset_index()

    ## Get usage data
    ts1 = mssql.rd_sql(server, database, ts_table, ['ExtSiteID', 'DateTime', 'Value'], where_in={'DatasetTypeID': usage_ts_summ1.DatasetTypeID.unique().tolist(), 'ExtSiteID': crc_wap.wap.unique().tolist()}, from_date=from_date, to_date=to_date, date_col='DateTime')
    ts1['Value'] = ts1['Value']/24/60/60
    ts1.rename(columns={'ExtSiteID': 'wap', 'DateTime': 'date', 'Value': 'Usage'}, inplace=True)
    ts1['date'] = pd.to_datetime(ts1['date'])

    ts2 = pd.merge(crc_wap, ts1, on='wap')

    count1 = ts2.groupby(['wap', 'date']).crc.transform('count')
    ts2['Usage'] = (ts2['Usage']/count1).round(3)

    ts3 = ts2.groupby(['crc', 'date'])['Usage'].sum().reset_index()

    ## Combine

    allo_usage1 = pd.merge(allo2, ts3, on=['crc', 'date'], how='left')
    allo_usage1['usage/allo'] = allo_usage1.Usage/allo_usage1.allo

    allo_usage2 = pd.merge(lf_crc, allo_usage1, on=['crc', 'date'])

    return allo_usage2





#latest1 = allo_usage1.dropna().groupby('crc').last().sort_values('usage/allo', ascending=False).reset_index()
