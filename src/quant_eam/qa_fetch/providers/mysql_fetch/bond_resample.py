import pandas as pd
import numpy as np
from pandas.tseries.frequencies import to_offset

def _bond_data_tick_resample(tick, _type='1min', if_drop=True):
    _temp = set(tick.index.date)
    resx = pd.DataFrame()
    tick.loc[:, 'quote_vol'] = tick['seq_no'].diff()
    tick.loc[:, 'quote_vol'] = tick[['seq_no', 'quote_vol']].apply(lambda x:x['seq_no'] if np.isnan(x['quote_vol']) else
                                                                  x['quote_vol'], axis=1)
    for item in _temp:
        _data = tick.loc[str(item):str(item)].sort_values("trade_date")
        _data1 = _data.resample(_type,
                                closed='right',
                                ).apply(
            {
                'strike_price': 'ohlc',
                'yield': 'ohlc', 'code': 'last',
                'vol': 'sum', 'tkn_vol': 'sum',
                'gvn_vol': 'sum', 'trade_vol': 'sum', 'quote_vol': 'sum'

            }
        )
        resx = resx.append(_data1)
    resx.columns = [x[1] + "_" + x[0].split("_")[-1] for x in _data1.columns[:8]] + [x[1] for x in _data1.columns[8:]]
    resx['trade_date'] = resx.index
    resx = resx.drop_duplicates().set_index(['trade_date'])

    return resx.ffill()


def one_hot_volume(x):
    '''
    对于XYZ类型的成交量进行分类
    '''
    if x =='X':
        return [1,1,0,0]
    elif x =='Y':
        return [1,0,1,0]
    elif x =='Z':
        return [1,0,0,1]

def bond_sh_data_resample(data,_type):
    '''
    对数据重采样成一日
    '''
    #对增量的数据跑一次resample
    data['exchange_area'] = data['symbol'].apply(lambda x :x.split(".")[1])
    data['code'] = data['symbol']
    #data = data.query("exchange_area=='IB'")
    data['trade_date'] = pd.to_datetime(data['trade_date'])
    data=data.query("strike_price!=0")
    data.loc[:, ['vol', 'tkn_vol', 'gvn_vol', 'trade_vol']] = data['side'].apply(
        lambda x: one_hot_volume(x)).values.tolist()
    #data.set_index(["create_time", 'symbol'], inplace=True, drop=False)
    data.set_index("create_time", inplace=True)
    data = data.groupby("code").apply(lambda x: _bond_data_tick_resample(x,_type=_type))
    data['symbol'] = data.index.get_level_values(0)
    data['trade_date'] = data.index.get_level_values(1)
    data.index=range(len(data))
    data = data.drop(columns=['code'])
    return data



def bond_data_resample(data,_type):
    '''
    对数据重采样成一日
    '''
    #对增量的数据跑一次resample
    data['exchange_area'] = data['symbol'].apply(lambda x :x.split(".")[1])
    data['code'] = data['symbol']
    data = data.query("exchange_area=='IB'")
    data['trade_date'] = pd.to_datetime(data['trade_date'])
    data=data.query("strike_price!=0")
    data.loc[:, ['vol', 'tkn_vol', 'gvn_vol', 'trade_vol']] = data['side'].apply(
        lambda x: one_hot_volume(x)).values.tolist()
    data.set_index(["create_time", 'symbol'], inplace=True, drop=False)
    data.set_index("create_time", inplace=True)
    data = data.groupby("code").apply(lambda x: _bond_data_tick_resample(x,_type=_type))
    data['symbol'] = data.index.get_level_values(0)
    data['trade_date'] = data.index.get_level_values(1)
    data.index=range(len(data))
    data = data.drop(columns=['code'])
    return data

