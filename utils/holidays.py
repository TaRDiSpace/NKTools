# -*- coding:utf-8 -*-

import json
import os
import re
from datetime import date, datetime, timedelta

import requests
from lxml import html as HTML


def get_holidays_from_file():
    print('load holidays from file')
    today = date.today()
    json_file = os.path.join(os.path.dirname(__file__), 'holidays.json')
    if os.path.exists(json_file):
        holiday_json = {}
        with open(json_file, encoding='utf-8') as f:
            holiday_json = json.load(f)
        if holiday_json['year'] == today.year:
            return holiday_json
        else:
            return None
    else:
        return None


def get_holidays_from_baidu():
    print('load holidays from baidu')
    today = date.today()
    relax_list = []
    work_list = []
    headers = {
        'Host': 'www.baidu.com',
        'X-Requested-With': 'ajax-request',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/59.0.3071.115 Safari/537.36',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Accept': '*/*',
        'Accept-Encoding': 'gzip, deflate',
        'Accept-Language': 'zh-CN,zh;q=0.8',
    }
    query_url = 'https://www.baidu.com/s?wd=%E8%8A%82%E5%81%87%E6%97%A5'
    response = requests.get(query_url, headers=headers)
    if response.status_code == 200:
        html = HTML.fromstring(response.text)
        holidays = html.xpath(
            '//div[@id="1"]/table//tr[not(@class="c-table-hihead")]')
        for holiday in holidays:
            name = holiday.xpath('td[1]/text()')[0]
            relax = holiday.xpath('td[2]/text()')[0]
            work = holiday.xpath('td[3]/text()')[0]
            total = holiday.xpath('td[4]/text()')[0]
            reg = re.compile(r'\d+')
            # 假日
            group = reg.findall(relax)
            if len(group) == 2:
                d = date(today.year, int(group[0]), int(group[1]))
                relax_list.append(d.strftime('%Y-%m-%d'))
            elif len(group) == 4:
                ds = date(today.year, int(group[0]), int(group[1]))  # 开始日期
                de = date(today.year, int(group[2]), int(group[3]))  # 结束日期
                dsstr = ds.strftime('%Y-%m-%d')
                destr = de.strftime('%Y-%m-%d')
                while dsstr <= destr:
                    relax_list.append(dsstr)
                    ds = ds + timedelta(days=1)
                    dsstr = ds.strftime('%Y-%m-%d')
            # 补休
            group = reg.findall(work)
            for i in range(0, len(group), 2):
                d = date(today.year, int(group[i]), int(group[i+1]))
                work_list.append(d.strftime('%Y-%m-%d'))
    holiday_json = {"relax": relax_list,
                    "work": work_list, "year": today.year}
    with open(os.path.join(os.path.dirname(__file__), 'holidays.json'), 'w') as f:
        json.dump(holiday_json, f, indent=True)
    return holiday_json


def get_holiday_json():
    holiday_json = get_holidays_from_file()
    if not holiday_json:
        holiday_json = get_holidays_from_baidu()
    return holiday_json


def get_date_type(datestr):
    '''
    get date type

    params:
    datestr %Y-%m-%d

    return:
    0 节假日
    1 工作日
    '''
    holiday_json = get_holiday_json()
    d = datetime.strptime(datestr, '%Y-%m-%d')
    if datestr in holiday_json['relax']:
        return 0
    elif datestr in holiday_json['work']:
        return 1
    elif d.weekday() in [5, 6]:
        return 0
    else:
        return 1


if __name__ == "__main__":
    datestr = '2020-10-03'
    date_type = get_date_type(datestr)
    print(datestr, date_type)
