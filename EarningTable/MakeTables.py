from ProPackage.LangMySQL import *
from ProPackage.ProConfig import *
from ProPackage.ProMySqlDB import ProMySqlDB
from ProPackage.ProTool import *


def MakeCompanyOITableList(mySqlDB, company, start, end, proLog=None, isLog=False):
    """
    生成某期货公司一段时期内所有期货合约上的持仓情况。
    :param mySqlDB:reader
    :param company:
    :param start:
    :param end:
    :param proLog:
    :param isLog:
    :return:ContractList
    """
    daylist = MySql_GetDateLists(mySqlDB, '2010-01-01')
    Table = []
    for date in daylist[start:end]['Date']:
        temp = Mysql_GetCompanyOITable(mySqlDB, company, date, proLog, True)
        Table.append(temp)
    try:
        ans = pd.concat(Table)
        ans.insert(0, 0, value=ans.index.values)
        ans = ans.rename(columns={0: '合约代码'})
        ans = ans.where(pd.notnull(ans), None)
    except ValueError:
        if (isLog and proLog != None):
            proLog.Log("%s  期间未没有期货持仓排名\n" % company, True)
            proLog.Close()
        pass
    else:
        return ans


def MakeEarningTable(mySqlDB, mySqlDB2, contract, company, multipliertable):
    """
    从ContractList表中提取单合约单期货公司未填充null的持仓信息,之后结合texchangefutureday中价格信息，
    填充完整单合约历史持仓数据。
    :param mySqlDB:
    :param contract:
    :param company:
    :return:
    """
    table = Mysql_GetSimpleCompanyList(mySqlDB, contract, company)
    pricetable = Mysql_GetOneContractPrice(mySqlDB2, contract)
    table['日期'] = pd.to_datetime(table['日期']).map(lambda x: x.date())
    pricetable['日期'] = pd.to_datetime(pricetable['日期']).map(lambda x: x.date())
    table = table.set_index(table['日期'])
    pricetable = pricetable.set_index(pricetable['日期'])

    table = table.reindex(pricetable.index, fill_value=None)
    table[['合约代码', '日期', '交易所', '会员简称', '期货品种']] = table[['合约代码', '日期', '交易所', '会员简称', '期货品种']]. \
        apply(lambda x: x.fillna(method='ffill'))
    table['持买仓量昨日'] = (table['持买仓量'] - table['持买增减量']).shift(-1)
    table['持买仓量'] = table['持买仓量'].fillna(table['持买仓量昨日'])
    table['持买增减量昨日'] = table['持买仓量'].diff()
    table['持买增减量'] = table['持买增减量'].fillna(table['持买增减量昨日'])
    table['持卖仓量昨日'] = (table['持卖仓量'] - table['持卖增减量']).shift(-1)
    table['持卖仓量'] = table['持卖仓量'].fillna(table['持卖仓量昨日'])
    table['持卖增减量昨日'] = table['持卖仓量'].diff()
    table['持卖增减量'] = table['持卖增减量'].fillna(table['持卖增减量昨日'])

    table['当日结算价'] = pricetable['当日结算价']
    table['开盘价'] = pricetable['开盘价']
    table['最高价'] = pricetable['最高价']
    table['最低价'] = pricetable['最低价']
    table['收盘价'] = pricetable['收盘价']
    table['合约持仓量'] = pricetable['持仓量']
    table[['合约代码', '日期', '交易所', '会员简称', '期货品种']] = table[['合约代码', '日期', '交易所', '会员简称', '期货品种']]. \
        apply(lambda x: x.fillna(method='bfill'))

    table = table[table['合约代码'].notnull()]
    table = table.fillna(0)
    table['净持仓'] = table['持买仓量'] - table['持卖仓量']
    table['净持仓变动'] = table['持买增减量'] - table['持卖增减量']

    table['当日盈亏'] = ((table['持买仓量'].shift(1) * (table['当日结算价'].diff()) - \
                      table['持卖仓量'].shift(1) * (table['当日结算价'].diff())) * multipliertable['合约乘数'][
                         table['期货品种'][0]]).fillna(0)
    table['期货公司'] = company
    table['日期'] = table.index
    return table[['合约代码', '日期', '交易所', '会员简称', '持买仓量', '持买增减量', \
                  '持卖仓量', '持卖增减量', '合约持仓量', '期货品种', '开盘价', '最高价', '最低价', '收盘价', '当日结算价', '净持仓', '净持仓变动', '当日盈亏']]
    return table


def TableToMysql(mySqlDB, table):
    """

    :param mySqlDB:
    :param table:
    :return:
    """
    values = frameToTuple(table)
    MySql_BatchInsertComanpyListTest_Test(mySqlDBLocal, values)


if __name__ == '__main__':
    mySqlDBReader = ProMySqlDB(mySqlDBC_DataOIDB_Name, mySqlDBC_User,
                               mySqlDBC_Passwd, mySqlDBC_Host, mySqlDBC_Port)
    mySqlDBLocal = ProMySqlDB(mySqlDBC_EARNINGDB_Name, mySqlDBC_UserLocal,
                              mySqlDBC_Passwd, mySqlDBC_HostLocal, mySqlDBC_Port)

    company = '永安期货'
    start = '2010-01-04'
    end = '2018-10-30'
    # ans = Mysql_GetSimpleCompanyList(mySqlDBLocal, 'CF1605', company)
    ans = runtimeR(MakeCompanyOITableList, mySqlDBReader, company, start, end)
    runtime(TableToMysql, mySqlDBLocal, ans)

    mySqlDBReader.Close()
    mySqlDBLocal.Close()